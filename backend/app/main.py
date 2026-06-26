import base64
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.llm import LLMService
from app.tts import TTSService

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

from contextlib import asynccontextmanager
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database and tables...")
    try:
        await init_db()
        logger.info("Database initialization completed successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
    yield

app = FastAPI(title="Outbound Voice Agent API", lifespan=lifespan)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigResponse(BaseModel):
    provider: str
    model: str
    voice: str
    has_gemini_key: bool
    has_groq_key: bool

@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    return {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "voice": settings.DEFAULT_VOICE,
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "has_groq_key": bool(settings.GROQ_API_KEY)
    }

@app.get("/api/voices")
async def get_voices():
    return TTSService.get_available_voices()


@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New WebSocket call connection established")
    
    # Session state
    conversation_history = []
    system_prompt = "You are a helpful assistant."
    voice = settings.DEFAULT_VOICE
    llm_service = LLMService()
    tts_service = TTSService()
    
    # Import STT service
    from app.stt import STTService
    stt_service = None
    
    # Audio buffer to accumulate incoming binary WebM audio chunks
    audio_buffer = bytearray()
    
    try:
        while True:
            # Accept both text and binary messages
            websocket_msg = await websocket.receive()
            
            if "text" in websocket_msg:
                message = json.loads(websocket_msg["text"])
                msg_type = message.get("type")
                
                if msg_type == "start_call":
                    system_prompt = message.get("systemPrompt", system_prompt)
                    voice = message.get("voice", voice)
                    provider = message.get("provider") or settings.LLM_PROVIDER
                    model = message.get("model") or settings.LLM_MODEL
                    gemini_key = message.get("geminiKey")
                    groq_key = message.get("groqKey")
                    
                    # Re-initialize LLM Service if client requested custom provider/model/keys
                    api_key = gemini_key if provider == "gemini" else groq_key
                    llm_service = LLMService(
                        provider=provider,
                        model=model,
                        api_key=api_key
                    )
                    
                    # Initialize STT Service using Groq Key if provided, otherwise fallback to settings key
                    stt_service = STTService(api_key=groq_key or settings.GROQ_API_KEY)
                    
                    greeting = message.get("greeting", "Hello! This is Alex calling. How can I help you today?")
                    logger.info(f"Starting call. Greeting: '{greeting}', Voice: {voice}")
                    
                    # Synthesize greeting
                    try:
                        audio_bytes = await tts_service.generate_speech(greeting, voice)
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                        
                        # Update history
                        conversation_history.append({"role": "assistant", "content": greeting})
                        
                        await websocket.send_json({
                            "type": "call_started",
                            "text": greeting,
                            "audio": audio_base64
                        })
                    except Exception as tts_err:
                        logger.error(f"Failed to generate greeting TTS: {tts_err}")
                        await websocket.send_json({
                            "type": "status",
                            "status": "error",
                            "message": f"TTS synthesis error: {str(tts_err)}"
                        })
                
                elif msg_type == "speech_start":
                    logger.info("VAD Speech Start: clearing audio buffer")
                    audio_buffer.clear()
                
                elif msg_type == "speech_end":
                    logger.info(f"VAD Speech End: transcribing accumulated {len(audio_buffer)} bytes")
                    if not audio_buffer:
                        logger.warning("Empty audio buffer. Skipping transcription.")
                        continue
                    
                    # Send thinking status
                    await websocket.send_json({
                        "type": "status",
                        "status": "thinking"
                    })
                    
                    try:
                        # Transcribe WebM using Groq Whisper
                        if not stt_service:
                            stt_service = STTService()
                            
                        transcribed_text = await stt_service.transcribe_audio(bytes(audio_buffer))
                        logger.info(f"Groq Whisper Transcription: '{transcribed_text}'")
                        
                        if not transcribed_text.strip():
                            logger.info("Speech was silent or untranscribable. Returning to listening.")
                            # Send listening status back to frontend
                            await websocket.send_json({
                                "type": "status",
                                "status": "listening"
                            })
                            continue
                        
                        # Send user transcript back to client for UI logging
                        await websocket.send_json({
                            "type": "user_speech_transcript",
                            "text": transcribed_text
                        })
                        
                        # Add user transcript to history
                        conversation_history.append({"role": "user", "content": transcribed_text})
                        
                        # Generate Response
                        response_text = await llm_service.get_response(conversation_history, system_prompt)
                        logger.info(f"Generated LLM Response: '{response_text}'")
                        
                        # Synthesize speech
                        tts_bytes = await tts_service.generate_speech(response_text, voice)
                        tts_base64 = base64.b64encode(tts_bytes).decode("utf-8")
                        
                        # Add agent response to history
                        conversation_history.append({"role": "assistant", "content": response_text})
                        
                        # Return to client
                        await websocket.send_json({
                            "type": "agent_speech",
                            "text": response_text,
                            "audio": tts_base64
                        })
                    except Exception as err:
                        logger.error(f"Error during audio transcription or agent response: {err}")
                        await websocket.send_json({
                            "type": "status",
                            "status": "error",
                            "message": f"Error: {str(err)}"
                        })
                
                elif msg_type == "user_speech":
                    # Text-based fallback (original browser-STT mode)
                    user_text = message.get("text", "")
                    if not user_text.strip():
                        continue
                    
                    logger.info(f"Received User Speech (Text Fallback): '{user_text}'")
                    conversation_history.append({"role": "user", "content": user_text})
                    
                    # Send thinking status
                    await websocket.send_json({
                        "type": "status",
                        "status": "thinking"
                    })
                    
                    try:
                        # Query LLM
                        response_text = await llm_service.get_response(conversation_history, system_prompt)
                        logger.info(f"Generated LLM Response: '{response_text}'")
                        
                        # Synthesize speech
                        audio_bytes = await tts_service.generate_speech(response_text, voice)
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                        
                        conversation_history.append({"role": "assistant", "content": response_text})
                        
                        await websocket.send_json({
                            "type": "agent_speech",
                            "text": response_text,
                            "audio": audio_base64
                        })
                    except Exception as err:
                        logger.error(f"Error generating LLM/TTS response: {err}")
                        await websocket.send_json({
                            "type": "status",
                            "status": "error",
                            "message": f"Error generating response: {str(err)}"
                        })
                
                elif msg_type == "interrupted":
                    logger.info("Agent was interrupted by user speech (barge-in)")
                    if conversation_history and conversation_history[-1]["role"] == "assistant":
                        text_spoken = message.get("text_spoken", "").strip()
                        if text_spoken:
                            conversation_history[-1]["content"] = text_spoken + "..."
                            logger.info(f"Updated assistant history history turn: '{text_spoken}...'")
                        else:
                            conversation_history[-1]["content"] = "..."
                            
                elif msg_type == "hang_up":
                    logger.info("Client hung up call session")
                    await websocket.send_json({
                        "type": "status",
                        "status": "disconnected"
                    })
                    break
            
            elif "bytes" in websocket_msg:
                # Accumulate raw WebM audio bytes from client
                audio_buffer.extend(websocket_msg["bytes"])
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by client")
    except Exception as e:
        logger.error(f"Unhandled WebSocket error: {e}")
    finally:
        logger.info("WebSocket session cleaned up")

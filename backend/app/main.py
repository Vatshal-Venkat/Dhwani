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

app = FastAPI(title="Outbound Voice Agent API")

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
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
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
            
            elif msg_type == "user_speech":
                user_text = message.get("text", "")
                if not user_text.strip():
                    continue
                
                logger.info(f"Received User Speech: '{user_text}'")
                conversation_history.append({"role": "user", "content": user_text})
                
                # Send thinking status
                await websocket.send_json({
                    "type": "status",
                    "status": "thinking"
                })
                
                # 1. Get response from LLM
                response_text = await llm_service.get_response(conversation_history, system_prompt)
                logger.info(f"LLM Response: '{response_text}'")
                
                # Update history
                conversation_history.append({"role": "assistant", "content": response_text})
                
                # 2. Synthesize agent response to TTS
                await websocket.send_json({
                    "type": "status",
                    "status": "speaking"
                })
                
                try:
                    audio_bytes = await tts_service.generate_speech(response_text, voice)
                    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                    
                    # 3. Send text and audio back to frontend
                    await websocket.send_json({
                        "type": "agent_speech",
                        "text": response_text,
                        "audio": audio_base64
                    })
                except Exception as tts_err:
                    logger.error(f"Failed to generate response TTS: {tts_err}")
                    await websocket.send_json({
                        "type": "agent_speech",
                        "text": response_text,
                        "audio": "" # Send text only if TTS fails
                    })
                    
            elif msg_type == "hang_up":
                logger.info("Client hung up call session")
                await websocket.send_json({
                    "type": "status",
                    "status": "disconnected"
                })
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by client")
    except Exception as e:
        logger.error(f"Unhandled WebSocket error: {e}")
    finally:
        logger.info("WebSocket session cleaned up")

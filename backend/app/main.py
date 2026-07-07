import asyncio
import base64
import json
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm import LLMService
from app.tts import TTSService
from app.database import get_db
from app.models import Agent, Call

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

class AgentCreate(BaseModel):
    name: str
    voice_id: str
    temperature: float = 0.7
    system_prompt: str
    greeting: str

class AgentResponse(BaseModel):
    id: int
    name: str
    voice_id: str
    temperature: float
    system_prompt: str
    greeting: str
    created_at: datetime

    class Config:
        from_attributes = True

class CallResponse(BaseModel):
    id: int
    agent_id: Optional[int] = None
    start_time: datetime
    duration: int
    status: str
    transcription_log: Optional[str] = None
    cost: float

    class Config:
        from_attributes = True

@app.get("/api/agents", response_model=List[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    stmt = select(Agent).order_by(Agent.id.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@app.post("/api/agents", response_model=AgentResponse)
async def create_agent(agent_data: AgentCreate, db: AsyncSession = Depends(get_db)):
    db_agent = Agent(**agent_data.model_dump())
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    return db_agent

@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: int, agent_data: AgentCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.name = agent_data.name
    agent.voice_id = agent_data.voice_id
    agent.temperature = agent_data.temperature
    agent.system_prompt = agent_data.system_prompt
    agent.greeting = agent_data.greeting
    
    await db.commit()
    await db.refresh(agent)
    return agent

@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await db.delete(agent)
    await db.commit()
    return {"status": "success", "message": "Agent deleted successfully"}

@app.get("/api/calls", response_model=List[CallResponse])
async def list_calls(db: AsyncSession = Depends(get_db)):
    stmt = select(Call).order_by(Call.id.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@app.get("/api/calls/{call_id}", response_model=CallResponse)
async def get_call(call_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Call).where(Call.id == call_id)
    result = await db.execute(stmt)
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call log not found")
    return call


@app.post("/api/twilio/twiml")
async def twilio_twiml(request: Request, agent_id: Optional[str] = None):
    # Construct dynamic WebSocket URL
    host = request.url.netloc
    scheme = "wss" if request.url.scheme == "https" else "ws"
    
    form_data = await request.form()
    selected_agent_id = agent_id or form_data.get("agent_id") or ""
    
    ws_url = f"{scheme}://{host}/ws/twilio"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="agent_id" value="{selected_agent_id}" />
        </Stream>
    </Connect>
</Response>
"""
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws/twilio")
async def websocket_twilio_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New Twilio WebSocket connection established")
    
    import miniaudio
    from app.twilio_utils import pcm_to_mulaw, mulaw_to_pcm, pcm_to_wav, EnergyVAD
    
    # Session state
    start_time = datetime.now()
    agent_id = None
    stream_sid = None
    call_sid = None
    
    conversation_history = []
    system_prompt = "You are a helpful assistant."
    voice = settings.DEFAULT_VOICE
    greeting = "Hello! How can I help you today?"
    
    llm_service = LLMService()
    tts_service = TTSService()
    
    # Import STT service
    from app.stt import STTService
    stt_service = None
    
    # VAD
    vad = EnergyVAD()
    
    # Audio buffer to accumulate incoming binary audio chunks (PCMU)
    audio_buffer = bytearray()
    
    # Track the active playback task to support interruption
    playback_task = None

    async def stream_audio_to_twilio(mulaw_bytes: bytes):
        nonlocal stream_sid
        if not stream_sid:
            return
        
        # 160 bytes of 8kHz mu-law audio = 20ms chunk
        chunk_size = 160
        for i in range(0, len(mulaw_bytes), chunk_size):
            chunk = mulaw_bytes[i:i+chunk_size]
            payload = base64.b64encode(chunk).decode("utf-8")
            try:
                await websocket.send_json({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": payload
                    }
                })
            except Exception as send_err:
                logger.error(f"Error sending audio chunk to Twilio: {send_err}")
                break
            await asyncio.sleep(0.02)

    try:
        while True:
            websocket_msg = await websocket.receive()
            
            if "text" in websocket_msg:
                message = json.loads(websocket_msg["text"])
                event = message.get("event")
                
                if event == "connected":
                    logger.info("Twilio: Connection message received")
                
                elif event == "start":
                    stream_sid = message.get("streamSid")
                    start_data = message.get("start", {})
                    call_sid = start_data.get("callSid")
                    logger.info(f"Twilio: Stream started. streamSid={stream_sid}, callSid={call_sid}")
                    
                    # Parse custom parameters
                    custom_params = start_data.get("customParameters", {})
                    raw_agent_id = custom_params.get("agent_id") or custom_params.get("agentId")
                    try:
                        agent_id = int(raw_agent_id) if raw_agent_id is not None else None
                    except ValueError:
                        agent_id = None
                    
                    # Load agent config from db if agent_id is provided
                    if agent_id is not None:
                        try:
                            from app.database import AsyncSessionLocal
                            async with AsyncSessionLocal() as session:
                                stmt = select(Agent).where(Agent.id == agent_id)
                                result = await session.execute(stmt)
                                db_agent = result.scalar_one_or_none()
                                if db_agent:
                                    system_prompt = db_agent.system_prompt
                                    greeting = db_agent.greeting
                                    voice = db_agent.voice_id
                                    logger.info(f"Loaded database Agent ID={agent_id}: Name='{db_agent.name}', Voice={voice}")
                        except Exception as db_err:
                            logger.error(f"Failed to retrieve agent configuration from DB: {db_err}")
                    
                    # Initialize LLM and STT using default environment keys
                    llm_service = LLMService(provider=settings.LLM_PROVIDER, model=settings.LLM_MODEL)
                    stt_service = STTService()
                    
                    # Speak greeting
                    logger.info(f"Twilio Outbound greeting: '{greeting}', Voice: {voice}")
                    try:
                        conversation_history.append({"role": "assistant", "content": greeting})
                        
                        # Generate TTS
                        audio_mp3 = await tts_service.generate_speech(greeting, voice)
                        
                        # Decode and downsample to 8kHz SIGNED16
                        decoded = miniaudio.decode(
                            audio_mp3,
                            output_format=miniaudio.SampleFormat.SIGNED16,
                            nchannels=1,
                            sample_rate=8000
                        )
                        mulaw_bytes = pcm_to_mulaw(decoded.samples.tobytes())
                        
                        # Stream greeting back
                        playback_task = asyncio.create_task(stream_audio_to_twilio(mulaw_bytes))
                    except Exception as tts_err:
                        logger.error(f"Failed to generate Twilio greeting TTS: {tts_err}")
                
                elif event == "media":
                    # Inbound media containing user speech
                    media_data = message.get("media", {})
                    track = media_data.get("track")
                    if track == "inbound":
                        payload = media_data.get("payload")
                        if not payload:
                            continue
                            
                        pcm_chunk = base64.b64decode(payload)
                        
                        # Pass PCMU bytes through VAD
                        vad_res = vad.process_chunk(pcm_chunk)
                        
                        if vad_res["speech_start_detected"]:
                            # Interrupt agent if they are currently speaking
                            if playback_task and not playback_task.done():
                                playback_task.cancel()
                                logger.info("Twilio VAD: Interrupted agent playback due to user barge-in")
                                try:
                                    await websocket.send_json({
                                        "event": "clear",
                                        "streamSid": stream_sid
                                    })
                                except Exception:
                                    pass
                                if conversation_history and conversation_history[-1]["role"] == "assistant":
                                    conversation_history[-1]["content"] += "..."
                            
                            audio_buffer.clear()
                            
                        if vad.is_speaking:
                            audio_buffer.extend(pcm_chunk)
                            
                        if vad_res["speech_end_detected"]:
                            if not audio_buffer:
                                logger.warning("Twilio VAD: Empty speech end buffer")
                                continue
                            
                            # End of user speech - Transcribe!
                            try:
                                # Convert accumulated PCMU to PCM then WAV
                                pcm_bytes = mulaw_to_pcm(bytes(audio_buffer))
                                wav_bytes = pcm_to_wav(pcm_bytes, sample_rate=8000, num_channels=1)
                                audio_buffer.clear()
                                
                                # Transcribe
                                if not stt_service:
                                    stt_service = STTService()
                                transcribed_text = await stt_service.transcribe_audio(wav_bytes, filename="speech.wav")
                                logger.info(f"Twilio Whisper STT: '{transcribed_text}'")
                                
                                if not transcribed_text.strip():
                                    continue
                                    
                                conversation_history.append({"role": "user", "content": transcribed_text})
                                
                                # Query LLM
                                response_text = await llm_service.get_response(conversation_history, system_prompt)
                                logger.info(f"Twilio Generated LLM: '{response_text}'")
                                
                                # Generate TTS
                                audio_mp3 = await tts_service.generate_speech(response_text, voice)
                                decoded = miniaudio.decode(
                                    audio_mp3,
                                    output_format=miniaudio.SampleFormat.SIGNED16,
                                    nchannels=1,
                                    sample_rate=8000
                                )
                                mulaw_bytes = pcm_to_mulaw(decoded.samples.tobytes())
                                
                                conversation_history.append({"role": "assistant", "content": response_text})
                                
                                # Play response
                                if playback_task and not playback_task.done():
                                    playback_task.cancel()
                                playback_task = asyncio.create_task(stream_audio_to_twilio(mulaw_bytes))
                                
                            except Exception as err:
                                logger.error(f"Twilio error in STT/LLM/TTS processing: {err}")
                
                elif event == "stop":
                    logger.info("Twilio: Stop message received, closing call session")
                    break
                    
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket connection disconnected")
    except Exception as e:
        logger.error(f"Unhandled Twilio WebSocket error: {e}")
    finally:
        # Cancel active playback task
        if playback_task and not playback_task.done():
            playback_task.cancel()
            
        logger.info("Twilio WebSocket session cleaned up")
        
        # Save call log to database
        if conversation_history:
            duration = int((datetime.now() - start_time).total_seconds())
            try:
                from app.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    db_call = Call(
                        agent_id=agent_id,
                        duration=duration,
                        status="completed",
                        transcription_log=json.dumps(conversation_history),
                        cost=0.0
                    )
                    session.add(db_call)
                    await session.commit()
                    logger.info("Twilio Call successfully logged to database.")
            except Exception as db_err:
                logger.error(f"Failed to log Twilio call to database: {db_err}")


@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New WebSocket call connection established")
    
    # Session state
    start_time = datetime.now()
    agent_id = None
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
                    
                    # Parse agent ID if provided
                    raw_agent_id = message.get("agentId") or message.get("agent_id")
                    try:
                        agent_id = int(raw_agent_id) if raw_agent_id is not None else None
                    except ValueError:
                        agent_id = None
                    
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
                        # Transcribe WAV using Groq Whisper
                        if not stt_service:
                            stt_service = STTService()
                            
                        transcribed_text = await stt_service.transcribe_audio(bytes(audio_buffer), filename="speech.wav")
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
        if conversation_history:
            duration = int((datetime.now() - start_time).total_seconds())
            try:
                from app.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    db_call = Call(
                        agent_id=agent_id,
                        duration=duration,
                        status="completed",
                        transcription_log=json.dumps(conversation_history),
                        cost=0.0
                    )
                    session.add(db_call)
                    await session.commit()
                    logger.info("Call successfully logged to database.")
            except Exception as db_err:
                logger.error(f"Failed to log call to database: {db_err}")

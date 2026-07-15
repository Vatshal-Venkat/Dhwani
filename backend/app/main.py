import asyncio
import base64
import json
import logging
from typing import Any, List, Optional
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
from app.models import Agent, Call, APIKey

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
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174"
    ],
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
async def get_config(db: AsyncSession = Depends(get_db)):
    # Check env or database for gemini key
    has_gemini = bool(settings.GEMINI_API_KEY)
    if not has_gemini:
        stmt = select(APIKey).where(APIKey.provider == "gemini")
        res = await db.execute(stmt)
        has_gemini = res.scalar_one_or_none() is not None

    # Check env or database for groq key
    has_groq = bool(settings.GROQ_API_KEY)
    if not has_groq:
        stmt = select(APIKey).where(APIKey.provider == "groq")
        res = await db.execute(stmt)
        has_groq = res.scalar_one_or_none() is not None

    return {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "voice": settings.DEFAULT_VOICE,
        "has_gemini_key": has_gemini,
        "has_groq_key": has_groq
    }

class APIKeySave(BaseModel):
    provider: str
    api_key: str

@app.post("/api/keys")
async def save_api_key(data: APIKeySave, db: AsyncSession = Depends(get_db)):
    if data.provider not in ("gemini", "groq"):
        raise HTTPException(status_code=400, detail="Invalid provider. Must be 'gemini' or 'groq'.")
    if not data.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key cannot be empty.")

    from app.security import encrypt_key
    encrypted = encrypt_key(data.api_key.strip())

    stmt = select(APIKey).where(APIKey.provider == data.provider)
    result = await db.execute(stmt)
    db_key = result.scalar_one_or_none()

    if db_key:
        db_key.encrypted_key = encrypted
    else:
        db_key = APIKey(provider=data.provider, encrypted_key=encrypted)
        db.add(db_key)

    await db.commit()
    return {"status": "success", "message": f"API Key for {data.provider} saved successfully."}

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
    summary: Optional[str] = None
    disposition: Optional[str] = None
    structured_outcome: Optional[str] = None

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


@app.get("/api/calls/stats")
async def get_calls_stats(db: AsyncSession = Depends(get_db)):
    stmt = select(Call)
    result = await db.execute(stmt)
    calls = result.scalars().all()
    
    total_calls = len(calls)
    total_cost = sum(c.cost for c in calls if c.cost)
    avg_duration = sum(c.duration for c in calls if c.duration) / total_calls if total_calls > 0 else 0.0
    
    disposition_breakdown = {}
    interest_level_breakdown = {"High": 0, "Medium": 0, "Low": 0, "None": 0}
    
    for c in calls:
        disp = c.disposition or "Unclassified"
        disposition_breakdown[disp] = disposition_breakdown.get(disp, 0) + 1
        
        if c.structured_outcome:
            try:
                outcome = json.loads(c.structured_outcome)
                interest = outcome.get("interest_level")
                if interest in interest_level_breakdown:
                    interest_level_breakdown[interest] += 1
            except Exception:
                pass
                
    return {
        "total_calls": total_calls,
        "total_cost": round(total_cost, 5),
        "average_duration_seconds": round(avg_duration, 2),
        "disposition_breakdown": disposition_breakdown,
        "interest_level_breakdown": interest_level_breakdown
    }


class CallTriggerRequest(BaseModel):
    phone_number: str
    agent_id: Optional[int] = None
    public_url: str

@app.post("/api/calls/trigger")
async def trigger_call(req: CallTriggerRequest):
    # Ensure Twilio configurations are set
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_FROM_NUMBER:
        raise HTTPException(
            status_code=400,
            detail="Twilio credentials are not configured in settings or .env file."
        )

    # Clean target phone number
    to_number = req.phone_number.strip()
    if not to_number.startswith("+"):
        to_number = "+" + to_number

    # Construct the twiml URL callback
    agent_param = f"?agent_id={req.agent_id}" if req.agent_id else ""
    twiml_url = f"{req.public_url.rstrip('/')}/api/twilio/twiml{agent_param}"

    # Call Twilio REST API to place outbound call using urllib
    import urllib.request
    import urllib.parse
    import base64
    import json
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls.json"
    
    data = {
        "To": to_number,
        "From": settings.TWILIO_FROM_NUMBER,
        "Url": twiml_url,
        "MachineDetection": "Enable",  # Enabled Twilio Answering Machine Detection (AMD)
        "MachineDetectionTimeout": "30"
    }
    
    encoded_data = urllib.parse.urlencode(data).encode("utf-8")
    
    auth_str = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
    auth_header = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    req_obj = urllib.request.Request(
        url,
        data=encoded_data,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )
    
    try:
        loop = asyncio.get_running_loop()
        def send_request():
            with urllib.request.urlopen(req_obj) as response:
                return response.read(), response.status
                
        res_body, res_status = await loop.run_in_executor(None, send_request)
        res_json = json.loads(res_body.decode("utf-8"))
        
        call_sid = res_json.get("sid")
        status = res_json.get("status")
        
        logger.info(f"Successfully triggered Twilio call. Sid: {call_sid}, Status: {status}")
        return {
            "status": "success",
            "message": "Call initiated successfully",
            "call_sid": call_sid,
            "twilio_status": status
        }
        
    except urllib.error.HTTPError as http_err:
        err_body = http_err.read().decode("utf-8")
        logger.error(f"Twilio API request failed: {http_err.code} - {err_body}")
        raise HTTPException(
            status_code=500,
            detail=f"Twilio API error: {http_err.code} - {err_body}"
        )
    except Exception as e:
        logger.error(f"Error triggering call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/twilio/twiml")
async def twilio_twiml(request: Request, agent_id: Optional[str] = None):
    # Construct dynamic WebSocket URL
    host = request.url.netloc
    scheme = "wss" if request.url.scheme == "https" else "ws"
    
    form_data = await request.form()
    selected_agent_id = agent_id or form_data.get("agent_id") or ""
    answered_by = form_data.get("AnsweredBy")
    
    logger.info(f"Twilio twiml callback. AnsweredBy: {answered_by}, agent_id: {selected_agent_id}")
    
    # Check if answered by an answering machine/voicemail
    is_machine = answered_by in ["machine_start", "machine_end_beep", "machine_end_silence"]
    
    if is_machine:
        # Log the call to database as "voicemail"
        try:
            from app.database import AsyncSessionLocal
            from app.models import Call
            import json
            async with AsyncSessionLocal() as session:
                db_call = Call(
                    agent_id=int(selected_agent_id) if selected_agent_id.isdigit() else None,
                    duration=0,
                    status="completed",
                    transcription_log=json.dumps([{"role": "system", "content": "Voicemail detected - played automated message"}]),
                    cost=0.0,
                    summary="Voicemail detected - played automated message.",
                    disposition="Voicemail Detected",
                    structured_outcome=json.dumps({"interest_level": "None", "follow_up_needed": True, "key_points": ["Voicemail detected"]})
                )
                session.add(db_call)
                await session.commit()
                logger.info(f"Voicemail call successfully logged to database (ID: {db_call.id}).")
        except Exception as db_err:
            logger.error(f"Failed to log voicemail call: {db_err}")
            
        # Return TwiML response to play a message and hang up
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello, this is an automated message from SmartHome Solutions. We reached your voicemail. We will call back later. Goodbye.</Say>
    <Hangup />
</Response>
"""
        return Response(content=twiml, media_type="application/xml")
        
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
    
    # Initialize Deepgram real-time STT
    from app.streaming_stt import DeepgramLiveSTT
    deepgram_stt = None
    try:
        deepgram_stt = DeepgramLiveSTT(sample_rate=8000, encoding="mulaw")
        await deepgram_stt.connect()
    except Exception as dg_err:
        logger.warning(f"Could not connect to Deepgram Live STT, falling back to Groq Whisper: {dg_err}")
        deepgram_stt = None
    
    # VAD
    vad = EnergyVAD()
    
    # Audio buffer to accumulate incoming binary audio chunks (PCMU)
    audio_buffer = bytearray()
    
    # Queue and tasks for LLM-TTS streaming
    playback_queue = asyncio.Queue()
    llm_tts_task: Optional[asyncio.Task[Any]] = None
    playback_worker_task: Optional[asyncio.Task[Any]] = None
    turn_monitor_task: Optional[asyncio.Task[Any]] = None
    
    # Stats for current turn interruption tracking
    current_turn_sentences_played = []
    current_playing_sentence = None
    current_playing_start_time = None

    # Track overall session cost
    total_call_cost = 0.0
    missed_text = ""

    def estimate_turn_cost(input_text: str, output_text: str, audio_duration_seconds: float) -> float:
        stt_cost = audio_duration_seconds * 0.00005  # $0.003 / min = $0.00005 / sec
        input_tokens = len(input_text) / 4
        output_tokens = len(output_text) / 4
        
        if settings.LLM_PROVIDER == "gemini":
            llm_cost = (input_tokens * 0.000000075) + (output_tokens * 0.00000030)
        elif settings.LLM_PROVIDER == "groq":
            llm_cost = (input_tokens * 0.00000005) + (output_tokens * 0.00000008)
        else:
            llm_cost = 0.0
        return stt_cost + llm_cost

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

    async def llm_tts_streamer(history, system_prompt, voice):
        try:
            # We stream sentences
            async for sentence in llm_service.get_response_stream(history, system_prompt):
                if not sentence.strip():
                    continue
                logger.info(f"Twilio LLM sentence generated: '{sentence}'")
                try:
                    # Generate speech
                    audio_mp3 = await tts_service.generate_speech(sentence, voice)
                    decoded = miniaudio.decode(
                        audio_mp3,
                        output_format=miniaudio.SampleFormat.SIGNED16,
                        nchannels=1,
                        sample_rate=8000
                    )
                    mulaw_bytes = pcm_to_mulaw(decoded.samples.tobytes())
                    await playback_queue.put((sentence, mulaw_bytes))
                except Exception as tts_err:
                    logger.error(f"Failed to generate TTS for sentence '{sentence}': {tts_err}")
        except asyncio.CancelledError:
            logger.info("llm_tts_streamer cancelled.")
            raise
        except Exception as e:
            logger.error(f"Error in llm_tts_streamer: {e}")
        finally:
            await playback_queue.put((None, None))  # Sentinel

    async def playback_worker():
        nonlocal current_playing_sentence, current_playing_start_time
        try:
            while True:
                item = await playback_queue.get()
                sentence, mulaw_bytes = item
                if sentence is None:
                    break
                
                logger.info(f"Twilio starting playback of sentence: '{sentence}'")
                current_playing_sentence = sentence
                current_playing_start_time = asyncio.get_event_loop().time()
                
                await stream_audio_to_twilio(mulaw_bytes)
                
                current_turn_sentences_played.append(sentence)
                current_playing_sentence = None
                current_playing_start_time = None
        except asyncio.CancelledError:
            logger.info("playback_worker cancelled.")
            raise

    async def handle_interruption():
        nonlocal llm_tts_task, playback_worker_task, current_playing_sentence, current_playing_start_time, total_call_cost, missed_text
        
        # 1. Collect all unspoken text from the queue
        unspoken_sentences = []
        while not playback_queue.empty():
            try:
                item = playback_queue.get_nowait()
                sentence, _ = item
                if sentence:
                    unspoken_sentences.append(sentence)
            except asyncio.QueueEmpty:
                break
                
        # 2. Cancel running tasks
        if llm_tts_task and not llm_tts_task.done():
            llm_tts_task.cancel()
        if playback_worker_task and not playback_worker_task.done():
            playback_worker_task.cancel()
            
        # 3. Twilio buffer clear
        try:
            await websocket.send_json({
                "event": "clear",
                "streamSid": stream_sid
            })
        except Exception:
            pass
            
        # 4. Estimate words spoken in the interrupted sentence and what was missed
        interrupted_words = ""
        missed_current = ""
        if current_playing_sentence and current_playing_start_time:
            elapsed = asyncio.get_event_loop().time() - current_playing_start_time
            words_spoken_count = int(elapsed * 2.5) # 150 words/min = 2.5 words/sec
            words = current_playing_sentence.split()
            if words_spoken_count > 0:
                interrupted_words = " ".join(words[:words_spoken_count])
            if words_spoken_count < len(words):
                missed_current = " ".join(words[words_spoken_count:])
            logger.info(f"Barge-in: Interrupted sentence '{current_playing_sentence}' after {elapsed:.2f}s (~{words_spoken_count} words: '{interrupted_words}')")
            
        # 5. Construct truncated response and missed text
        spoken_parts = list(current_turn_sentences_played)
        if interrupted_words:
            spoken_parts.append(interrupted_words + "...")
        elif spoken_parts:
            spoken_parts[-1] = spoken_parts[-1] + "..."
        else:
            spoken_parts.append("...")
            
        truncated_response = " ".join(spoken_parts)
        
        missed_parts = []
        if missed_current:
            missed_parts.append(missed_current)
        missed_parts.extend(unspoken_sentences)
        missed_text = " ".join(missed_parts).strip()
        if missed_text:
            logger.info(f"Twilio Interruption: User missed listening to: '{missed_text}'")
        
        # Calculate cost for this turn (using truncated text as output)
        last_user_msg = conversation_history[-1]["content"] if conversation_history else ""
        turn_cost = estimate_turn_cost(last_user_msg, truncated_response, 0.0)
        total_call_cost += turn_cost
        
        conversation_history.append({
            "role": "assistant", 
            "content": truncated_response,
            "cost": turn_cost
        })
        logger.info(f"Interrupted. Added truncated response: '{truncated_response}' (cost: ${turn_cost:.6f})")
        
        # Clear stats
        current_playing_sentence = None
        current_playing_start_time = None
        current_turn_sentences_played.clear()
        
        # Drain the queue
        while not playback_queue.empty():
            try:
                playback_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

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
                        # Generate TTS for greeting
                        audio_mp3 = await tts_service.generate_speech(greeting, voice)
                        decoded = miniaudio.decode(
                            audio_mp3,
                            output_format=miniaudio.SampleFormat.SIGNED16,
                            nchannels=1,
                            sample_rate=8000
                        )
                        mulaw_bytes = pcm_to_mulaw(decoded.samples.tobytes())
                        
                        # Put greeting audio in queue and sentinel
                        await playback_queue.put((greeting, mulaw_bytes))
                        await playback_queue.put((None, None))
                        
                        current_turn_sentences_played.clear()
                        current_playing_sentence = None
                        current_playing_start_time = None
                        
                        playback_worker_task = asyncio.create_task(playback_worker())
                        
                        async def monitor_greeting():
                            nonlocal total_call_cost
                            try:
                                if playback_worker_task is not None:
                                    await playback_worker_task
                                # Calculate greeting cost
                                greet_cost = estimate_turn_cost("", greeting, 0.0)
                                total_call_cost += greet_cost
                                conversation_history.append({
                                    "role": "assistant", 
                                    "content": greeting,
                                    "cost": greet_cost
                                })
                                logger.info(f"Greeting completed. (cost: ${greet_cost:.6f})")
                            except asyncio.CancelledError:
                                pass
                        turn_monitor_task = asyncio.create_task(monitor_greeting())
                        
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
                        
                        # Stream live audio chunk to Deepgram STT
                        if deepgram_stt:
                            await deepgram_stt.send_audio(pcm_chunk)
                        
                        # Pass PCMU bytes through VAD
                        vad_res = vad.process_chunk(pcm_chunk)
                        
                        if vad_res["speech_start_detected"]:
                            # Interrupt agent if they are currently speaking
                            is_agent_speaking = (playback_worker_task and not playback_worker_task.done()) or (llm_tts_task and not llm_tts_task.done())
                            if is_agent_speaking:
                                if turn_monitor_task and not turn_monitor_task.done():
                                    turn_monitor_task.cancel()
                                await handle_interruption()
                                logger.info("Twilio VAD: Interrupted agent playback due to user barge-in")
                            
                            audio_buffer.clear()
                            
                            # Clear Deepgram transcript for the new turn
                            if deepgram_stt:
                                deepgram_stt.clear_transcript()
                            
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
                                
                                # Track audio duration for cost calculation
                                user_audio_duration = len(audio_buffer) / 8000.0
                                audio_buffer.clear()
                                
                                transcribed_text = ""
                                stt_start = asyncio.get_event_loop().time()
                                
                                # Attempt to retrieve real-time transcript from Deepgram
                                if deepgram_stt:
                                    await asyncio.sleep(0.2) # Allow last audio packet processing
                                    transcribed_text = deepgram_stt.get_transcript()
                                    stt_latency = asyncio.get_event_loop().time() - stt_start
                                    logger.info(f"Twilio Deepgram STT: '{transcribed_text}' (took {stt_latency:.2f}s latency)")
                                    
                                # Fallback to Groq Whisper if Deepgram is not active or returned empty text
                                if not transcribed_text.strip():
                                    if not stt_service:
                                        stt_service = STTService()
                                    transcribed_text = await stt_service.transcribe_audio(wav_bytes, filename="speech.wav")
                                    stt_latency = asyncio.get_event_loop().time() - stt_start
                                    logger.info(f"Twilio Whisper STT Fallback: '{transcribed_text}' (took {stt_latency:.2f}s)")
                                
                                if not transcribed_text.strip():
                                    continue
                                    
                                conversation_history.append({
                                    "role": "user", 
                                    "content": transcribed_text,
                                    "metrics": {"stt_latency": round(stt_latency, 3)}
                                })
                                
                                # Clear queue and previous stats
                                current_turn_sentences_played.clear()
                                current_playing_sentence = None
                                current_playing_start_time = None
                                
                                # Drain queue
                                while not playback_queue.empty():
                                    try:
                                        playback_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                
                                # Inject missed text context into system prompt
                                dynamic_system_prompt = system_prompt
                                if missed_text:
                                    dynamic_system_prompt += (
                                        f"\n\n[SYSTEM DIRECTIVE: During the previous turn, the user interrupted you. "
                                        f"You MUST weave the following unspoken information naturally into your next response: '{missed_text}']"
                                    )
                                    logger.info(f"Injected Twilio missed text directive: '{missed_text}'")
                                    missed_text = ""  # Clear after injecting
                                    
                                # Start streamer and player tasks
                                llm_tts_task = asyncio.create_task(llm_tts_streamer(conversation_history, dynamic_system_prompt, voice))
                                playback_worker_task = asyncio.create_task(playback_worker())
                                
                                # Monitor the completion of the assistant turn
                                async def monitor_assistant_turn(stt_dur):
                                    nonlocal total_call_cost
                                    try:
                                        tasks = [t for t in (llm_tts_task, playback_worker_task) if t is not None]
                                        if tasks:
                                            await asyncio.gather(*tasks)
                                        # Complete successfully
                                        full_response = " ".join(current_turn_sentences_played)
                                        
                                        # Calculate cost
                                        turn_cost = estimate_turn_cost(transcribed_text, full_response, stt_dur)
                                        total_call_cost += turn_cost
                                        
                                        conversation_history.append({
                                            "role": "assistant", 
                                            "content": full_response,
                                            "cost": turn_cost
                                        })
                                        logger.info(f"Assistant turn completed. Response: '{full_response}' (cost: ${turn_cost:.6f})")
                                    except asyncio.CancelledError:
                                        pass
                                    except Exception as e:
                                        logger.error(f"Error in monitor_assistant_turn: {e}")
                                
                                turn_monitor_task = asyncio.create_task(monitor_assistant_turn(user_audio_duration))
                                
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
        # Cancel tasks
        if llm_tts_task and not llm_tts_task.done():
            llm_tts_task.cancel()
        if playback_worker_task and not playback_worker_task.done():
            playback_worker_task.cancel()
        if turn_monitor_task and not turn_monitor_task.done():
            turn_monitor_task.cancel()
            
        # Clean up Deepgram connection
        if deepgram_stt:
            await deepgram_stt.close()
            
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
                        cost=round(total_call_cost, 5)
                    )
                    session.add(db_call)
                    await session.commit()
                    logger.info(f"Twilio Call successfully logged to database (ID: {db_call.id}). Cost: ${total_call_cost:.5f}")
                    
                    # Trigger post-call analysis in the background
                    from app.analytics import summarize_and_update_call
                    asyncio.create_task(summarize_and_update_call(db_call.id, db_call.transcription_log))
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
    
    # Streaming tasks
    llm_tts_task: Optional[asyncio.Task[Any]] = None
    turn_monitor_task: Optional[asyncio.Task[Any]] = None
    
    # Current turn tracking
    current_turn_sentences_generated = []
    
    # Cost tracking
    total_call_cost = 0.0
    missed_text = ""
    
    def estimate_turn_cost(input_text: str, output_text: str, audio_duration_seconds: float) -> float:
        stt_cost = audio_duration_seconds * 0.00005  # $0.003 / min
        input_tokens = len(input_text) / 4
        output_tokens = len(output_text) / 4
        
        prov = llm_service.provider if llm_service else settings.LLM_PROVIDER
        if prov == "gemini":
            llm_cost = (input_tokens * 0.000000075) + (output_tokens * 0.00000030)
        elif prov == "groq":
            llm_cost = (input_tokens * 0.00000005) + (output_tokens * 0.00000008)
        else:
            llm_cost = 0.0
        return stt_cost + llm_cost

    async def cancel_tasks():
        nonlocal llm_tts_task, turn_monitor_task
        if llm_tts_task and not llm_tts_task.done():
            llm_tts_task.cancel()
        if turn_monitor_task and not turn_monitor_task.done():
            turn_monitor_task.cancel()

    async def llm_tts_streamer_call(history, system_prompt, voice):
        try:
            async for sentence in llm_service.get_response_stream(history, system_prompt):
                if not sentence.strip():
                    continue
                logger.info(f"Browser LLM sentence generated: '{sentence}'")
                try:
                    # Generate speech
                    audio_bytes = await tts_service.generate_speech(sentence, voice)
                    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                    
                    current_turn_sentences_generated.append(sentence)
                    
                    # Immediately send to browser
                    await websocket.send_json({
                        "type": "agent_speech",
                        "text": sentence,
                        "audio": audio_base64
                    })
                except Exception as tts_err:
                    logger.error(f"Failed browser TTS for sentence '{sentence}': {tts_err}")
        except asyncio.CancelledError:
            logger.info("Browser llm_tts_streamer_call cancelled.")
            raise
        except Exception as e:
            logger.error(f"Error in browser llm_tts_streamer_call: {e}")

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
                        
                        # Calculate greeting cost
                        greet_cost = estimate_turn_cost("", greeting, 0.0)
                        total_call_cost += greet_cost
                        
                        # Update history
                        conversation_history.append({
                            "role": "assistant", 
                            "content": greeting,
                            "cost": greet_cost
                        })
                        
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
                            
                        user_audio_duration = len(audio_buffer) / 16000.0  # WebM raw capture is 16kHz float converted to WAV PCM
                        
                        stt_start = asyncio.get_event_loop().time()
                        transcribed_text = await stt_service.transcribe_audio(bytes(audio_buffer), filename="speech.wav")
                        stt_latency = asyncio.get_event_loop().time() - stt_start
                        logger.info(f"Groq Whisper Transcription: '{transcribed_text}' (took {stt_latency:.2f}s)")
                        
                        audio_buffer.clear()
                        
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
                        conversation_history.append({
                            "role": "user", 
                            "content": transcribed_text,
                            "metrics": {"stt_latency": round(stt_latency, 3)}
                        })
                        
                        # Clear previous turn stats
                        current_turn_sentences_generated.clear()
                        await cancel_tasks()
                        
                        # Inject missed text if any
                        dynamic_system_prompt = system_prompt
                        if missed_text:
                            dynamic_system_prompt += (
                                f"\n\n[SYSTEM DIRECTIVE: During the previous turn, the user interrupted you. "
                                f"You MUST weave the following unspoken information naturally into your next response: '{missed_text}']"
                            )
                            logger.info(f"Browser injected missed text directive: '{missed_text}'")
                            missed_text = ""
                        
                        # Start streamer and player monitor
                        llm_tts_task = asyncio.create_task(llm_tts_streamer_call(conversation_history, dynamic_system_prompt, voice))
                        
                        async def monitor_assistant_turn_call(stt_dur, user_speech_text):
                            nonlocal total_call_cost
                            try:
                                if llm_tts_task is not None:
                                    await llm_tts_task
                                full_response = " ".join(current_turn_sentences_generated)
                                
                                # Calculate cost
                                turn_cost = estimate_turn_cost(user_speech_text, full_response, stt_dur)
                                total_call_cost += turn_cost
                                
                                conversation_history.append({
                                    "role": "assistant", 
                                    "content": full_response,
                                    "cost": turn_cost
                                })
                                logger.info(f"Browser call turn completed. Response: '{full_response}' (cost: ${turn_cost:.6f})")
                                
                                # Return status to client
                                await websocket.send_json({
                                    "type": "status",
                                    "status": "listening"
                                })
                            except asyncio.CancelledError:
                                try:
                                    await websocket.send_json({
                                        "type": "status",
                                        "status": "listening"
                                    })
                                except Exception as e:
                                    logger.error(f"Failed to reset client status on cancel: {e}")
                                raise
                            except Exception as e:
                                logger.error(f"Error in monitor_assistant_turn_call: {e}")
                                
                        turn_monitor_task = asyncio.create_task(monitor_assistant_turn_call(user_audio_duration, transcribed_text))
                        
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
                        # Inject missed text if any
                        dynamic_system_prompt = system_prompt
                        if missed_text:
                            dynamic_system_prompt += (
                                f"\n\n[SYSTEM DIRECTIVE: During the previous turn, the user interrupted you. "
                                f"You MUST weave the following unspoken information naturally into your next response: '{missed_text}']"
                            )
                            logger.info(f"Browser injected missed text directive (text fallback): '{missed_text}'")
                            missed_text = ""

                        # Query LLM
                        response_text = await llm_service.get_response(conversation_history, dynamic_system_prompt)
                        logger.info(f"Generated LLM Response: '{response_text}'")
                        
                        # Synthesize speech
                        audio_bytes = await tts_service.generate_speech(response_text, voice)
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                        
                        # Calculate cost
                        turn_cost = estimate_turn_cost(user_text, response_text, 0.0)
                        total_call_cost += turn_cost
                        
                        conversation_history.append({
                            "role": "assistant", 
                            "content": response_text,
                            "cost": turn_cost
                        })
                        
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
                    await cancel_tasks()
                    
                    text_spoken = message.get("text_spoken", "").strip()
                    
                    # 1. Determine missed text by subtracting spoken text from full generated response
                    full_response = " ".join(current_turn_sentences_generated)
                    clean_spoken = text_spoken.rstrip(".")
                    idx = full_response.lower().find(clean_spoken.lower())
                    if idx != -1:
                        missed_text = full_response[idx + len(clean_spoken):].strip()
                    else:
                        missed_text = current_turn_sentences_generated[-1] if current_turn_sentences_generated else ""
                        
                    if missed_text:
                        logger.info(f"Browser Barge-in: User missed listening to: '{missed_text}'")
                    
                    spoken_parts = []
                    if len(current_turn_sentences_generated) > 1:
                        # Append all but the last sentence (which was interrupted)
                        spoken_parts.extend(current_turn_sentences_generated[:-1])
                        
                    if text_spoken:
                        spoken_parts.append(text_spoken + "...")
                    elif spoken_parts:
                        spoken_parts[-1] = spoken_parts[-1] + "..."
                    else:
                        spoken_parts.append("...")
                        
                    truncated_response = " ".join(spoken_parts)
                    
                    # Calculate cost
                    last_user_msg = conversation_history[-1]["content"] if conversation_history else ""
                    turn_cost = estimate_turn_cost(last_user_msg, truncated_response, 0.0)
                    total_call_cost += turn_cost
                    
                    conversation_history.append({
                        "role": "assistant", 
                        "content": truncated_response,
                        "cost": turn_cost
                    })
                    logger.info(f"Browser interrupted. Added truncated response: '{truncated_response}' (cost: ${turn_cost:.6f})")
                            
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
        # Cancel active tasks
        await cancel_tasks()
        
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
                        cost=round(total_call_cost, 5)
                    )
                    session.add(db_call)
                    await session.commit()
                    logger.info(f"Call successfully logged to database (ID: {db_call.id}). Cost: ${total_call_cost:.5f}")
                    
                    # Trigger post-call analysis in the background
                    from app.analytics import summarize_and_update_call
                    asyncio.create_task(summarize_and_update_call(db_call.id, db_call.transcription_log))
            except Exception as db_err:
                logger.error(f"Failed to log call to database: {db_err}")

import asyncio
import json
import logging
import aiohttp
from app.config import settings

logger = logging.getLogger("voice-agent")

class DeepgramLiveSTT:
    """
    Manages a live WebSocket connection to Deepgram's real-time streaming STT service.
    Streams raw audio frames dynamically and compiles transcription text with virtually zero latency.
    """
    def __init__(self, sample_rate: int = 16000, encoding: str = "linear16", api_key: str = None, language: str = "en"):
        self.sample_rate = sample_rate
        self.encoding = encoding
        self.api_key = api_key
        self.language = language or "en"
        self.ws = None
        self.session = None
        self.transcript_parts = []
        self._receive_task = None

    async def connect(self):
        # Retrieve key from environment or database
        if not self.api_key:
            self.api_key = settings.DEEPGRAM_API_KEY
        if not self.api_key:
            from app.security import get_api_key_from_db
            self.api_key = await get_api_key_from_db("deepgram")
            
        if not self.api_key:
            logger.warning("Deepgram API Key not set. Streaming STT will fail.")
            raise ValueError("DEEPGRAM_API_KEY is not configured.")

        # Match Deepgram model to audio frequency (nova-2-phonecall is optimized for 8kHz Twilio streams)
        model = "nova-2-phonecall" if self.sample_rate == 8000 else "nova-2-general"
        
        url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?model={model}"
            f"&encoding={self.encoding}"
            f"&sample_rate={self.sample_rate}"
            f"&channels=1"
            f"&interim_results=true"
            f"&smart_format=true"
            f"&language={self.language}"
        )
        
        headers = {
            "Authorization": f"Token {self.api_key}"
        }
        
        self.session = aiohttp.ClientSession()
        try:
            self.ws = await self.session.ws_connect(url, headers=headers)
            logger.info(f"Successfully established Deepgram live streaming connection (model: {model})")
            
            # Start background listener loop
            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Live WebSockets: {e}")
            await self.close()
            raise e

    async def _receive_loop(self):
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [{}])
                    transcript = alternatives[0].get("transcript", "")
                    
                    is_final = data.get("is_final", False)
                    if transcript.strip():
                        if is_final:
                            self.transcript_parts.append(transcript)
                            logger.info(f"Deepgram Real-time Final chunk: '{transcript}'")
                        else:
                            logger.debug(f"Deepgram Interim chunk: '{transcript}'")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error inside Deepgram WebSockets receive loop: {e}")

    async def send_audio(self, chunk: bytes):
        if self.ws and not self.ws.closed:
            try:
                await self.ws.send_bytes(chunk)
            except Exception as e:
                logger.error(f"Failed to stream audio chunk to Deepgram: {e}")

    def get_transcript(self) -> str:
        text = " ".join(self.transcript_parts).strip()
        return text

    def clear_transcript(self):
        self.transcript_parts.clear()

    async def close(self):
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        logger.info("Closed Deepgram Live STT WebSocket session.")

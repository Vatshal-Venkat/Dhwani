import io
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from groq import Groq
from app.config import settings

logger = logging.getLogger("voice-agent")

# Persistent shared executor for Whisper STT API calls
_stt_executor = ThreadPoolExecutor(max_workers=4)

class STTService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.client = None

    async def _ensure_client(self):
        if self.client:
            return
        if not self.api_key:
            self.api_key = settings.GROQ_API_KEY
        if not self.api_key:
            from app.security import get_api_key_from_db
            self.api_key = await get_api_key_from_db("groq")
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            logger.warning("GROQ_API_KEY is not configured. STT service will fail unless a key is provided dynamically.")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "speech.webm", language: str = None) -> str:
        """
        Transcribes audio bytes to text using Groq's Whisper-large-v3 with optional language lock.
        """
        await self._ensure_client()
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set. Please set it in your environment or credentials.")
        try:
            # Create a file-like object from raw bytes
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename

            def run_transcribe():
                kwargs = {
                    "file": audio_file,
                    "model": "whisper-large-v3",
                    "response_format": "text"
                }
                if language:
                    kwargs["language"] = language
                response = self.client.audio.transcriptions.create(**kwargs)
                return response

            loop = asyncio.get_running_loop()
            transcript_text = await loop.run_in_executor(_stt_executor, run_transcribe)
            
            return transcript_text.strip()
        except Exception as e:
            logger.error(f"Error transcribing audio with Groq: {e}")
            raise e

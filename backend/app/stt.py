import io
import logging
from groq import Groq
from app.config import settings

logger = logging.getLogger("voice-agent")

class STTService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.client = None
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            logger.warning("GROQ_API_KEY is not configured. STT service will fail unless a key is provided dynamically.")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "speech.webm") -> str:
        """
        Transcribes WebM audio bytes to text using Groq's Whisper-large-v3.
        """
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set. Please set it in your environment or credentials.")

        if not self.client:
            self.client = Groq(api_key=self.api_key)

        try:
            # Run the synchronous API call in an executor to avoid blocking the main async thread
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            # Create a file-like object from raw bytes
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename

            def run_transcribe():
                response = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="text"
                )
                return response

            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as pool:
                transcript_text = await loop.run_in_executor(pool, run_transcribe)
            
            return transcript_text.strip()
        except Exception as e:
            logger.error(f"Error transcribing audio with Groq: {e}")
            raise e

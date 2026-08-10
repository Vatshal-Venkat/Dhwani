import edge_tts
from app.config import settings
import logging

logger = logging.getLogger("voice-agent")

class TTSService:
    def __init__(self, voice: str = None):
        self.voice = voice or settings.DEFAULT_VOICE

    async def generate_speech(self, text: str, voice_override: str = None, rate_override: str = None) -> bytes:
        """
        Synthesize text to speech using edge-tts with a natural speaking pace.
        Returns bytes of MP3 audio.
        """
        selected_voice = voice_override or self.voice
        selected_rate = rate_override or "-10%"
        try:
            communicate = edge_tts.Communicate(text, selected_voice, rate=selected_rate)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            if audio_data:
                return audio_data


            # Fallback retry without rate modification
            logger.info("Retrying edge-tts synthesis without custom rate...")
            communicate = edge_tts.Communicate(text, selected_voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data
        except Exception as e:
            logger.error(f"Error during edge-tts synthesis: {e}")
            raise e

    @staticmethod
    def get_available_voices():
        # A curated list of realistic Microsoft voices
        return [
            {"id": "en-US-EmmaMultilingualNeural", "name": "Emma (Multilingual, US)", "gender": "Female"},
            {"id": "en-US-AvaNeural", "name": "Ava (US)", "gender": "Female"},
            {"id": "en-US-AndrewNeural", "name": "Andrew (US)", "gender": "Male"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia (UK)", "gender": "Female"},
            {"id": "en-GB-RyanNeural", "name": "Ryan (UK)", "gender": "Male"},
            {"id": "es-ES-ElviraNeural", "name": "Elvira (Spain)", "gender": "Female"},
            {"id": "fr-FR-DeniseNeural", "name": "Denise (France)", "gender": "Female"},
            {"id": "de-DE-KatjaNeural", "name": "Katja (Germany)", "gender": "Female"}
        ]

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.5-flash")
    DEFAULT_VOICE: str = os.getenv("DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Twilio configurations for outbound calling
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

settings = Settings()

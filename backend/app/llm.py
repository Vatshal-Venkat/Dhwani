import google.generativeai as genai
from groq import Groq
from app.config import settings
import logging

logger = logging.getLogger("voice-agent")

class LLMService:
    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        
        self.gemini_client = None
        self.groq_client = None
        self.api_key = api_key
        
        if self.provider == "gemini":
            if not self.api_key:
                self.api_key = settings.GEMINI_API_KEY
            if not self.api_key:
                logger.warning("GEMINI_API_KEY is not set.")
            genai.configure(api_key=self.api_key)
        elif self.provider == "groq":
            if not self.api_key:
                self.api_key = settings.GROQ_API_KEY
            if not self.api_key:
                logger.warning("GROQ_API_KEY is not set.")
            self.groq_client = Groq(api_key=self.api_key)

    async def get_response(self, history: list, system_prompt: str) -> str:
        """
        Generates LLM completion based on history.
        history format: [{"role": "user"/"assistant", "content": "..."}]
        """
        if not self.api_key:
            return f"Please configure your {self.provider.upper()}_API_KEY in the environment settings or enter it in the web interface."

        try:
            if self.provider == "gemini":
                # Convert standard chat history to Gemini structure
                # System prompt is passed to generation config or system_instruction
                model_name = self.model if "gemini" in self.model else "gemini-1.5-flash"
                
                # Format history for Gemini
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [h["content"]]})
                
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_prompt
                )
                
                # Using run_in_executor or call directly since generativeai is synchronous
                response = model.generate_content(contents)
                return response.text
                
            elif self.provider == "groq":
                messages = [{"role": "system", "content": system_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
                
                completion = self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150
                )
                return completion.choices[0].message.content
            
            else:
                return f"Unsupported LLM provider: {self.provider}"
        except Exception as e:
            logger.error(f"Error calling LLM provider {self.provider}: {e}")
            return f"Error: Could not retrieve response from {self.provider}. Details: {str(e)}"

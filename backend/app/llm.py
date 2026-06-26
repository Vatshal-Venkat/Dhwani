from google import genai
from google.genai import types
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
            self.gemini_client = genai.Client(api_key=self.api_key)
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
                model_name = self.model if "gemini" in self.model else "gemini-3.5-flash"
                
                # Format history for Gemini
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=h["content"])]
                        )
                    )
                
                # Generate content using the new SDK
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt
                    )
                )
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

    async def get_response_stream(self, history: list, system_prompt: str):
        """
        Generates LLM completion as an async generator yielding complete sentences.
        """
        if not self.api_key:
            yield f"Please configure your {self.provider.upper()}_API_KEY."
            return

        try:
            sentence_buffer = ""
            sentence_endings = {'.', '!', '?'}

            if self.provider == "gemini":
                model_name = self.model if "gemini" in self.model else "gemini-3.5-flash"
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=h["content"])]
                        )
                    )
                
                # Using the google-genai generate_content_stream
                response_stream = self.gemini_client.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt
                    )
                )

                for chunk in response_stream:
                    if chunk.text:
                        sentence_buffer += chunk.text
                        while True:
                            first_ending_idx = -1
                            for i, char in enumerate(sentence_buffer):
                                if char in sentence_endings:
                                    if i + 1 == len(sentence_buffer) or sentence_buffer[i + 1].isspace():
                                        first_ending_idx = i
                                        break
                            if first_ending_idx != -1:
                                sentence = sentence_buffer[:first_ending_idx + 1].strip()
                                sentence_buffer = sentence_buffer[first_ending_idx + 1:]
                                if sentence:
                                    yield sentence
                            else:
                                break

            elif self.provider == "groq":
                messages = [{"role": "system", "content": system_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})

                completion_stream = self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150,
                    stream=True
                )

                for chunk in completion_stream:
                    if chunk.choices[0].delta.content:
                        sentence_buffer += chunk.choices[0].delta.content
                        while True:
                            first_ending_idx = -1
                            for i, char in enumerate(sentence_buffer):
                                if char in sentence_endings:
                                    if i + 1 == len(sentence_buffer) or sentence_buffer[i + 1].isspace():
                                        first_ending_idx = i
                                        break
                            if first_ending_idx != -1:
                                sentence = sentence_buffer[:first_ending_idx + 1].strip()
                                sentence_buffer = sentence_buffer[first_ending_idx + 1:]
                                if sentence:
                                    yield sentence
                            else:
                                break

            else:
                yield f"Unsupported LLM provider: {self.provider}"

            # Yield any remaining text
            remaining = sentence_buffer.strip()
            if remaining:
                yield remaining

        except Exception as e:
            logger.error(f"Error streaming from {self.provider}: {e}")
            yield f"Error: Could not retrieve response from {self.provider}."

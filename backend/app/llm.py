from google import genai
from google.genai import types
from groq import AsyncGroq
from app.config import settings
import logging

logger = logging.getLogger("voice-agent")

def split_buffer_into_sentences(buffer: str) -> tuple[list[str], str]:
    """
    Splits the buffer into completed sentences, bypassing common abbreviations.
    Returns (completed_sentences, remaining_buffer).
    """
    sentence_endings = {'.', '!', '?'}
    abbreviations = {
        'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr',
        'eg', 'ie', 'etc', 'vs', 'approx', 'apt', 'dept', 'est', 'temp',
        'a.m', 'p.m', 'st', 'inc', 'co', 'ltd'
    }
    
    sentences = []
    i = 0
    start_idx = 0
    
    while i < len(buffer):
        char = buffer[i]
        if char in sentence_endings:
            is_split = True
            
            # Case 1: Decimals / digits (e.g. "3.14" or "10.00")
            if char == '.' and i > 0 and i + 1 < len(buffer):
                if buffer[i-1].isdigit() and buffer[i+1].isdigit():
                    is_split = False
            
            # Case 2: Abbreviations
            if is_split and char == '.' and i > 0:
                # Find the word preceding the period
                word_start = i - 1
                while word_start > start_idx and not buffer[word_start].isspace():
                    word_start -= 1
                
                word = buffer[word_start:i].strip().lower()
                word = word.lstrip('("-\'')
                
                if word in abbreviations:
                    is_split = False
                elif '.' in word:
                    is_split = False
            
            # Case 3: Check if followed by whitespace or end of buffer
            if is_split:
                if i + 1 == len(buffer) or buffer[i+1].isspace():
                    sentence = buffer[start_idx:i+1].strip()
                    if sentence:
                        sentences.append(sentence)
                    start_idx = i + 1
        i += 1
        
    remaining_buffer = buffer[start_idx:]
    return sentences, remaining_buffer


class LLMService:
    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        
        self.gemini_client = None
        self.groq_client = None
        self.api_key = api_key

    async def _ensure_client(self):
        """
        Ensures the client for the selected provider is initialized.
        Asynchronously fetches keys from database if not set.
        """
        if self.provider == "gemini":
            if self.gemini_client:
                return
            if not self.api_key:
                self.api_key = settings.GEMINI_API_KEY
            if not self.api_key:
                from app.security import get_api_key_from_db
                self.api_key = await get_api_key_from_db("gemini")
            
            if self.api_key:
                self.gemini_client = genai.Client(api_key=self.api_key)
            else:
                logger.warning("GEMINI_API_KEY is not set.")
                
        elif self.provider == "groq":
            if self.groq_client:
                return
            if not self.api_key:
                self.api_key = settings.GROQ_API_KEY
            if not self.api_key:
                from app.security import get_api_key_from_db
                self.api_key = await get_api_key_from_db("groq")
            
            if self.api_key:
                self.groq_client = AsyncGroq(api_key=self.api_key)
            else:
                logger.warning("GROQ_API_KEY is not set.")

    async def get_response(self, history: list, system_prompt: str, json_mode: bool = False) -> str:
        """
        Generates LLM completion based on history.
        history format: [{"role": "user"/"assistant", "content": "..."}]
        """
        await self._ensure_client()
        if not self.api_key:
            return f"Please configure your {self.provider.upper()}_API_KEY in the environment settings or enter it in the web interface."

        if history:
            system_prompt = system_prompt + (
                "\n\n[CONVERSATIONAL RULE: You must always respond in the same language that the user spoke to you in their latest message. "
                "If the user speaks Spanish, reply in Spanish. If they speak English, reply in English. "
                "Do not translate their query to reply in English if they spoke another language.]"
            )

        try:
            if self.provider == "gemini":
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
                
                # If contents is empty, we must pass the prompt inside contents, otherwise pass it as system_instruction
                if not contents:
                    contents = system_prompt
                    if json_mode:
                        config = types.GenerateContentConfig(response_mime_type="application/json")
                    else:
                        config = None
                else:
                    if json_mode:
                        config = types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json"
                        )
                    else:
                        config = types.GenerateContentConfig(
                            system_instruction=system_prompt
                        )
                
                # Generate content using the new SDK asynchronously
                response = await self.gemini_client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                return response.text
                
            elif self.provider == "groq":
                messages = [{"role": "system", "content": system_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
                
                completion = await self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150,
                    response_format={"type": "json_object"} if json_mode else None
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
        await self._ensure_client()
        if not self.api_key:
            yield f"Please configure your {self.provider.upper()}_API_KEY."
            return

        if history:
            system_prompt = system_prompt + (
                "\n\n[CONVERSATIONAL RULE: You must always respond in the same language that the user spoke to you in their latest message. "
                "If the user speaks Spanish, reply in Spanish. If they speak English, reply in English. "
                "Do not translate their query to reply in English if they spoke another language.]"
            )

        try:
            sentence_buffer = ""

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
                
                # Using the async google-genai generate_content_stream
                response_stream = await self.gemini_client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt
                    )
                )

                async for chunk in response_stream:
                    if chunk.text:
                        sentence_buffer += chunk.text
                        completed_sentences, sentence_buffer = split_buffer_into_sentences(sentence_buffer)
                        for sentence in completed_sentences:
                            yield sentence

            elif self.provider == "groq":
                messages = [{"role": "system", "content": system_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})

                completion_stream = await self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150,
                    stream=True
                )

                async for chunk in completion_stream:
                    if chunk.choices[0].delta.content:
                        sentence_buffer += chunk.choices[0].delta.content
                        completed_sentences, sentence_buffer = split_buffer_into_sentences(sentence_buffer)
                        for sentence in completed_sentences:
                            yield sentence

            else:
                yield f"Unsupported LLM provider: {self.provider}"

            # Yield any remaining text
            remaining = sentence_buffer.strip()
            if remaining:
                yield remaining

        except Exception as e:
            logger.error(f"Error streaming from {self.provider}: {e}")
            yield f"Error: Could not retrieve response from {self.provider}."

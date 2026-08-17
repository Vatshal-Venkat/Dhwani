from google import genai
from google.genai import types
from groq import AsyncGroq
from app.config import settings
from app.tools import execute_tool, AVAILABLE_TOOLS
import logging
import json
import re

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
        raw_model = model or settings.LLM_MODEL
        if self.provider == "groq" and ("gemini" in raw_model or not raw_model):
            raw_model = "llama-3.1-8b-instant"
        elif self.provider == "gemini" and ("llama" in raw_model or "groq" in raw_model or raw_model == "gemini-3.5-flash"):
            raw_model = "gemini-2.5-flash"
        self.model = raw_model
        
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

    def _build_system_prompt(self, base_prompt: str) -> str:
        """Appends conversational pacing, tool calling capabilities, and human transfer protocol to system prompt."""
        tool_desc = json.dumps(AVAILABLE_TOOLS, indent=2)
        prompt = (
            base_prompt +
            "\n\n[ACTION EXECUTION ENGINE & TOOL INSTRUCTIONS]\n"
            "You have access to real-time action tools to create/check appointments, record customer leads, and transfer callers to human representatives.\n"
            f"Available Tools Schema:\n{tool_desc}\n\n"
            "When the user requests an action (e.g. checking slots, booking an appointment, transferring to human), output a tool execution tag in this exact format:\n"
            "[ACTION: tool_name({\"param1\": \"val1\", ...})]\n"
            "If you need to book an appointment or capture a lead, ask for the customer's name and details if missing, or use default details from context.\n"
            "Do NOT invent false confirmation codes without invoking the create_booking tool."
            "\n\n[CUSTOMER DISSATISFACTION & HUMAN TRANSFER PROTOCOL]\n"
            "1. DISSATISFACTION DETECTION: If the customer expresses frustration, says you are not being helpful (e.g., 'you aren't helping', 'this isn't working', 'waste of time', 'this is useless', 'can I speak to a person'), or explicitly asks for a human/agent/representative/manager:\n"
            "   - Do NOT argue or repeat prior unhelpful answers.\n"
            "   - Immediately ASK PERMISSION to connect them with a real human representative:\n"
            "     \"I apologize, it seems like I'm not helping as well as you need. Would you like me to connect you with a real human representative from our team right now?\"\n"
            "2. PERMISSION CONFIRMATION & REDIRECTION:\n"
            "   - IF the customer confirms or says yes (e.g., 'yes', 'yeah', 'please', 'connect me', 'sure', 'do that'):\n"
            "     - Output the tool execution tag: [ACTION: transfer_to_human({\"reason\": \"Customer requested human after dissatisfaction\", \"department\": \"Senior Customer Support\"})]\n"
            "     - Say: \"Connecting you to a live support representative now. Please hold on...\"\n"
            "   - IF the customer declines or says no (e.g., 'no', 'it's okay', 'let's try again'):\n"
            "     - Say: \"Understood! I'm here to help. What else can I assist you with today?\"\n"
            "\n\n[CONVERSATIONAL RULE: You must always respond in the same language that the user spoke to you in their latest message.]"
            "\n\n[CONVERSATIONAL PACING RULE: You must sound like a natural, polite human during a telephone call. "
            "1. Use occasional conversational filler words naturally at the beginning of your response to acknowledge the user (e.g., 'Ah, got it.', 'Oh, okay.', 'Hmm, let me check...', 'Sure, I can help with that...'). "
            "2. Write like you speak. Keep sentences relatively short and use ellipsis '...' to indicate brief natural pauses between ideas.]"
        )
        return prompt

    async def get_response(self, history: list, system_prompt: str, json_mode: bool = False) -> str:
        await self._ensure_client()
        if not self.api_key:
            return f"Please configure your {self.provider.upper()}_API_KEY."

        full_prompt = self._build_system_prompt(system_prompt)

        try:
            if self.provider == "gemini":
                model_name = self.model if "gemini" in self.model else "gemini-2.5-flash"
                if model_name == "gemini-3.5-flash":
                    model_name = "gemini-2.5-flash"
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))
                if not contents:
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(text="Analyze the input.")]))
                
                config = types.GenerateContentConfig(
                    system_instruction=full_prompt,
                    response_mime_type="application/json" if json_mode else None
                )
                
                response = await self.gemini_client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                text = response.text or ""
                
            elif self.provider == "groq":
                messages = [{"role": "system", "content": full_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
                
                completion = await self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=250,
                    response_format={"type": "json_object"} if json_mode else None
                )
                text = completion.choices[0].message.content or ""
            else:
                return f"Unsupported LLM provider: {self.provider}"

            # Check if text contains tool action tag
            action_match = re.search(r'\[ACTION:\s*(\w+)\((.*?)\)\]', text, re.DOTALL)
            if action_match:
                func_name = action_match.group(1)
                raw_args = action_match.group(2)
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}

                tool_res = await execute_tool(func_name, args)
                # Re-run LLM with tool result
                tool_msg = f"[TOOL EXECUTION RESULT]: {json.dumps(tool_res)}"
                history.append({"role": "assistant", "content": text})
                history.append({"role": "user", "content": tool_msg})
                return await self.get_response(history, system_prompt, json_mode)

            return text
        except Exception as e:
            logger.error(f"Error calling LLM provider {self.provider}: {e}")
            return f"Error: Could not retrieve response from {self.provider}. Details: {str(e)}"

    async def get_response_stream(self, history: list, system_prompt: str):
        """
        Generates LLM completion as an async generator yielding complete sentences.
        Intercepts tool execution tags and runs backend tools mid-stream.
        """
        await self._ensure_client()
        if not self.api_key:
            yield f"Please configure your {self.provider.upper()}_API_KEY."
            return

        full_prompt = self._build_system_prompt(system_prompt)

        try:
            sentence_buffer = ""
            full_text = ""

            if self.provider == "gemini":
                model_name = self.model if "gemini" in self.model else "gemini-2.5-flash"
                if model_name == "gemini-3.5-flash":
                    model_name = "gemini-2.5-flash"
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))
                if not contents:
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(text="Hello.")]))
                
                response_stream = await self.gemini_client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=full_prompt)
                )

                async for chunk in response_stream:
                    if chunk.text:
                        full_text += chunk.text
                        sentence_buffer += chunk.text
                        completed_sentences, sentence_buffer = split_buffer_into_sentences(sentence_buffer)
                        for sentence in completed_sentences:
                            # Filter out raw action tag from spoken audio if present
                            clean_sentence = re.sub(r'\[ACTION:.*?\]', '', sentence).strip()
                            if clean_sentence:
                                yield clean_sentence

            elif self.provider == "groq":
                messages = [{"role": "system", "content": full_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})

                completion_stream = await self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=250,
                    stream=True
                )

                async for chunk in completion_stream:
                    if chunk.choices[0].delta.content:
                        text_chunk = chunk.choices[0].delta.content
                        full_text += text_chunk
                        sentence_buffer += text_chunk
                        completed_sentences, sentence_buffer = split_buffer_into_sentences(sentence_buffer)
                        for sentence in completed_sentences:
                            clean_sentence = re.sub(r'\[ACTION:.*?\]', '', sentence).strip()
                            if clean_sentence:
                                yield clean_sentence

            # Check remaining text in sentence buffer
            remaining = sentence_buffer.strip()
            if remaining:
                clean_rem = re.sub(r'\[ACTION:.*?\]', '', remaining).strip()
                if clean_rem:
                    yield clean_rem

            # Check if a tool execution was triggered in full_text
            action_match = re.search(r'\[ACTION:\s*(\w+)\((.*?)\)\]', full_text, re.DOTALL)
            if action_match:
                func_name = action_match.group(1)
                raw_args = action_match.group(2)
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}

                logger.info(f"Executing mid-stream tool call: {func_name}")
                tool_res = await execute_tool(func_name, args)
                
                # Secondary stream turn to verbally communicate tool result
                updated_history = list(history)
                updated_history.append({"role": "assistant", "content": f"I will perform this action now. [Executed {func_name}]"})
                updated_history.append({"role": "user", "content": f"[SYSTEM TOOL EXECUTION SUCCESSFUL]: {json.dumps(tool_res)}. Please inform the user."})
                
                async for sec_sentence in self.get_response_stream(updated_history, system_prompt):
                    yield sec_sentence

        except Exception as e:
            logger.error(f"Error streaming from {self.provider}: {e}")
            yield f"Error: Could not retrieve response from {self.provider}."

import json
import logging
from app.database import AsyncSessionLocal
from app.models import Call
from app.llm import LLMService

logger = logging.getLogger("voice-agent")

async def summarize_and_update_call(call_id: int, transcription_log_json: str):
    """
    Summarizes the call transcript, classifies the call disposition,
    and extracts key structured metrics using LLM analysis.
    """
    if not transcription_log_json:
        logger.info(f"Summarizer: Empty transcript for Call {call_id}. Skipping summarization.")
        return

    try:
        # 1. Parse transcription log and format into a dialogue script
        history = json.loads(transcription_log_json)
        if not history:
            logger.info(f"Summarizer: Empty conversation history for Call {call_id}.")
            return
            
        dialogue = ""
        for turn in history:
            role = turn.get("role", "unknown").capitalize()
            content = turn.get("content", "")
            dialogue += f"{role}: {content}\n"

        logger.info(f"Summarizer: Starting post-call analysis for Call {call_id} ({len(history)} turns)")

        # 2. Construct LLM analysis prompt for structured JSON output
        # We initialize LLMService which defaults to the system provider (Gemini or Groq)
        llm = LLMService()
        
        prompt = f"""
You are an expert conversational AI analysis system. Analyze the following phone call transcript.
You must output a single JSON object. Do not wrap the JSON object in markdown blocks (e.g. do not write ```json), and do not include any explanatory text before or after the JSON.

Expected JSON schema:
{{
  "summary": "A concise, single-sentence summary of what happened during the call (e.g., 'The customer scheduled a tech support appointment for tomorrow morning.')",
  "disposition": "Must be exactly one of: 'Appointment Confirmed', 'Reschedule Requested', 'Voicemail Detected', 'Refused/Hung Up', 'General Inquiry', 'Unclear/No Response'.",
  "structured_outcome": {{
     "interest_level": "High", "Medium", "Low", or "None",
     "follow_up_needed": true or false,
     "key_points": ["Point 1", "Point 2", ...]
  }}
}}

Transcript to analyze:
{dialogue}
"""
        
        # 3. Call LLM
        response_text = await llm.get_response(history=[], system_prompt=prompt, json_mode=True)
        
        # Parse the JSON response
        clean_text = response_text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()
            
        try:
            analysis_data = json.loads(clean_text)
        except json.JSONDecodeError as json_err:
            logger.error(f"Summarizer: JSON parsing failed for raw LLM text: '{clean_text}'. Error: {json_err}")
            raise json_err
            
        summary = analysis_data.get("summary", "No summary could be parsed.")
        disposition = analysis_data.get("disposition", "General Inquiry")
        structured_outcome = json.dumps(analysis_data.get("structured_outcome", {}))

        # 4. Save to Database
        async with AsyncSessionLocal() as session:
            db_call = await session.get(Call, call_id)
            if db_call:
                db_call.summary = summary
                db_call.disposition = disposition
                db_call.structured_outcome = structured_outcome
                await session.commit()
                logger.info(f"Summarizer: Call {call_id} successfully updated. Disposition: '{disposition}'")
            else:
                logger.error(f"Summarizer: Call ID {call_id} not found in database.")
                
    except Exception as e:
        logger.error(f"Summarizer: Failed to analyze Call {call_id}: {e}")

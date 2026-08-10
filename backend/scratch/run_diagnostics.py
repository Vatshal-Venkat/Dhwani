import asyncio
import os
import sys
import importlib
import traceback

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def run_diagnostics():
    print("=" * 60)
    print("      DHWANI VOICE AGENT - BACKEND DIAGNOSTIC REPORT      ")
    print("=" * 60)
    
    results = {}
    
    # 1. Environment & Config Audit
    print("\n--- 1. CONFIGURATION & ENVIRONMENT VARIABLES ---")
    try:
        from app.config import settings
        results["config_import"] = "OK"
        print(f"  LLM Provider    : {settings.LLM_PROVIDER}")
        print(f"  LLM Model       : {settings.LLM_MODEL}")
        print(f"  Default Voice   : {settings.DEFAULT_VOICE}")
        print(f"  Server Port     : {settings.PORT}")
        print(f"  Gemini API Key  : {'SET (' + settings.GEMINI_API_KEY[:6] + '...)' if settings.GEMINI_API_KEY else 'NOT SET'}")
        print(f"  Groq API Key    : {'SET (' + settings.GROQ_API_KEY[:6] + '...)' if settings.GROQ_API_KEY else 'NOT SET'}")
        print(f"  Deepgram Key    : {'SET (' + settings.DEEPGRAM_API_KEY[:6] + '...)' if settings.DEEPGRAM_API_KEY else 'NOT SET'}")
        print(f"  Twilio Account  : {'SET' if settings.TWILIO_ACCOUNT_SID else 'NOT SET'}")
        print(f"  Twilio From     : {settings.TWILIO_FROM_NUMBER if settings.TWILIO_FROM_NUMBER else 'NOT SET'}")
        print(f"  Public URL      : {settings.PUBLIC_URL if settings.PUBLIC_URL else 'NOT SET'}")
    except Exception as e:
        results["config_import"] = f"FAILED: {e}"
        print(f"  [ERROR] Loading config: {e}")

    # 2. Module Import Checks
    print("\n--- 2. BACKEND MODULE INTEGRITY & IMPORTS ---")
    modules_to_test = [
        "app.config",
        "app.models",
        "app.database",
        "app.security",
        "app.analytics",
        "app.guardrails",
        "app.stt",
        "app.streaming_stt",
        "app.tts",
        "app.tools",
        "app.llm",
        "app.scheduler",
        "app.twilio_utils",
        "app.main"
    ]
    
    failed_modules = []
    for mod_name in modules_to_test:
        try:
            mod = importlib.import_module(mod_name)
            print(f"  [OK] {mod_name}")
        except Exception as e:
            failed_modules.append((mod_name, str(e)))
            print(f"  [FAIL] {mod_name}: {e}")
            traceback.print_exc()

    results["modules_status"] = "ALL OK" if not failed_modules else f"{len(failed_modules)} failed"

    # 3. Database Integrity & Migration Diagnostic
    print("\n--- 3. DATABASE DIAGNOSTIC ---")
    try:
        from app.database import init_db, AsyncSessionLocal, DATABASE_URL
        print(f"  Database URL    : {DATABASE_URL}")
        
        # Test DB connection and migration
        await init_db()
        print("  [OK] Database schema initialization & migration successful")

        from sqlalchemy import select, func
        from app.models import Agent, Call, APIKey, ScheduledCall, Booking, Lead
        
        async with AsyncSessionLocal() as session:
            agent_count = (await session.execute(select(func.count(Agent.id)))).scalar()
            call_count = (await session.execute(select(func.count(Call.id)))).scalar()
            key_count = (await session.execute(select(func.count(APIKey.id)))).scalar()
            sched_count = (await session.execute(select(func.count(ScheduledCall.id)))).scalar()
            booking_count = (await session.execute(select(func.count(Booking.id)))).scalar()
            lead_count = (await session.execute(select(func.count(Lead.id)))).scalar()

            print(f"  Agents Table    : {agent_count} records")
            print(f"  Calls Table     : {call_count} records")
            print(f"  API Keys Table  : {key_count} records")
            print(f"  Scheduled Calls : {sched_count} records")
            print(f"  Bookings Table  : {booking_count} records")
            print(f"  Leads Table     : {lead_count} records")
            
        results["db_status"] = "OK"
    except Exception as e:
        results["db_status"] = f"FAILED: {e}"
        print(f"  [ERROR] Database diagnostic failed: {e}")
        traceback.print_exc()

    # 4. LLM Service Connectivity Check
    print("\n--- 4. LLM SERVICE CONNECTIVITY ---")
    try:
        from app.config import settings
        if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.LLM_MODEL,
                contents="Ping backend diagnostic check. Answer in one word: Operational"
            )
            print(f"  [OK] Gemini API Response ({settings.LLM_MODEL}): {response.text.strip()}")
            results["llm_status"] = "OK"
        elif settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
            from groq import AsyncGroq
            groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            response = await groq_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": "Ping backend diagnostic check. Answer in one word: Operational"}]
            )
            print(f"  [OK] Groq API Response ({settings.LLM_MODEL}): {response.choices[0].message.content.strip()}")
            results["llm_status"] = "OK"
        else:
            print(f"  [WARNING] Provider={settings.LLM_PROVIDER}, API Key presence check failed or missing key.")
            results["llm_status"] = "WARNING: API key missing"
    except Exception as e:
        results["llm_status"] = f"FAILED: {e}"
        print(f"  [ERROR] LLM test failed: {e}")

    # 5. Text-To-Speech (Edge TTS) Diagnostic
    print("\n--- 5. TTS (EDGE-TTS) DIAGNOSTIC ---")
    try:
        import edge_tts
        communicate = edge_tts.Communicate("Backend diagnostic audio test.", settings.DEFAULT_VOICE)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        print(f"  [OK] Edge-TTS stream test successful. Generated {len(audio_data)} bytes of audio.")
        results["tts_status"] = "OK"
    except Exception as e:
        results["tts_status"] = f"FAILED: {e}"
        print(f"  [ERROR] Edge-TTS test failed: {e}")

    # 6. FastAPI Router & Endpoints Diagnostic
    print("\n--- 6. FASTAPI ROUTER & ENDPOINTS AUDIT ---")
    try:
        from app.main import app
        route_list = []
        for route in app.routes:
            methods = getattr(route, "methods", None)
            path = getattr(route, "path", None)
            if path:
                m_str = ",".join(methods) if methods else "WS/SubApp"
                route_list.append(f"{m_str:<15} {path}")
        
        print(f"  Total Registered Routes: {len(route_list)}")
        for r in route_list:
            print(f"    {r}")
        results["fastapi_status"] = f"OK ({len(route_list)} routes)"
    except Exception as e:
        results["fastapi_status"] = f"FAILED: {e}"
        print(f"  [ERROR] FastAPI audit failed: {e}")

    print("\n" + "=" * 60)
    print("                    DIAGNOSTIC SUMMARY                    ")
    print("=" * 60)
    for k, v in results.items():
        print(f"  {k:<20}: {v}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_diagnostics())

import asyncio
import google.generativeai as genai
from app.config import settings

async def main():
    print("API Key:", settings.GEMINI_API_KEY)
    print("Provider:", settings.LLM_PROVIDER)
    print("Model:", settings.LLM_MODEL)
    
    # Try gemini-1.5-flash first
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Hello")
        print("Success with gemini-1.5-flash:", response.text)
    except Exception as e:
        print("Failed with gemini-1.5-flash:", e)

    # Try model in settings
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.LLM_MODEL)
        response = model.generate_content("Hello")
        print(f"Success with {settings.LLM_MODEL}:", response.text)
    except Exception as e:
        print(f"Failed with {settings.LLM_MODEL}:", e)

if __name__ == "__main__":
    asyncio.run(main())

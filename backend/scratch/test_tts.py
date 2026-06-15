import asyncio
from app.tts import TTSService

async def main():
    try:
        service = TTSService()
        audio = await service.generate_speech("Hello, this is a test.")
        print(f"Success! Generated {len(audio)} bytes of audio.")
    except Exception as e:
        print("Failed to generate speech:", e)

if __name__ == "__main__":
    asyncio.run(main())

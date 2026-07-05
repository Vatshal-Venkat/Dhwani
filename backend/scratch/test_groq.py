import os
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv(dotenv_path="../.env")

api_key = os.getenv("GROQ_API_KEY")
print(f"Loaded API key: {api_key[:10]}...{api_key[-10:] if api_key else ''}")

client = Groq(api_key=api_key)

try:
    models = client.models.list()
    print("Groq API key is VALID! Successfully listed models.")
    print("Available models:")
    for model in models.data[:5]:
        print(f"- {model.id}")
except Exception as e:
    print(f"Groq API key verification failed: {e}")

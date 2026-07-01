import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("GEMINI_API_KEY is not set.")
    exit(1)

client = genai.Client(api_key=api_key)

print("Listing available models...")
try:
    for model in client.models.list():
        print(f"- {model.name} (supports generateContent: {model.supported_actions})")
except Exception as e:
    print(f"Error listing models: {e}")

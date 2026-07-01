import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def validate_config():
    """Validates that all required environment variables are set and not placeholder values."""
    errors = []
    
    if not TELEGRAM_BOT_TOKEN or "your_telegram_bot_token_here" in TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is missing or contains the default placeholder.")
        
    if not GEMINI_API_KEY or "your_gemini_api_key_here" in GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is missing or contains the default placeholder.")
        
    if errors:
        print("Configuration Error(s) found:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease create a '.env' file in the root directory based on '.env.example' and fill in your actual credentials.")
        sys.exit(1)

# Run validation on import to prevent running with invalid config
validate_config()

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LiveKit settings
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_WS_URL = os.getenv("LIVEKIT_WS_URL")

# AI Services
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

# STT Services
# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# TTS Services
# ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# PLAYHT_API_KEY = os.getenv("PLAYHT_API_KEY")
# PLAYHT_USER_ID = os.getenv("PLAYHT_USER_ID")

# Web Search Tool
# SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# Basic check for required environment variables
required_vars = [
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "LIVEKIT_WS_URL",
    "GROQ_API_KEY"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set these variables in your .env file or environment.") 
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Gemini API Configuration ---
API_KEY = os.getenv("GOOGLE_API_KEY")
# Ensure you use a model capable of good code generation and instruction following
MODEL_NAME = "gemini-1.5-flash-latest" # Or "gemini-1.0-pro", "gemini-1.5-pro-latest" etc.

# --- Docker Configuration ---
# A base Python image. Assumes generated code needs only standard libs.
# For more complex needs, you might create a custom image with common libraries (numpy, pandas etc.)
DOCKER_IMAGE = "python:3.10-slim"
DOCKER_TIMEOUT_SECONDS = 120 # Max execution time for the generated code

# --- Agent Configuration ---
MAX_ITERATIONS = 4 # Max attempts including the initial one (0 to MAX_ITERATIONS-1)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

# --- Filename Templates ---
# Use iteration number for clarity
INITIAL_CODE_FILENAME_TPL = "iteration_{}_initial.py"
CORRECTED_CODE_FILENAME_TPL = "iteration_{}_corrected.py"
FINAL_CODE_FILENAME = "final_working_code.py"

# --- Logging ---
LOG_FILE = os.path.join(PROJECT_ROOT, "agent.log")
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL
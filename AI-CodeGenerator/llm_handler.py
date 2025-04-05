# ... (imports and setup as before) ...
import google.generativeai as genai
import config
import logging
from utils import extract_python_code

logger = logging.getLogger(__name__)
# ... (model initialization as before) ...
try:
    if not config.API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set in config or environment.")
    genai.configure(api_key=config.API_KEY)
    model = genai.GenerativeModel(config.MODEL_NAME)
    logger.info(f"Gemini model '{config.MODEL_NAME}' initialized.")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini model: {e}", exc_info=True)
    model = None


def generate_initial_code(requirements: str) -> str | None:
    """Generates the initial Python code based on requirements."""
    if not model: return None # Guard clause

    # --- Updated Prompt ---
    prompt = f"""
    You are an expert Python programmer. Your task is to write a complete, executable Python script based ONLY on the following requirements.
    Assume the script will be executed in a standard Python 3.10 environment.
    You can use standard Python 3.10 libraries. If you need external libraries (e.g., requests, pandas, beautifulsoup4), you MUST include the necessary `import` statements for them. The execution environment will attempt to install these imported packages using pip.
    The script should be self-contained and perform the required task.
    Output ONLY the Python code, enclosed in a single markdown block like ```python ... ```. Do not include explanations before or after the code block.

    Requirements:
    {requirements}
    """
    # --- End Updated Prompt ---

    logger.info("Sending request to Gemini for initial code generation...")
    try:
        # ... (rest of the function remains the same) ...
        response = model.generate_content(prompt)
        logger.debug(f"LLM Raw Response (initial):\n{response.text[:500]}...")
        code = extract_python_code(response.text)
        if code:
            logger.info("Successfully generated and extracted initial code.")
            return code
        else:
            logger.error("Failed to extract code from LLM response for initial generation.")
            logger.debug(f"Full LLM response was:\n{response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during Gemini API call (initial generation): {e}", exc_info=True)
        return None


def debug_code(requirements: str, faulty_code: str, error_message: str) -> str | None:
    """Attempts to fix the provided Python code based on the error message."""
    if not model: return None # Guard clause

    # --- Updated Prompt ---
    prompt = f"""
    You are an expert Python debugger. The following Python script, intended to meet the given requirements, failed during execution (potentially during package installation or script runtime).
    Your task is to analyze the error message and the faulty code, then provide a corrected version of the Python script.
    Assume the script runs in a standard Python 3.10 environment where necessary external libraries mentioned via `import` statements can be installed via pip. Correct any incorrect import statements or library usage.
    Output ONLY the corrected Python code, enclosed in a single markdown block like ```python ... ```. Do not include explanations before or after the code block.

    Initial Requirements:
    {requirements}

    Faulty Code:
    ```python
    {faulty_code}
    ```

    Execution Error (may include pip logs):
    ```
    {error_message}
    ```

    Corrected Code:
    """
    # --- End Updated Prompt ---
    logger.info("Sending request to Gemini for code debugging...")
    try:
        # ... (rest of the function remains the same) ...
        response = model.generate_content(prompt)
        logger.debug(f"LLM Raw Response (debug):\n{response.text[:500]}...")
        code = extract_python_code(response.text)
        if code:
            logger.info("Successfully generated and extracted corrected code.")
            return code
        else:
            logger.error("Failed to extract code from LLM response during debugging.")
            logger.debug(f"Full LLM response was:\n{response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during Gemini API call (debugging): {e}", exc_info=True)
        return None
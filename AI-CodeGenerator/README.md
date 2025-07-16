AI Agent Suite will try to create a project structure like the one below , it will try to follow system design principles and create multiple modules of code
each with different sub task and main.py will make everything work end to end.

user_management_project/
│
├── README.md
├── main.py
├── models/
│   └── user.py
├── services/
│   └── user_service.py
└── utils/
    └── validation.py


    # AI Code Generation Agent Project

This project implements an AI agent that takes natural language requirements, generates Python code using Google's Gemini model, executes it in a secure Docker container, and attempts to debug failures through a feedback loop.

**Disclaimer:** Executing AI-generated code is inherently risky. This project uses Docker for sandboxing, but caution is always advised. The agent currently **does not** handle external library dependencies within the generated code automatically – it assumes standard Python libraries are sufficient.

## Features

*   Takes user requirements as input.
*   Uses Gemini API (configurable model) for code generation and debugging.
*   Executes generated code in an isolated Docker container (`python:3.10-slim` by default).
*   Implements a feedback loop: If code fails (non-zero exit code or stderr output), it sends the code and error back to Gemini for correction.
*   Configurable maximum number of iterations.
*   Saves initial, intermediate (corrected), and final working code to an `output/` directory.
*   Uses structured logging to `output/agent_run.log` and console.

## Setup

1.  **Prerequisites:**
    *   Python 3.8+
    *   Docker Desktop or Docker Engine installed and **running**.
    *   A Google Cloud project with the Gemini API enabled.
    *   Your Google Gemini API Key.

2.  **Clone the Repository (or create files):**
    ```bash
    # git clone <repository_url> # If applicable
    # cd ai_coder_project
    ```    Make sure all the Python files (`main.py`, `config.py`, etc.) and the `output/` directory exist as described above.

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure API Key:**
    *   Create a file named `.env` in the project root directory.
    *   Add your API key to it:
        ```
        GOOGLE_API_KEY=YOUR_ACTUAL_GEMINI_API_KEY
        ```
    *   Alternatively, you can set the `GOOGLE_API_KEY` environment variable directly in your shell before running.

6.  **Review Configuration (Optional):**
    *   Check `config.py` to adjust the `MODEL_NAME`, `DOCKER_IMAGE`, `MAX_ITERATIONS`, etc., if needed.

## Usage

Run the main script from the project's root directory:

```bash
python main.py


How the Dependency Management Works Now:

When docker_runner.execute_code is called, utils.parse_imports scans the generated code.

It identifies potential external packages (filtering out standard libs using stdlib_list).

If external packages are found, a shell command is constructed for Docker:

cd /app

python -m venv .venv_agent (Create venv)

. .venv_agent/bin/activate (Activate venv)

pip install package1 package2 ... (Install detected packages)

python agent_script.py (Run the actual code)

This entire command sequence runs inside the container.

stderr will capture output from pip and the Python script. If pip install fails, the script execution might not even start, but the error will be in stderr.

The main.py loop receives this combined stderr and passes it back to llm_handler.debug_code if the execution fails (non-zero exit code). The LLM now has context about potential installation failures or runtime errors after installation.
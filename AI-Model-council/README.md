# AI Model Council

Small experiment to test how well Composer 2.5 performs on coding and reasoning tasks through the Cursor SDK.

The setup is inspired by the "model council" idea often discussed by Andrej Karpathy:
- run the same prompt through multiple reasoning personas
- let each persona keep its own chat memory
- use a fresh judge to pick or merge the best answer for the current turn

## What it does

- Uses 4 personas:
  - Tree
  - First Principles
  - Inversion
  - Second Order
- Sends every user message through all 4 personas
- Lets a fresh judge synthesize the final answer
- Persists chats locally in `council.db`
- Exposes a minimal Gradio chat UI

## Why this exists

It is a small weekend project to explore whether a council-style loop improves answer quality for coding tasks when all members use Composer 2.5 through the Cursor SDK.

## Run it

Requirements:
- Python 3.11+
- Node.js and `npm`
- `CURSOR_API_KEY` or `CURSOR_SDK_API_KEYS`

Install:

```bash
python -m pip install -r requirements.txt
```

Start:

```bash
python app.py
```

Then open the local Gradio URL shown in the terminal.

## Files

- `model_council.py`: council execution against Cursor SDK
- `db.py`: tiny SQLite persistence layer
- `app.py`: Gradio chat UI
- `council.db`: local chat store created at runtime

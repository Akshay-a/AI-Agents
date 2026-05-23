# TODO

- [x] Confirm architecture: Gradio UI, session-local chat, 4 persona memories, stateless judge
- [x] Refactor council engine to accept and return persona histories
- [x] Add minimal Gradio chat frontend with final answer plus optional persona drafts
- [x] Add minimal SQLite persistence for chats and persona histories
- [x] Add persisted chat session controls to the UI
- [x] Write README for the Composer 2.5 experiment
- [x] Verify runtime and test real chat interaction through Computer Use

# Architecture

- Keep `model_council.py` as the single council backend module.
- Add a small `app.py` Gradio entrypoint instead of introducing a package.
- Use a single local SQLite file for minimal persistence overhead.
- Store chat transcript and persona histories as JSON blobs keyed by chat id.
- Keep one history list per persona; pass it into the backend on every turn.
- Keep the judge fresh by giving it only the current user prompt and current candidate answers.
- Return updated persona histories after each turn so the UI and database can keep continuity.
- Keep files under 150 lines and avoid framework layers this project does not need.

# Review

- `python -m py_compile model_council.py app.py` passed.
- `import app` passed after installing `gradio`.
- `python -m py_compile model_council.py db.py app.py` passed.
- SQLite smoke test passed for create/load/save roundtrip.
- Launching `python app.py` served `http://127.0.0.1:7860`.
- Browser chat test passed with Computer Use for UI clicks plus local keystroke injection:
  first turn asked for `BETA` and the UI returned `BETA`
  second turn asked for the previous token and the UI returned `BETA`
- Persistence check passed:
  `council.db` stored `4` chat messages
  all persona histories had length `4`
  after app restart and browser reload, the prior chat still rendered in the UI

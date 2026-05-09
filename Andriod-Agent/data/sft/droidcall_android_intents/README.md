# DroidCall Android Intent SFT Dataset

This folder contains a deterministic conversion of high-confidence `mllmTeam/DroidCall` rows into this app's current Android Intent JSON schema.

## Files

- `train.jsonl`: 4,027 TRL conversational prompt/completion rows.
- `eval.jsonl`: 200 held-out rows.
- `sample.jsonl`: 100 deterministic sample rows for manual inspection.
- `report.json`: generation counts, drop reasons, action distribution, and examples.

## Format

Each row uses TRL's conversational prompt/completion format:

```json
{
  "prompt": [{"role": "user", "content": "Convert the user request ..."}],
  "completion": [{"role": "assistant", "content": "{\"type\":\"android_intent\",...}"}],
  "source": {"dataset": "mllmTeam/DroidCall", "split": "train", "row_index": 1601, "function": "ACTION_SET_ALARM"}
}
```

The assistant completion is a JSON string that parses into:

```json
{
  "type": "android_intent",
  "intent": {
    "action": "android.intent.action.SET_ALARM",
    "data": null,
    "package": null,
    "extras": {},
    "flags": []
  },
  "safety": {
    "requires_confirmation": false,
    "risk": "low"
  }
}
```

## Conversion Scope

Included:

- alarms and timers
- show alarms
- dialer
- map/location search via `geo:` URI
- web search via browser `VIEW` URL
- camera/video launch intents
- settings screens
- contact view by URI
- SMS draft intents

Excluded:

- multi-step DroidCall traces
- helper data-query functions such as `get_contact_info`
- document/file picker rows that require MIME type support
- rows needing arrays or nested extras, which the Kotlin parser does not currently accept
- email/contact/calendar insert rows that need richer schema support

## Validation

Generated with:

```bash
python3 scripts/build_droidcall_sft.py
```

Validated with:

```bash
python3 scripts/validate_sft_dataset.py \
  data/sft/droidcall_android_intents/train.jsonl \
  data/sft/droidcall_android_intents/eval.jsonl
```

Current result:

```text
valid_rows: 4227
error_count: 0
```

Android emulator resolver checks passed for a 100-row sample from `train.jsonl`, covering alarm, timer, dialer, map/contact/browser `VIEW`, settings, SMS draft, and camera/video intents.

## Training Readiness

This is good enough for a first Gemma SFT smoke test because:

- labels are deterministic, not LLM-generated
- completions are strict JSON only
- every completion passes the current parser constraints
- train/eval split is already present
- unsupported DroidCall rows are skipped instead of guessed

Do not treat this as a complete Android-agent dataset. It is a narrow Intent-first seed dataset.

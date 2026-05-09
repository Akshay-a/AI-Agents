# Android Intent Simulation Spec

## Problem Statement

We want to test whether an LLM can output a structured JSON object that Android can execute. The immediate goal is not to fine-tune the model yet. The immediate goal is to prove the execution path:

```text
JSON object -> Kotlin parser/validator -> Android Intent -> visible Android behavior
```

The first simulation should answer one question:

```text
Can I pass this JSON to Android and dynamically create/execute an Intent from it?
```

If this works, then future model training can target this JSON format. If it does not work, the schema and runtime should be revised before any dataset or fine-tuning work begins.

## Directional Thinking

The initial idea was to make the model output custom commands, such as:

```json
{
  "action": "open_maps",
  "args": {
    "place": "Sydney Opera House"
  }
}
```

That approach is easy to understand, but it creates a scaling problem. Every new action requires custom Kotlin routing, validation, implementation, and tests. Over time, the Android app becomes a custom action framework.

The current preferred direction is to make the model output Android Intent JSON directly. The Android app should stay thin. It should contain one generic runtime that validates JSON, constructs an Intent, and executes it when safe.

The scalable unit is:

```text
generic Android Intent schema + generic Intent runner
```

not:

```text
custom Kotlin function per user task
```

## Target Output Shape

The model should eventually produce one JSON object shaped like this:

```json
{
  "type": "android_intent",
  "intent": {
    "action": "android.intent.action.VIEW",
    "data": "geo:0,0?q=Sydney%20Opera%20House",
    "package": "com.google.android.apps.maps",
    "extras": {},
    "flags": []
  },
  "safety": {
    "requires_confirmation": false,
    "risk": "low"
  }
}
```

The schema may evolve later, but do not redesign it without asking the user first.

## One Simple Simulation Task

Build the smallest possible Android/Kotlin layer that can manually test individual JSON objects.

Required behavior:

1. Accept a JSON string manually, either from a simple text box or through `adb`.
2. Parse the JSON.
3. Validate that `type` is `android_intent`.
4. Read the `intent` fields.
5. Create an Android `Intent` dynamically.
6. Apply supported fields only:
   - `action`
   - `data`
   - `package`
   - `extras`
   - `flags`
7. Execute the Intent with `startActivity`.
8. Show a visible success/error result in the test app.

First manual test case:

```json
{
  "type": "android_intent",
  "intent": {
    "action": "android.intent.action.SET_ALARM",
    "extras": {
      "android.intent.extra.alarm.HOUR": 7,
      "android.intent.extra.alarm.MINUTES": 30,
      "android.intent.extra.alarm.MESSAGE": "Morning check"
    },
    "flags": []
  },
  "safety": {
    "requires_confirmation": false,
    "risk": "low"
  }
}
```

Expected result:

```text
Android opens the alarm/clock flow, creates the alarm depending on emulator behavior, or fails gracefully with an actionable error.
```

## Explicit Non-Goals

Do not fine-tune a model yet.

Do not research datasets yet.

Do not design the full Android agent architecture yet.

Do not add custom action handlers for WhatsApp, reminders, contacts, Accessibility, permissions, or system settings in the first simulation.

Do not assume that all Android automation can be solved with Intents. Some cases will later need special handling.

Do not silently change the output schema.

## Architecture Control Rule

The user wants full control over architecture, model output format, dataset schema, and fine-tuning strategy.

If an agent thinks an architectural decision is needed, it must ask before implementing.

Examples that require asking:

- Changing the JSON schema.
- Replacing generic Intent JSON with custom action JSON.
- Adding an action router.
- Adding special native handlers.
- Adding Accessibility automation.
- Introducing Appium, UIAutomator, or a larger test framework.
- Choosing the final SFT/GRPO dataset format.
- Deciding confirmation policy for sensitive actions.

The next agent should only implement the simple simulation unless the user explicitly approves a broader scope.

## Success Criteria

The task is complete only when:

1. A manually supplied JSON object can be passed into the Android app.
2. The Kotlin layer parses and validates it.
3. The Kotlin layer creates an Intent dynamically.
4. The app either launches the target Intent or displays a clear error.
5. The alarm example has been manually tested on a real emulator.

After this simulation works, the next phase is to define the model output schema and dataset formatting for fine-tuning.

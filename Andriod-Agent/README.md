# Android Intent Execution POC

This is a minimal Android app for testing whether structured model output can be converted into a native Android `Intent` and executed on a real emulator.

The app is intentionally small. It is not an Android agent, not a fine-tuned model, and not a task router. Its job is to validate one execution path:

```text
model JSON -> Android app parser -> native Intent -> emulator execution
```

## Why This Exists

Future Android AI agent work may need the model to trigger phone actions without adding a custom Kotlin function for every task. This POC checks whether the Android layer can stay thin by accepting a generic Intent JSON schema and converting it directly into a native `Intent`.

If this works reliably, later work can focus on model output quality and safety policy. If it does not, the schema/runtime should be revised before collecting datasets or fine-tuning.

## What The App Does

- Shows a raw JSON text box.
- Parses and validates a minimal Intent JSON payload.
- Supports these Intent fields:
  - `action`
  - `data`
  - `package`
  - `extras`
  - `flags`
- Builds a native Android `Intent`.
- Calls `startActivity()`.
- Shows readable parse or execution errors in the app.

## What It Does Not Do

- It does not include custom handlers such as `setAlarm()` or `openMaps()`.
- It does not route model commands through a custom action framework.
- It does not use Accessibility, UIAutomator, Appium, or background automation.
- It does not fine-tune or call a language model.
- It does not prove that all Android tasks can be handled with Intents.

## Project Shape

```text
app/src/main/java/com/example/intentpoc/
  MainActivity.kt
  IntentJsonParser.kt
  IntentExecutor.kt
```

`MainActivity.kt` owns the small manual test UI.  
`IntentJsonParser.kt` validates JSON and produces a parsed Intent model.  
`IntentExecutor.kt` converts the parsed model into a native Android `Intent` and launches it.

## Build

```bash
./gradlew assembleDebug
```

## Manual Test Loop

1. Start an Android emulator.
2. Install the debug APK.
3. Open the app.
4. Paste or edit Intent JSON.
5. Tap `Execute`.
6. Confirm Android opens the target activity or the app shows a clear error.

Example install and launch:

```bash
./gradlew installDebug
adb shell am start -n com.example.intentpoc/.MainActivity
```

## Example Payload

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

The exact visible behavior depends on the emulator image and installed apps. The app should either launch the native Android flow or show an actionable failure.

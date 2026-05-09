# Android Intent Execution POC Plan

## Goal

Prove the execution path: model JSON -> Android app parser -> native Intent -> real emulator execution, starting with an Android alarm Intent.

## Implementation Checklist

- [x] Inspect local Android/Gradle availability and choose the smallest viable project shape.
- [x] Scaffold a minimal Android Kotlin app if no app exists.
- [x] Implement `MainActivity.kt` with raw JSON input, Execute button, and visible log output.
- [x] Implement `IntentJsonParser.kt` to validate `type == "android_intent"` and parse supported fields only: `action`, `data`, `package`, `extras`, `flags`.
- [x] Implement `IntentExecutor.kt` to construct and execute a native Android `Intent` without custom task handlers.
- [x] Add manifest/package setup required for launching the POC.
- [x] Build the app locally and fix compile issues.
- [x] Install and run on a real Android emulator when available.
- [x] Execute the alarm JSON and record whether Android opens the clock/alarm flow, creates an alarm, or returns a clear actionable failure.
- [x] Add review/results notes here before marking complete.

## Constraints

- No custom alarm handler.
- No custom Maps handler.
- No fallback URLs or alternate success paths.
- Keep the Android layer thin and generic.
- Do not redesign the JSON schema without explicit user approval.

## Review / Results

- Built a minimal Android Kotlin app with `MainActivity.kt`, `IntentJsonParser.kt`, and `IntentExecutor.kt`.
- The app accepts raw JSON, validates `type == "android_intent"`, validates the optional `safety` metadata shape, reads supported intent fields only, builds a native Android `Intent`, and calls `startActivity()`.
- No custom task router, custom alarm handler, custom Maps handler, or fallback URL was added.
- Build command passed: `./gradlew assembleDebug`.
- Emulator used: `Medium_Phone_API_36.1` attached as `emulator-5554`.
- Installed APK with `adb install -r app/build/outputs/apk/debug/app-debug.apk`.
- Executed the default alarm JSON through the app UI by tapping Execute.
- Verification evidence: Android focused `com.google.android.deskclock/com.android.deskclock.DeskClock`, and the UI tree showed an alarm card with `7:30 AM` and label `Morning check`.
- Screenshot evidence saved at `tasks/evidence/alarm-intent-proof.png`.
- Runtime lesson: app-side `resolveActivity()` can produce a false negative for arbitrary implicit intents under Android package visibility, even when `startActivity()` succeeds. The executor now relies on `startActivity()` and clear exception handling.

# Project Overview

## Purpose

This app is a proof of concept for Android Intent execution from structured JSON. It exists to validate the execution layer for a future Android AI agent before investing in model datasets or fine-tuning.

The core question is whether model output can use a generic Android Intent schema instead of custom app-specific Kotlin handlers.

## Execution Path

```text
JSON payload -> parser/validator -> native Android Intent -> startActivity()
```

## Current Scope

The app provides:

- A manual JSON input UI.
- A generic Intent JSON parser.
- A native Intent executor.
- Visible success and error messages.

Supported Intent fields are:

- `action`
- `data`
- `package`
- `extras`
- `flags`

The optional `safety` object is validated as metadata, but it does not currently enforce policy.

## Design Boundary

The app deliberately avoids custom task routing. There are no dedicated Kotlin handlers for alarms, maps, or other user tasks. A payload either maps to a native Android Intent or fails with a clear message.

This keeps the Android layer small and makes it easier to test whether the model-facing schema is viable.

## Validation Goal

The initial validation target is a simple Android-native flow such as `android.intent.action.SET_ALARM`. Package-specific flows can be tested later after the generic execution layer is proven.

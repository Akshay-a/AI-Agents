#!/usr/bin/env python3
import argparse
import json
import random
from collections import Counter
from pathlib import Path


SUPPORTED_FLAGS = {
    "FLAG_ACTIVITY_NEW_TASK",
    "FLAG_ACTIVITY_CLEAR_TOP",
    "FLAG_ACTIVITY_SINGLE_TOP",
    "FLAG_ACTIVITY_NO_HISTORY",
    "FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS",
}

KNOWN_ACTIONS = {
    "android.intent.action.DIAL",
    "android.intent.action.SENDTO",
    "android.intent.action.SET_ALARM",
    "android.intent.action.SET_TIMER",
    "android.intent.action.SHOW_ALARMS",
    "android.intent.action.VIEW",
    "android.media.action.IMAGE_CAPTURE",
    "android.media.action.STILL_IMAGE_CAMERA",
    "android.media.action.VIDEO_CAPTURE",
    "android.media.action.VIDEO_CAMERA",
    "android.settings.AIRPLANE_MODE_SETTINGS",
    "android.settings.APN_SETTINGS",
    "android.settings.BLUETOOTH_SETTINGS",
    "android.settings.DATE_SETTINGS",
    "android.settings.DISPLAY_SETTINGS",
    "android.settings.INPUT_METHOD_SETTINGS",
    "android.settings.INTERNAL_STORAGE_SETTINGS",
    "android.settings.LOCALE_SETTINGS",
    "android.settings.LOCATION_SOURCE_SETTINGS",
    "android.settings.MEMORY_CARD_SETTINGS",
    "android.settings.SECURITY_SETTINGS",
    "android.settings.SETTINGS",
    "android.settings.WIFI_SETTINGS",
    "android.settings.WIRELESS_SETTINGS",
}


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if line.strip():
                yield line_number, json.loads(line)


def completion_payload(row):
    completion = row.get("completion")
    if not isinstance(completion, list) or len(completion) != 1:
        raise ValueError("completion must be a one-message list")
    content = completion[0].get("content")
    if not isinstance(content, str):
        raise ValueError("assistant content must be a string")
    return json.loads(content)


def validate_payload(obj):
    errors = []
    if not isinstance(obj, dict):
        return ["root must be object"]
    if obj.get("type") != "android_intent":
        errors.append("type must be android_intent")
    intent = obj.get("intent")
    if not isinstance(intent, dict):
        return errors + ["intent must be object"]
    action = intent.get("action")
    if not isinstance(action, str) or not action.strip():
        errors.append("intent.action must be non-blank string")
    elif action not in KNOWN_ACTIONS:
        errors.append(f"unknown action {action}")
    for field in ("data", "package"):
        if field in intent and intent[field] is not None and not isinstance(intent[field], str):
            errors.append(f"intent.{field} must be string or null")
    extras = intent.get("extras", {})
    if extras is None:
        extras = {}
    if not isinstance(extras, dict):
        errors.append("intent.extras must be object or null")
    else:
        for key, value in extras.items():
            if not isinstance(key, str):
                errors.append("extra keys must be strings")
            if type(value) not in (str, bool, int, float):
                errors.append(f"unsupported extra {key}")
    flags = intent.get("flags", [])
    if flags is None:
        flags = []
    if not isinstance(flags, list):
        errors.append("intent.flags must be array or null")
    else:
        for flag in flags:
            if type(flag) is str and flag not in SUPPORTED_FLAGS:
                errors.append(f"unsupported flag {flag}")
            elif type(flag) not in (str, int):
                errors.append("flags must be strings or ints")
    safety = obj.get("safety")
    if safety is not None:
        if not isinstance(safety, dict):
            errors.append("safety must be object or null")
        else:
            if "requires_confirmation" in safety and type(safety["requires_confirmation"]) is not bool:
                errors.append("safety.requires_confirmation must be bool")
            if "risk" in safety and type(safety["risk"]) is not str:
                errors.append("safety.risk must be string")
    return errors


def validate_action_semantics(payload):
    errors = []
    intent = payload["intent"]
    action = intent["action"]
    data = intent.get("data")
    extras = intent.get("extras") or {}

    if action == "android.intent.action.DIAL" and not str(data or "").startswith("tel:"):
        errors.append("dial action needs tel: data")
    if action == "android.intent.action.SENDTO" and not str(data or "").startswith("smsto:"):
        errors.append("sms action needs smsto: data")
    if action == "android.intent.action.SET_ALARM":
        for key in ("android.intent.extra.alarm.HOUR", "android.intent.extra.alarm.MINUTES"):
            if type(extras.get(key)) is not int:
                errors.append(f"alarm missing int extra {key}")
    if action == "android.intent.action.SET_TIMER" and type(extras.get("android.intent.extra.alarm.LENGTH")) is not int:
        errors.append("timer missing int length extra")
    if action == "android.intent.action.VIEW" and not isinstance(data, str):
        errors.append("view action needs data")
    if action == "android.intent.action.WEB_SEARCH" and not isinstance(extras.get("query"), str):
        errors.append("web search needs query extra")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = []
    errors = Counter()
    actions = Counter()

    for file_path in args.files:
        for line_number, row in load_jsonl(file_path):
            try:
                payload = completion_payload(row)
                row_errors = validate_payload(payload) + validate_action_semantics(payload)
            except Exception as error:
                row_errors = [f"invalid_record:{error}"]
                payload = None
            if row_errors:
                for error in row_errors:
                    errors[f"{file_path}:{line_number}:{error}"] += 1
            else:
                actions[payload["intent"]["action"]] += 1
                rows.append((file_path, line_number, row, payload))

    print(json.dumps({
        "valid_rows": len(rows),
        "error_count": sum(errors.values()),
        "actions": actions.most_common(),
    }, indent=2))

    if errors:
        print("Errors:")
        for error, count in errors.most_common(25):
            print(count, error)
        raise SystemExit(1)

    sample = random.Random(args.seed).sample(rows, min(args.sample_size, len(rows)))
    print("\nSample:")
    for file_path, line_number, row, payload in sample:
        prompt = row["prompt"][0]["content"].split("User request:", 1)[-1].strip()
        print(f"- {file_path}:{line_number} | {payload['intent']['action']} | {prompt[:120]}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import ast
import json
import random
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


DROIDCALL_PARQUET_URL = (
    "https://huggingface.co/datasets/mllmTeam/DroidCall/resolve/"
    "refs%2Fconvert%2Fparquet/dataset/train/0000.parquet"
)

SYSTEM_INSTRUCTION = (
    "Convert the user request into one executable Android Intent JSON object. "
    "Return only valid JSON. Do not wrap it in Markdown."
)

SUPPORTED_FLAGS = {
    "FLAG_ACTIVITY_NEW_TASK",
    "FLAG_ACTIVITY_CLEAR_TOP",
    "FLAG_ACTIVITY_SINGLE_TOP",
    "FLAG_ACTIVITY_NO_HISTORY",
    "FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS",
}

SETTINGS_ACTIONS = {
    "general": "android.settings.SETTINGS",
    "wireless": "android.settings.WIRELESS_SETTINGS",
    "airplane_mode": "android.settings.AIRPLANE_MODE_SETTINGS",
    "wifi": "android.settings.WIFI_SETTINGS",
    "apn": "android.settings.APN_SETTINGS",
    "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
    "date": "android.settings.DATE_SETTINGS",
    "locale": "android.settings.LOCALE_SETTINGS",
    "input_method": "android.settings.INPUT_METHOD_SETTINGS",
    "display": "android.settings.DISPLAY_SETTINGS",
    "security": "android.settings.SECURITY_SETTINGS",
    "location": "android.settings.LOCATION_SOURCE_SETTINGS",
    "internal_storage": "android.settings.INTERNAL_STORAGE_SETTINGS",
    "memory_card": "android.settings.MEMORY_CARD_SETTINGS",
}

ALARM_EXTRA_KEYS = {
    "EXTRA_HOUR": "android.intent.extra.alarm.HOUR",
    "EXTRA_MINUTES": "android.intent.extra.alarm.MINUTES",
    "EXTRA_MESSAGE": "android.intent.extra.alarm.MESSAGE",
    "EXTRA_RINGTONE": "android.intent.extra.alarm.RINGTONE",
    "EXTRA_VIBRATE": "android.intent.extra.alarm.VIBRATE",
    "EXTRA_SKIP_UI": "android.intent.extra.alarm.SKIP_UI",
}

TIMER_EXTRA_KEYS = {
    "EXTRA_MESSAGE": "android.intent.extra.alarm.MESSAGE",
    "EXTRA_SKIP_UI": "android.intent.extra.alarm.SKIP_UI",
}


def download_if_missing(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        urllib.request.urlretrieve(DROIDCALL_PARQUET_URL, path)


def user_query(messages):
    for message in messages:
        if message.get("role") == "user":
            marker = "Now my query is:"
            content = message.get("content", "")
            return content.split(marker, 1)[-1].strip() if marker in content else content.strip()
    return ""


def assistant_content(messages):
    for message in messages:
        if message.get("role") == "assistant":
            return message.get("content", "").strip()
    return ""


def parse_single_call(text):
    cleaned = text.strip().strip("$").strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) != 1:
        return None, "multi_step"

    _, _, expr = lines[0].partition("=")
    expr = expr.strip() if expr else lines[0]

    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None, "parse_error"

    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None, "not_simple_call"

    args = {}
    for index, arg in enumerate(node.args):
        try:
            args[f"arg{index}"] = ast.literal_eval(arg)
        except ValueError:
            return None, "unsupported_arg"

    for kw in node.keywords:
        if kw.arg is None:
            return None, "unsupported_kwarg"
        try:
            args[kw.arg] = ast.literal_eval(kw.value)
        except ValueError:
            return None, "unsupported_kwarg"

    return {"name": node.func.id, "args": args}, None


def intent(action, data=None, extras=None, risk="low", requires_confirmation=False):
    clean_extras = {key: value for key, value in (extras or {}).items() if value is not None}
    return {
        "type": "android_intent",
        "intent": {
            "action": action,
            "data": data,
            "package": None,
            "extras": clean_extras,
            "flags": [],
        },
        "safety": {
            "requires_confirmation": requires_confirmation,
            "risk": risk,
        },
    }


def duration_seconds(text):
    total = 0
    for amount, unit in re.findall(r"(\d+)\s*(hours?|minutes?|seconds?)", text or "", re.I):
        value = int(amount)
        unit = unit.lower()
        total += value * 3600 if unit.startswith("hour") else value * 60 if unit.startswith("minute") else value
    return total or None


def primitive_dict(values):
    return all(type(value) in (str, bool, int, float) for value in values.values())


def map_call(call):
    name = call["name"]
    args = call["args"]

    if name == "ACTION_SET_ALARM":
        extras = {ALARM_EXTRA_KEYS[key]: args.get(key) for key in ALARM_EXTRA_KEYS}
        if not isinstance(extras.get("android.intent.extra.alarm.HOUR"), int):
            return None, "alarm_missing_hour"
        if not isinstance(extras.get("android.intent.extra.alarm.MINUTES"), int):
            return None, "alarm_missing_minutes"
        return intent("android.intent.action.SET_ALARM", extras=extras), None

    if name == "ACTION_SET_TIMER":
        seconds = duration_seconds(args.get("duration"))
        if seconds is None:
            return None, "timer_bad_duration"
        extras = {"android.intent.extra.alarm.LENGTH": seconds}
        extras.update({TIMER_EXTRA_KEYS[key]: args.get(key) for key in TIMER_EXTRA_KEYS})
        return intent("android.intent.action.SET_TIMER", extras=extras), None

    if name == "ACTION_SHOW_ALARMS":
        return intent("android.intent.action.SHOW_ALARMS"), None

    if name == "ACTION_IMAGE_CAPTURE":
        return intent("android.media.action.IMAGE_CAPTURE", risk="medium", requires_confirmation=True), None

    if name == "ACTION_VIDEO_CAPTURE":
        return intent("android.media.action.VIDEO_CAPTURE", risk="medium", requires_confirmation=True), None

    if name == "INTENT_ACTION_STILL_IMAGE_CAMERA":
        return intent("android.media.action.STILL_IMAGE_CAMERA", risk="medium", requires_confirmation=True), None

    if name == "INTENT_ACTION_VIDEO_CAMERA":
        return intent("android.media.action.VIDEO_CAMERA", risk="medium", requires_confirmation=True), None

    if name == "ACTION_VIEW_CONTACT":
        contact_uri = args.get("contact_uri") or args.get("arg0")
        if not isinstance(contact_uri, str):
            return None, "contact_missing_uri"
        return intent("android.intent.action.VIEW", data=contact_uri), None

    if name == "dial":
        phone_number = args.get("phone_number") or args.get("arg0")
        if not isinstance(phone_number, str):
            return None, "dial_missing_number"
        return intent("android.intent.action.DIAL", data=f"tel:{phone_number}"), None

    if name == "search_location":
        query = args.get("query") or args.get("arg0")
        if not isinstance(query, str):
            return None, "location_missing_query"
        return intent("android.intent.action.VIEW", data=f"geo:0,0?q={urllib.parse.quote(query)}"), None

    if name == "web_search":
        query = args.get("query") or args.get("arg0")
        if not isinstance(query, str):
            return None, "web_missing_query"
        engine = args.get("engine") or "google"
        base_url = "https://www.baidu.com/s" if engine == "baidu" else "https://www.google.com/search"
        return intent("android.intent.action.VIEW", data=f"{base_url}?q={urllib.parse.quote(query)}"), None

    if name == "open_settings":
        setting_type = args.get("setting_type") or args.get("arg0") or "general"
        action = SETTINGS_ACTIONS.get(setting_type)
        if action is None:
            return None, "unsupported_setting"
        return intent(action), None

    if name == "send_message":
        phone_number = args.get("phone_number") or args.get("arg0")
        if not isinstance(phone_number, str):
            return None, "sms_missing_number"
        if args.get("attachments"):
            return None, "sms_attachments_unsupported"
        extras = {
            "sms_body": args.get("body"),
            "android.intent.extra.SUBJECT": args.get("subject"),
        }
        return intent(
            "android.intent.action.SENDTO",
            data=f"smsto:{phone_number}",
            extras=extras,
            risk="medium",
            requires_confirmation=True,
        ), None

    return None, f"unsupported_function:{name}"


def validate_payload(obj):
    errors = []
    if not isinstance(obj, dict):
        return ["root must be object"]
    if obj.get("type") != "android_intent":
        errors.append("type must be android_intent")
    intent_obj = obj.get("intent")
    if not isinstance(intent_obj, dict):
        return errors + ["intent must be object"]
    action = intent_obj.get("action")
    if not isinstance(action, str) or not action.strip():
        errors.append("intent.action must be non-blank string")
    for field in ("data", "package"):
        if field in intent_obj and intent_obj[field] is not None and not isinstance(intent_obj[field], str):
            errors.append(f"intent.{field} must be string or null")
    extras = intent_obj.get("extras", {})
    if extras is None:
        extras = {}
    if not isinstance(extras, dict):
        errors.append("intent.extras must be object or null")
    elif not primitive_dict(extras):
        errors.append("extras must contain only primitive string/bool/int/float values")
    flags = intent_obj.get("flags", [])
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
        elif "requires_confirmation" in safety and type(safety["requires_confirmation"]) is not bool:
            errors.append("safety.requires_confirmation must be bool")
        elif "risk" in safety and type(safety["risk"]) is not str:
            errors.append("safety.risk must be string")
    return errors


def record(prompt, payload):
    return {
        "prompt": [{"role": "user", "content": f"{SYSTEM_INSTRUCTION}\n\nUser request: {prompt}"}],
        "completion": [{"role": "assistant", "content": json.dumps(payload, separators=(",", ":"))}],
    }


def build(args):
    raw_path = Path(args.raw_parquet)
    download_if_missing(raw_path)

    df = pd.read_parquet(raw_path)
    rows = []
    drops = Counter()
    actions = Counter()
    examples_by_action = defaultdict(list)

    for source_index, item in enumerate(df.to_dict("records")):
        messages = item["messages"]
        call, parse_error = parse_single_call(assistant_content(messages))
        if parse_error:
            drops[parse_error] += 1
            continue

        payload, map_error = map_call(call)
        if map_error:
            drops[map_error] += 1
            continue

        validation_errors = validate_payload(payload)
        if validation_errors:
            drops[f"validation:{validation_errors[0]}"] += 1
            continue

        output = record(user_query(messages), payload)
        output["source"] = {
            "dataset": "mllmTeam/DroidCall",
            "split": "train",
            "row_index": source_index,
            "function": call["name"],
        }
        rows.append(output)
        action = payload["intent"]["action"]
        actions[action] += 1
        if len(examples_by_action[action]) < 3:
            examples_by_action[action].append(output)

    random.Random(args.seed).shuffle(rows)
    eval_count = min(args.eval_size, max(1, len(rows) // 10))
    eval_rows = rows[:eval_count]
    train_rows = rows[eval_count:]

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    write_jsonl(Path(args.out_dir) / "train.jsonl", train_rows)
    write_jsonl(Path(args.out_dir) / "eval.jsonl", eval_rows)

    sample_rows = rows[: min(args.sample_size, len(rows))]
    write_jsonl(Path(args.out_dir) / "sample.jsonl", sample_rows)

    report = {
        "source_rows": len(df),
        "generated_rows": len(rows),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "drop_reasons": drops.most_common(),
        "actions": actions.most_common(),
        "examples_by_action": examples_by_action,
    }
    (Path(args.out_dir) / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("source_rows", "generated_rows", "train_rows", "eval_rows")}, indent=2))
    print("Top drop reasons:", drops.most_common(12))
    print("Actions:", actions.most_common())


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-parquet", default="data/raw/droidcall_train.parquet")
    parser.add_argument("--out-dir", default="data/sft/droidcall_android_intents")
    parser.add_argument("--eval-size", type=int, default=200)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    build(parser.parse_args())


if __name__ == "__main__":
    main()

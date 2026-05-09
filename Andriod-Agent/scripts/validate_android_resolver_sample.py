#!/usr/bin/env python3
import argparse
import json
import random
import shlex
import subprocess
from collections import Counter
from pathlib import Path


def load_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            row = json.loads(line)
            payload = json.loads(row["completion"][0]["content"])
            rows.append((line_number, row, payload))
    return rows


def resolver_command(payload):
    intent = payload["intent"]
    cmd = ["adb", "shell", "cmd", "package", "resolve-activity", "--brief", "-a", intent["action"]]

    if intent.get("data"):
        cmd += ["-d", intent["data"]]

    if intent.get("package"):
        cmd += ["-p", intent["package"]]

    for key, value in (intent.get("extras") or {}).items():
        if type(value) is bool:
            cmd += ["--ez", key, str(value).lower()]
        elif type(value) is int:
            cmd += ["--ei", key, str(value)]
        elif type(value) is float:
            cmd += ["--ef", key, str(value)]
        elif type(value) is str:
            cmd += ["--es", key, value]

    return cmd


def resolve(payload, timeout):
    command = resolver_command(payload)
    remote_command = shlex.join(command[2:])
    result = subprocess.run(["adb", "shell", remote_command], text=True, capture_output=True, timeout=timeout)
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    resolved = result.returncode == 0 and "No activity found" not in output and bool(output.strip())
    return {
        "resolved": resolved,
        "returncode": result.returncode,
        "output": output,
        "command": ["adb", "shell", remote_command],
    }


def prompt_text(row):
    return row["prompt"][0]["content"].split("User request:", 1)[-1].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/sft/droidcall_android_intents/train.jsonl")
    parser.add_argument("--output", default="data/sft/droidcall_android_intents/android_resolver_100.json")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=44)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    rows = load_rows(args.input)
    sample = random.Random(args.seed).sample(rows, min(args.sample_size, len(rows)))

    results = []
    actions = Counter()
    failures = Counter()

    for line_number, row, payload in sample:
        action = payload["intent"]["action"]
        actions[action] += 1
        result = resolve(payload, args.timeout)
        if not result["resolved"]:
            failures[action] += 1
        results.append({
            "line": line_number,
            "source": row.get("source"),
            "prompt": prompt_text(row),
            "intent": payload["intent"],
            "resolved": result["resolved"],
            "resolver_output": result["output"],
        })

    report = {
        "input": args.input,
        "sample_size": len(sample),
        "seed": args.seed,
        "resolved": sum(1 for item in results if item["resolved"]),
        "unresolved": sum(1 for item in results if not item["resolved"]),
        "actions": actions.most_common(),
        "unresolved_actions": failures.most_common(),
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("sample_size", "resolved", "unresolved", "actions", "unresolved_actions")}, indent=2))


if __name__ == "__main__":
    main()

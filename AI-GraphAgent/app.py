"""Graphroom MVP: FastAPI + LangGraph around one Codex CLI loop per node."""

import asyncio
import hashlib
import json
import os
import re
import shlex
import shutil
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal, TypedDict
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).parent.resolve()
DATA = Path(os.getenv("GRAPHROOM_DATA_DIR", ROOT / "runs")).resolve()
TERMINAL = {"completed", "failed", "blocked", "cancelled"}
SANDBOX_CAPABILITIES = {
    "read-only": {"read_files", "shell_read_only"},
    "workspace-write": {"read_files", "shell", "write_workspace"},
}
RUNS, GRAPHS, TASKS, PROCESSES = {}, {}, {}, {}


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=3, max_length=4000)
    mode: Literal["simulate", "supervised"] = "simulate"
    memory_mode: Literal["ephemeral", "run_only", "permanent_proposals"] = "ephemeral"

    @field_validator("objective")
    @classmethod
    def objective_must_have_content(cls, value):
        if not value.strip():
            raise ValueError("objective cannot be blank")
        return value.strip()


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


class NodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["complete", "blocked", "failed", "pass"]
    summary: str
    artifact: str
    evidence: list[str]
    memory: list[str]
    question: str


class GraphState(TypedDict, total=False):
    route: str
    source: str


def now():
    return datetime.now(timezone.utc).isoformat()


def frontmatter(path: Path):
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"{path.relative_to(ROOT)} needs YAML frontmatter")
    _, header, body = text.split("---", 2)
    return yaml.safe_load(header) or {}, body.strip(), text


def compile_org():
    errors, warnings, sources = [], [], []
    try:
        meta, purpose, raw = frontmatter(ROOT / "ORG.md")
        sources.append(raw)
    except Exception as exc:
        return {"validation": {"errors": [str(exc)], "warnings": []}, "nodes": [], "edges": []}

    nodes = []
    for node_id, relative in (meta.get("nodes") or {}).items():
        try:
            path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError("node path leaves the project")
            node_meta, contract, raw = frontmatter(path)
            sources.append(raw)
            if node_meta.get("id") != node_id:
                errors.append(f"{relative}: id must be {node_id}")
            sandbox = node_meta.get("sandbox")
            if sandbox not in SANDBOX_CAPABILITIES:
                errors.append(f"{relative}: sandbox must be read-only or workspace-write")
            if "tools_allowed" in node_meta or "mcp_allowed" in node_meta:
                errors.append(f"{relative}: tool capabilities are derived from sandbox")
            if not node_meta.get("artifact_type"):
                errors.append(f"{relative}: artifact_type is required")
            nodes.append({
                **node_meta,
                "id": node_id,
                "file": relative,
                "contract": contract,
                "tools_allowed": sorted(SANDBOX_CAPABILITIES.get(sandbox, set())),
                "mcp_allowed": [],
                "max_attempts": int(node_meta.get("max_attempts", 1)),
                "timeout_seconds": int(node_meta.get("timeout_seconds", 180)),
            })
        except Exception as exc:
            errors.append(f"{relative}: {exc}")

    node_ids = {node["id"] for node in nodes}
    edges, edge_ids, routes = meta.get("edges") or [], set(), set()
    for edge in edges:
        edge_id, route = edge.get("id"), (edge.get("from"), edge.get("when"))
        if not edge_id or edge_id in edge_ids:
            errors.append(f"edge id {edge_id or '?'} must be unique")
        if route in routes:
            errors.append(f"edge route {route[0]} + {route[1]} must be unique")
        edge_ids.add(edge_id)
        routes.add(route)
        if edge.get("from") not in node_ids | {"approval"}:
            errors.append(f"edge {edge.get('id', '?')} has unknown source")
        if edge.get("to") not in node_ids | {"approval", "END"}:
            errors.append(f"edge {edge.get('id', '?')} has unknown target")
        if not edge.get("when"):
            errors.append(f"edge {edge.get('id', '?')} needs a condition")
        source = edge.get("from")
        allowed_conditions = {"approved", "rejected"} if source == "approval" else {"pass", "blocked", "failed"} if source == meta.get("completion_node") else {"complete", "blocked", "failed"}
        if edge.get("when") not in allowed_conditions:
            errors.append(f"edge {edge.get('id', '?')} has invalid condition for {source}")
    if meta.get("entry_node") not in node_ids:
        errors.append("entry_node must reference a node")
    if meta.get("completion_node") not in node_ids:
        errors.append("completion_node must reference a node")
    artifact_types = [node.get("artifact_type") for node in nodes if node.get("artifact_type")]
    if len(artifact_types) != len(set(artifact_types)):
        errors.append("node artifact_type values must be unique")

    return {
        "id": meta.get("id", "graphroom"),
        "name": meta.get("name", "Graphroom Org"),
        "version": str(meta.get("version", "0.1")),
        "config_hash": hashlib.sha256("".join(sources).encode()).hexdigest()[:12],
        "purpose": purpose,
        "entry_node": meta.get("entry_node"),
        "completion_node": meta.get("completion_node"),
        "nodes": nodes,
        "edges": edges,
        "policies": {
            "approval": meta.get("approval_policy", ""),
            "memory": meta.get("memory_policy", ""),
            "memory_container": meta.get("memory_container", meta.get("id", "graphroom")),
        },
        "validation": {"errors": errors, "warnings": warnings},
    }


def run_path(run_id):
    if not re.fullmatch(r"[a-f0-9]{10}", run_id):
        raise HTTPException(404, "Run not found")
    return DATA / run_id


def refresh(run):
    states = [node["state"] for node in run["nodes"]]
    run["run"]["active_count"] = sum(state in {"running", "reviewing"} for state in states)
    run["run"]["blocked_count"] = sum(state in {"blocked", "failed"} for state in states)
    run["run"]["updated_at"] = now()
    pending = [item for item in run["queues"]["approvals"] if item["status"] in {"pending", "resolving"}]
    run["run"]["risk"] = "gate" if pending else "bounded"
    if pending:
        run["run"]["next_handoff"] = f"{pending[0].get('destination_name', 'Next node')} after operator decision"
    elif run["run"]["status"] == "completed":
        run["run"]["next_handoff"] = "None — verified complete"
    elif run["run"]["status"] in TERMINAL:
        run["run"]["next_handoff"] = "Operator intervention"
    else:
        active = next((node["name"] for node in run["nodes"] if node["state"] in {"running", "reviewing"}), None)
        run["run"]["next_handoff"] = active or "Next eligible node"


def persist(run, event=None):
    folder = run_path(run["run"]["id"])
    folder.mkdir(parents=True, exist_ok=True)
    if event:
        with (folder / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    snapshot = {key: value for key, value in run.items() if key != "events"}
    temp = folder / "state.json.tmp"
    temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    temp.replace(folder / "state.json")


def emit(run, event_type, node_id=None, data=None):
    event = {
        "seq": len(run["events"]) + 1,
        "timestamp": now(),
        "run_id": run["run"]["id"],
        "node_id": node_id,
        "type": event_type,
        "data": data or {},
    }
    run["events"].append(event)
    run["run"]["last_seq"] = event["seq"]
    run["run"]["latest_event"] = event_type
    refresh(run)
    persist(run, event)
    return event


def load_run(run_id):
    if run_id in RUNS:
        return RUNS[run_id]
    folder = run_path(run_id)
    try:
        run = json.loads((folder / "state.json").read_text())
        events_file = folder / "events.jsonl"
        run["events"] = [json.loads(line) for line in events_file.read_text().splitlines()] if events_file.exists() else []
        RUNS[run_id] = run
        if run["run"]["status"] not in TERMINAL:
            run["run"]["status"] = "failed"
            for node in run["nodes"]:
                if node["state"] in {"running", "reviewing", "waiting_for_approval"}:
                    node.update(state="failed", state_reason="Server restarted; v0 checkpoints are in-process only")
            emit(run, "run.failed", data={"reason": "Server restarted; v0 checkpoint unavailable"})
        return run
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(404, "Run not found")


def projection(run, include_events=True):
    value = json.loads(json.dumps(run))
    if not include_events:
        value.pop("events", None)
    value["memory"]["configured"] = bool(os.getenv("SUPERMEMORY_API_KEY"))
    pending = any(item["status"] == "pending" for item in value["queues"]["approvals"])
    value["run"]["resumable"] = value["run"]["status"] == "waiting_for_approval" and pending and value["run"]["id"] in GRAPHS
    return value


def new_run(request: StartRun, org):
    run_id = uuid4().hex[:10]
    created = now()
    run = {
        "org": org,
        "run": {
            "id": run_id,
            "objective": request.objective,
            "mode": request.mode,
            "memory_mode": request.memory_mode,
            "status": "queued",
            "risk": "bounded",
            "created_at": created,
            "updated_at": created,
            "active_count": 0,
            "blocked_count": 0,
            "latest_event": "run.created",
            "next_handoff": org["entry_node"],
            "last_seq": 0,
            "tokens": {"input": 0, "cached_input": 0, "output": 0},
        },
        "nodes": [{
            **spec,
            "state": "ready" if spec["id"] == org["entry_node"] else "idle",
            "state_reason": "Entry node" if spec["id"] == org["entry_node"] else "Waiting for an eligible edge",
            "attempt": 0,
            "activity": "Not started",
            "thread_id": None,
            "context": {},
            "memory_reads": [],
            "memory_proposals": [],
            "artifacts": [],
            "workspace_diff": None,
        } for spec in org["nodes"]],
        "edges": [{**edge, "active": False, "last_activation": None} for edge in org["edges"]],
        "queues": {"approvals": [], "questions": [], "assumptions": [], "artifacts": []},
        "build_contract": {"status": "pending", "path": "BUILD_CONTRACT.json", "content": None, "errors": [], "last_diff": None},
        "memory": {"provider": "supermemory", "configured": False, "records": []},
        "events": [],
    }
    RUNS[run_id] = run
    emit(run, "run.started", data={"mode": request.mode, "config_hash": org["config_hash"]})
    return run


def edge_target(run, source, condition):
    return next((edge["to"] for edge in run["edges"] if edge["from"] == source and edge["when"] == condition), None)


def activate_edge(run, source, condition):
    target = edge_target(run, source, condition)
    if not target:
        return
    for edge in run["edges"]:
        edge["active"] = edge["from"] == source and edge["when"] == condition
        if edge["active"]:
            edge["last_activation"] = now()
    emit(run, "edge.activated", source if source != "approval" else None, {"from": source, "to": target, "condition": condition})


def latest_artifact(run, artifact_type):
    return next((item for item in reversed(run["queues"]["artifacts"]) if item["type"] == artifact_type), None)


def workspace_snapshot(workspace):
    snapshot = {}
    for path in sorted(workspace.rglob("*")):
        if path.is_symlink():
            content = f"symlink:{os.readlink(path)}".encode()
        elif path.is_file():
            content = path.read_bytes()
        else:
            continue
        snapshot[path.relative_to(workspace).as_posix()] = hashlib.sha256(content).hexdigest()
    return snapshot


def workspace_diff(before, after):
    return {
        "created": sorted(after.keys() - before.keys()),
        "changed": sorted(path for path in before.keys() & after.keys() if before[path] != after[path]),
        "deleted": sorted(before.keys() - after.keys()),
    }


def valid_contract_path(value):
    return isinstance(value, str) and bool(value) and not value.startswith(("/", "./")) and ".." not in Path(value).parts and value not in {".", "*", "**", "**/*", "*/**"}


def path_matches(path, patterns):
    for pattern in patterns:
        base = pattern.removesuffix("/**").rstrip("/")
        if path == base or pattern.endswith("/**") and path.startswith(base + "/"):
            return True
        if not any(mark in pattern for mark in "*?[") and path.startswith(base + "/"):
            return True
        if PurePosixPath(path).match(pattern):
            return True
    return False


def validate_build_contract(run, node_id):
    state, path = run["build_contract"], run_path(run["run"]["id"]) / "workspace" / "BUILD_CONTRACT.json"
    errors, contract = [], None
    if path.is_symlink():
        errors.append("BUILD_CONTRACT.json cannot be a symlink")
    else:
        try:
            contract = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            errors.append(f"BUILD_CONTRACT.json is missing or invalid JSON: {exc}")
    required = {"allowed_paths", "immutable_paths", "required_checks", "architecture_artifact_id"}
    if isinstance(contract, dict):
        if set(contract) != required:
            errors.append(f"BUILD_CONTRACT.json keys must be exactly {sorted(required)}")
        for key in ("allowed_paths", "immutable_paths", "required_checks"):
            if not isinstance(contract.get(key), list) or not contract[key] or not all(isinstance(item, str) and item for item in contract[key]):
                errors.append(f"{key} must be a non-empty string list")
        for key in ("allowed_paths", "immutable_paths"):
            if isinstance(contract.get(key), list) and not all(valid_contract_path(item) for item in contract[key]):
                errors.append(f"{key} contains an unsafe path or blanket glob")
        if "BUILD_CONTRACT.json" not in contract.get("immutable_paths", []):
            errors.append("immutable_paths must include BUILD_CONTRACT.json")
        architecture = latest_artifact(run, "architecture")
        if not architecture or architecture.get("status") != "approved" or contract.get("architecture_artifact_id") != architecture["id"]:
            errors.append("architecture_artifact_id must reference the approved architecture")
    elif contract is not None:
        errors.append("BUILD_CONTRACT.json must contain an object")
    state.update(status="invalid" if errors else "validated", content=contract, errors=errors)
    emit(run, "contract.invalid" if errors else "contract.validated", node_id, {"errors": errors, "contract": contract})
    return None if errors else contract


def enforce_workspace_diff(diff, contract):
    touched = diff["created"] + diff["changed"] + diff["deleted"]
    outside = sorted(path for path in touched if not path_matches(path, contract["allowed_paths"]))
    immutable = sorted(path for path in touched if path_matches(path, contract["immutable_paths"]))
    return {**diff, "outside_allowed_paths": outside, "immutable_changes": immutable, "offending": sorted(set(outside + immutable))}


async def recall_memory(run, node_id):
    if run["run"]["memory_mode"] == "ephemeral" or not os.getenv("SUPERMEMORY_API_KEY"):
        return []
    if run["run"]["mode"] == "simulate" and os.getenv("GRAPHROOM_MEMORY_IN_SIMULATE") != "1":
        return []
    try:
        from supermemory import AsyncSupermemory
        kwargs = {"api_key": os.environ["SUPERMEMORY_API_KEY"], "timeout": 10, "max_retries": 0}
        if os.getenv("SUPERMEMORY_BASE_URL"):
            kwargs["base_url"] = os.environ["SUPERMEMORY_BASE_URL"]
        async with AsyncSupermemory(**kwargs) as client:
            response = await client.search.documents(
                q=run["run"]["objective"],
                container_tag=run["org"]["policies"]["memory_container"],
                include_summary=True,
                limit=5,
            )
        memories = []
        for result in response.results:
            content = result.content or result.summary or " ".join(getattr(chunk, "content", "") for chunk in result.chunks)
            if content:
                memories.append({"content": content[:2000], "score": result.score, "source": result.document_id})
        for memory in memories:
            run["memory"]["records"].append({**memory, "scope": "graph", "reader_node": node_id, "event": "memory.read"})
        if memories:
            emit(run, "memory.read", node_id, {"count": len(memories), "provider": "supermemory"})
        return memories
    except Exception as exc:
        emit(run, "memory.provider.failed", node_id, {"provider": "supermemory", "error": str(exc)[:240]})
        return []


async def remember_verified(run):
    if run["run"]["memory_mode"] == "ephemeral":
        return
    reviewer = next(node for node in run["nodes"] if node["id"] == run["org"]["completion_node"])
    record = {
        "scope": "run" if run["run"]["memory_mode"] != "permanent_proposals" else "graph",
        "writer_node": "graph",
        "content": f"Objective: {run['run']['objective']}\nVerified outcome: {reviewer['artifacts'][-1]['summary'] if reviewer['artifacts'] else 'passed'}",
        "source_event": "review.completed",
        "status": "proposed" if run["run"]["memory_mode"] == "permanent_proposals" else "committed",
    }
    run["memory"]["records"].append(record)
    event = "memory.write.proposed" if record["status"] == "proposed" else "memory.write.committed"
    emit(run, event, data={"scope": record["scope"], "provider": "local-ledger"})


async def simulate_node(run, node, context):
    await asyncio.sleep(float(os.getenv("GRAPHROOM_SIM_DELAY", "0.2")))
    kind, workspace = node["artifact_type"], run_path(run["run"]["id"]) / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    if kind == "plan":
        return NodeResult(outcome="complete", summary="Bounded the objective into seven governed stages.", artifact="Plan: research evidence, approve one architecture, scaffold its boundaries, implement within contract, run required checks, then review independently.", evidence=["Every stage has one observable artifact and no autonomous retry."], memory=[], question="")
    if kind == "research":
        return NodeResult(outcome="complete", summary="Collected the minimum decision evidence.", artifact="Research: the existing runtime is Python and the proof can use only standard-library modules, a small src module, and unittest coverage.", evidence=["Repository and graph constraints were treated as current evidence."], memory=[], question="")
    if kind == "architecture":
        architecture = """Assumptions: local Python is available and the proof has no external service.
Smallest architecture: one src/solution.py module plus one unittest file.
Components: solution module owns behaviour; tests own observable acceptance.
Data/control flow: objective -> solution function -> asserted return value.
Interfaces/files: src/solution.py, tests/test_solution.py.
Technology: Python standard library; smallest dependency surface, no deployment layer.
Security/operations: local files only, no network, secrets, subprocesses, or external writes.
Implementation boundaries: Builder may change only src/** and tests/**.
Acceptance checks: compile src and run unittest discovery.
Unresolved questions: none."""
        return NodeResult(outcome="complete", summary="Defined a scaffold-ready minimal architecture.", artifact=architecture, evidence=["Architecture fixes files, responsibilities, boundaries, and executable checks."], memory=[], question="")
    if kind == "build_contract":
        (workspace / "src").mkdir(exist_ok=True)
        (workspace / "tests").mkdir(exist_ok=True)
        (workspace / "src" / "__init__.py").write_text("")
        architecture = latest_artifact(run, "architecture")
        contract = {
            "allowed_paths": ["src/**", "tests/**"],
            "immutable_paths": ["BUILD_CONTRACT.json"],
            "required_checks": ["python -c \"from pathlib import Path; compile(Path('src/solution.py').read_text(), 'src/solution.py', 'exec')\"", "python -B -m unittest discover -s tests"],
            "architecture_artifact_id": architecture["id"],
        }
        (workspace / "BUILD_CONTRACT.json").write_text(json.dumps(contract, indent=2) + "\n")
        return NodeResult(outcome="complete", summary="Created the minimum skeleton and binding build contract.", artifact=json.dumps(contract, indent=2), evidence=["Only src/__init__.py, tests/, and BUILD_CONTRACT.json were scaffolded."], memory=[], question="")
    if kind == "implementation":
        (workspace / "src" / "solution.py").write_text("def solve():\n    return 'GRAPHROOM_V02'\n")
        (workspace / "tests" / "test_solution.py").write_text("from unittest import TestCase\nfrom src.solution import solve\n\nclass SolutionTest(TestCase):\n    def test_result(self):\n        self.assertEqual(solve(), 'GRAPHROOM_V02')\n")
        return NodeResult(outcome="complete", summary="Implemented the approved minimal behaviour inside contract paths.", artifact="src/solution.py and tests/test_solution.py", evidence=["Created only src/solution.py and tests/test_solution.py."], memory=[], question="")
    if kind == "test_report":
        evidence, failed = [], False
        for command in run["build_contract"]["content"]["required_checks"]:
            process = await asyncio.create_subprocess_shell(command, cwd=workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            output = clip((stdout + stderr).decode(errors="replace").strip() or "no output")
            evidence.append(f"{command} -> exit {process.returncode}: {output}")
            failed = failed or process.returncode != 0
        return NodeResult(outcome="failed" if failed else "complete", summary="A required check failed." if failed else "All required checks passed.", artifact="\n".join(evidence), evidence=evidence, memory=[], question="")
    ready = run["build_contract"]["status"] == "validated" and not (run["build_contract"]["last_diff"] or {}).get("offending") and bool(latest_artifact(run, "test_report"))
    return NodeResult(outcome="pass" if ready else "blocked", summary="Implementation conforms to the approved architecture and contract." if ready else "Required verification evidence is incomplete.", artifact="PASS — architecture approval, contract, diff, and tests agree." if ready else "BLOCKED — evidence incomplete.", evidence=["Approved architecture, clean policy diff, and complete test report are present."], memory=[], question="")


def clip(value, limit=400):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


async def codex_node(run, node, context):
    run_id, node_id, attempt = run["run"]["id"], node["id"], node["attempt"]
    workspace = run_path(run_id) / "workspace"
    agent_dir = run_path(run_id) / "agents" / node_id
    workspace.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)
    schema_path, result_path = agent_dir / "result.schema.json", agent_dir / f"result-{attempt}.json"
    schema_path.write_text(json.dumps(NodeResult.model_json_schema(), indent=2))
    prompt = f"""You are the {node['name']} node inside a graph-managed agent organisation.
Codex already provides your internal observe/act/evaluate loop. Do not delegate, spawn agents, change the graph, or ask interactively.

NODE CONTRACT
{node['contract']}

CONTEXT PACKET
{json.dumps(context, ensure_ascii=False, indent=2)}

Work only inside the current node workspace and obey its sandbox. Return every schema field. Use an empty string/list when a field is unused. The graph—not you—decides routing, approvals, memory commits, and final completion.
"""
    codex = os.getenv("CODEX_BIN") or shutil.which("codex")
    if not codex:
        raise RuntimeError("codex executable not found")
    base = [codex, "--ask-for-approval", "never", "--disable", "multi_agent", "--sandbox", node.get("sandbox", "read-only"), "-c", 'shell_environment_policy.inherit="core"', "-c", "mcp_servers={}"]
    if os.getenv("CODEX_MODEL"):
        base += ["--model", os.environ["CODEX_MODEL"]]
    common = ["--json", "--output-schema", str(schema_path), "--output-last-message", str(result_path)]
    command = base + ["--cd", str(workspace), "exec", "--ignore-user-config", *common, "--skip-git-repo-check", "-"]

    child_env = os.environ.copy()
    for key in ("CODEX_THREAD_ID", "CODEX_CI", "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"):
        child_env.pop(key, None)
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=workspace,
        env=child_env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    PROCESSES[(run_id, node_id)] = process
    stderr, last_message = [], None
    raw_path = agent_dir / f"codex-{attempt}.jsonl"

    async def drain_stderr():
        async for line in process.stderr:
            stderr.append(line.decode(errors="replace").strip())

    async def consume():
        nonlocal last_message
        with raw_path.open("a") as raw_stream:
            async for line in process.stdout:
                raw_stream.write(line.decode(errors="replace"))
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type, item = raw.get("type", "unknown"), raw.get("item") or {}
                if event_type == "thread.started":
                    node["thread_id"] = raw.get("thread_id")
                if item.get("type") == "agent_message" and item.get("text"):
                    last_message = item["text"]
                if event_type == "turn.completed":
                    usage = raw.get("usage") or {}
                    tokens = run["run"]["tokens"]
                    tokens["input"] += usage.get("input_tokens", 0)
                    tokens["cached_input"] += usage.get("cached_input_tokens", 0)
                    tokens["output"] += usage.get("output_tokens", 0)
                activity = "runtime notice" if item.get("type") == "error" else item.get("type") or event_type
                node["activity"] = activity.replace("_", " ")
                data = {"codex_type": event_type, "item_type": item.get("type"), "status": item.get("status")}
                for key in ("command", "path", "text", "message"):
                    if item.get(key) and not (key == "text" and item.get("type") == "reasoning"):
                        data[key] = item[key] if key == "command" else clip(item[key])
                if item.get("exit_code") is not None:
                    data["exit_code"] = item["exit_code"]
                if item.get("aggregated_output"):
                    data["output"] = clip(item["aggregated_output"])
                if raw.get("usage"):
                    data["usage"] = raw["usage"]
                normalized = "tool.requested" if event_type == "item.started" and item.get("type") in {"command_execution", "mcp_tool_call"} else "tool.completed" if event_type == "item.completed" and item.get("type") in {"command_execution", "mcp_tool_call"} else "worker.event"
                emit(run, normalized, node_id, data)
        return await process.wait()

    stderr_task = asyncio.create_task(drain_stderr())
    consume_task = asyncio.create_task(consume())
    try:
        process.stdin.write(prompt.encode())
        await process.stdin.drain()
        process.stdin.close()
        exit_code = await asyncio.wait_for(consume_task, timeout=node["timeout_seconds"])
    except BaseException:
        await stop_process(process)
        raise
    finally:
        if not process.stdin.is_closing():
            process.stdin.close()
        await asyncio.gather(stderr_task, consume_task, return_exceptions=True)
        PROCESSES.pop((run_id, node_id), None)
    if exit_code:
        raise RuntimeError(("\n".join(stderr[-8:]) or f"Codex exited {exit_code}")[-1600:])
    raw_result = result_path.read_text() if result_path.exists() else last_message
    if not raw_result:
        raise RuntimeError("Codex returned no final node result")
    return NodeResult.model_validate_json(raw_result)


async def stop_process(process):
    if process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), 3)
    except TimeoutError:
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()


def context_packet(run, node, memories):
    def copy(value):
        return json.loads(json.dumps(value))

    artifacts = copy(run["queues"]["artifacts"])
    by_type = {item["type"]: item for item in artifacts}
    packet = {
        "node": {key: node.get(key) for key in ("id", "role", "description", "artifact_type", "sandbox", "tools_allowed", "memory_read_scope", "stop_conditions")},
        "attempt": node["attempt"],
        "graph_limits": {"max_attempts": node["max_attempts"], "timeout_seconds": node["timeout_seconds"]},
        "prior_artifacts": artifacts,
        "verified_memory": copy(memories),
        "approval_policy": run["org"]["policies"]["approval"],
    }
    if node["artifact_type"] != "build_contract":
        packet["objective"] = run["run"]["objective"]
    kind = node["artifact_type"]
    if kind in {"research", "architecture"}:
        packet["plan"] = by_type.get("plan")
    if kind == "architecture":
        packet["research"] = by_type.get("research")
    if kind in {"build_contract", "implementation", "test_report", "verdict"}:
        packet["approved_architecture"] = by_type.get("architecture")
        packet["architecture_approval"] = copy(next((item for item in reversed(run["queues"]["approvals"]) if item.get("artifact_id") == (by_type.get("architecture") or {}).get("id")), None))
    if kind in {"implementation", "test_report", "verdict"}:
        packet["build_contract"] = copy(run["build_contract"]["content"])
    if kind in {"test_report", "verdict"}:
        packet["implementation"] = by_type.get("implementation")
        packet["builder_diff"] = copy(run["build_contract"]["last_diff"])
    if kind == "verdict":
        packet["approval_history"] = copy(run["queues"]["approvals"])
        packet["test_report"] = by_type.get("test_report")
    return packet


async def execute_node(run_id, node_id, state):
    run = load_run(run_id)
    node = next(item for item in run["nodes"] if item["id"] == node_id)
    if node["attempt"] >= node["max_attempts"]:
        node.update(state="failed", state_reason="Attempt limit reached")
        emit(run, "budget.exceeded", node_id, {"kind": "attempts", "limit": node["max_attempts"]})
        return {"route": "failed", "source": node_id}
    kind, workspace = node["artifact_type"], run_path(run_id) / "workspace"
    if kind == "implementation" and run["build_contract"]["status"] != "validated":
        node.update(state="failed", state_reason="Builder requires a validated BUILD_CONTRACT.json", activity="Blocked by contract")
        emit(run, "contract.invalid", node_id, {"errors": [node["state_reason"]]})
        return {"route": "failed", "source": node_id}
    before = workspace_snapshot(workspace) if kind == "implementation" else None
    node["attempt"] += 1
    node.update(state="reviewing" if node_id == run["org"]["completion_node"] else "running", state_reason=f"Attempt {node['attempt']} is active", activity="Assembling context")
    run["run"]["status"] = "running"
    emit(run, "node.activated", node_id, {"attempt": node["attempt"], "thread_id": node.get("thread_id")})
    memories = await recall_memory(run, node_id) if node.get("memory_read_scope") else []
    context = context_packet(run, node, memories)
    node["context"], node["memory_reads"] = context, memories
    emit(run, "node.loop.started", node_id, {"attempt": node["attempt"]})
    try:
        result = await (simulate_node(run, node, context) if run["run"]["mode"] == "simulate" else codex_node(run, node, context))
    except asyncio.CancelledError:
        node.update(state="cancelled", state_reason="Run cancelled")
        raise
    except Exception as exc:
        if before is not None and run["run"]["status"] != "cancelled":
            diff = enforce_workspace_diff(workspace_diff(before, workspace_snapshot(workspace)), run["build_contract"]["content"])
            node["workspace_diff"] = run["build_contract"]["last_diff"] = diff
            if diff["offending"]:
                emit(run, "policy.violation", node_id, {"offending_paths": diff["offending"], "diff": diff})
        node.update(state="failed", state_reason=str(exc)[:500], activity="Failed")
        emit(run, "node.state.changed", node_id, {"state": "failed", "reason": node["state_reason"]})
        return {"route": "failed", "source": node_id}

    allowed = {"pass", "blocked", "failed"} if node_id == run["org"]["completion_node"] else {"complete", "blocked", "failed"}
    if result.outcome not in allowed:
        result = result.model_copy(update={"outcome": "failed", "summary": f"Invalid outcome for {node_id}: {result.outcome}"})
    if result.outcome in {"complete", "pass"} and (not result.artifact.strip() or not result.evidence):
        result = result.model_copy(update={"outcome": "failed", "summary": "Completion requires an artifact and evidence."})
    if kind == "build_contract":
        contract = validate_build_contract(run, node_id)
        if contract:
            result = result.model_copy(update={"artifact": json.dumps(contract, indent=2), "evidence": [*result.evidence, "Runtime validated BUILD_CONTRACT.json against the approved architecture."]})
        else:
            result = result.model_copy(update={"outcome": "failed", "summary": "; ".join(run["build_contract"]["errors"])})
    if kind == "implementation":
        diff = enforce_workspace_diff(workspace_diff(before, workspace_snapshot(workspace)), run["build_contract"]["content"])
        node["workspace_diff"] = run["build_contract"]["last_diff"] = diff
        result = result.model_copy(update={"evidence": [*result.evidence, f"Runtime-verified workspace diff: {json.dumps(diff, sort_keys=True)}"]})
        emit(run, "workspace.diff.verified", node_id, diff)
        if diff["offending"]:
            emit(run, "policy.violation", node_id, {"offending_paths": diff["offending"], "diff": diff})
            result = result.model_copy(update={"outcome": "blocked", "summary": f"Builder changed paths outside the build contract: {', '.join(diff['offending'])}"})
    if kind == "test_report" and result.outcome == "complete":
        required = run["build_contract"]["content"]["required_checks"]
        if run["run"]["mode"] == "simulate":
            report = "\n".join([result.artifact, *result.evidence])
            missing, failed = [check for check in required if check not in report], []
        else:
            executed = []
            for event in run["events"]:
                data = event["data"]
                if event["node_id"] == node_id and event["type"] == "tool.completed" and data.get("exit_code") is not None:
                    with suppress(ValueError):
                        parts = shlex.split(data.get("command", ""))
                        if len(parts) == 3 and parts[1] == "-lc":
                            executed.append((parts[2], data["exit_code"]))
            missing, failed = [], []
            for check in required:
                match = next((item for item in executed if item[0] == check), None)
                if not match:
                    missing.append(check)
                else:
                    executed.remove(match)
                    if match[1] != 0:
                        failed.append(check)
        if missing or failed:
            detail = [*(f"not observed: {check}" for check in missing), *(f"exit nonzero: {check}" for check in failed)]
            result = result.model_copy(update={"outcome": "failed", "summary": f"Required check verification failed: {'; '.join(detail)}"})
    if result.artifact:
        artifact = {
            "id": f"{node_id}-{node['attempt']}",
            "node_id": node_id,
            "type": kind,
            "summary": result.summary,
            "content": result.artifact,
            "evidence": result.evidence,
            "status": "verified" if result.outcome == "pass" else "unreviewed",
        }
        if kind == "implementation":
            artifact["workspace_diff"] = node["workspace_diff"]
        node["artifacts"].append(artifact)
        run["queues"]["artifacts"].append(artifact)
        emit(run, "artifact.created", node_id, {"artifact_id": artifact["id"], "type": artifact["type"]})
    if node.get("memory_write_scope") and run["run"]["memory_mode"] != "ephemeral":
        for content in result.memory:
            proposal = {"writer_node": node_id, "content": content, "scope": "run_proposal", "status": "proposed"}
            node["memory_proposals"].append(proposal)
            emit(run, "memory.write.proposed", node_id, proposal)
    if result.question:
        question = {"id": f"q-{uuid4().hex[:6]}", "node_id": node_id, "text": result.question, "blocking": result.outcome == "blocked", "status": "open"}
        run["queues"]["questions"].append(question)
        emit(run, "question.raised", node_id, question)
    node.update(
        state="completed" if result.outcome in {"complete", "pass"} else result.outcome,
        state_reason=result.summary,
        activity=f"Returned {result.outcome}",
    )
    if node_id == run["org"]["completion_node"]:
        emit(run, "review.completed", node_id, {"verdict": result.outcome, "summary": result.summary})
        if result.outcome == "pass":
            implementation = latest_artifact(run, "implementation")
            if implementation:
                implementation.update(status="verified", reviewed_by=node_id)
                emit(run, "artifact.verified", node_id, {"artifact_id": implementation["id"]})
    emit(run, "node.loop.completed", node_id, {"attempt": node["attempt"], "outcome": result.outcome, "summary": result.summary})
    activate_edge(run, node_id, result.outcome)
    return {"route": result.outcome, "source": node_id}


async def approval_node(run_id, state):
    run = load_run(run_id)
    source = state.get("source")
    source_node = next((node for node in run["nodes"] if node["id"] == source), None)
    if not source_node:
        return {"route": "failed", "source": "approval"}
    source_artifact = latest_artifact(run, source_node["artifact_type"])
    destination_id = edge_target(run, "approval", "approved")
    destination = next((node for node in run["nodes"] if node["id"] == destination_id), None)
    if not source_artifact or not destination:
        return {"route": "failed", "source": "approval"}
    approval_id = f"approval-{run_id}-{source}-{source_node['attempt']}"
    approval = next((item for item in run["queues"]["approvals"] if item["id"] == approval_id), None)
    if not approval:
        approval = {
            "id": approval_id,
            "node_id": source,
            "source_node_id": source,
            "destination_node_id": destination_id,
            "destination_name": destination["name"],
            "artifact_id": source_artifact["id"],
            "title": f"Approve {source_node['name']} {source_node['artifact_type']} for {destination['name']}",
            "policy": run["org"]["policies"]["approval"],
            "risk": "bounded handoff",
            "impact": f"Approval releases {source_artifact['id']} to {destination['name']} within its declared boundaries; rejection ends the run blocked.",
            "status": "pending",
            "options": ["approve", "reject"],
            "created_at": now(),
        }
        run["queues"]["approvals"].append(approval)
        source_node.update(state="waiting_for_approval", state_reason=approval["policy"])
        run["run"]["status"] = "waiting_for_approval"
        emit(run, "approval.requested", source, {"approval_id": approval_id, "title": approval["title"]})
    decision = interrupt({key: approval[key] for key in ("id", "title", "policy", "risk", "impact", "artifact_id", "destination_node_id", "options")})
    route = "rejected" if decision.get("decision") == "reject" else "approved"
    approval.update(status="rejected" if route == "rejected" else "approved", decision=decision, resolved_at=now())
    source_artifact.update(status="rejected" if route == "rejected" else "approved", approval_id=approval_id)
    source_node.update(state="blocked" if route == "rejected" else "completed", state_reason=f"Approval {approval['status']}")
    run["run"]["status"] = "blocked" if route == "rejected" else "running"
    emit(run, "approval.resolved", source, {"approval_id": approval_id, "decision": decision.get("decision")})
    activate_edge(run, "approval", route)
    return {"route": route, "source": "approval"}


def build_graph(run):
    builder = StateGraph(GraphState)
    node_ids = [node["id"] for node in run["nodes"]]
    for node_id in node_ids:
        async def execute(state, node_id=node_id):
            return await execute_node(run["run"]["id"], node_id, state)
        builder.add_node(node_id, execute)
    if any(edge["from"] == "approval" or edge["to"] == "approval" for edge in run["edges"]):
        async def approve(state):
            return await approval_node(run["run"]["id"], state)
        builder.add_node("approval", approve)

    grouped = {}
    for edge in run["edges"]:
        grouped.setdefault(edge["from"], []).append(edge)
    for source in node_ids + (["approval"] if "approval" in grouped else []):
        edges = grouped.get(source, [])
        if not edges:
            builder.add_edge(source, END)
            continue
        targets = {edge["when"]: END if edge["to"] == "END" else edge["to"] for edge in edges}
        targets["__end__"] = END
        allowed = set(targets)
        builder.add_conditional_edges(source, lambda state, allowed=allowed: state.get("route") if state.get("route") in allowed else "__end__", targets)
    builder.add_edge(START, run["org"]["entry_node"])
    return builder.compile(checkpointer=InMemorySaver())


async def drive(run_id, value):
    run = load_run(run_id)
    try:
        graph = GRAPHS.get(run_id)
        if not graph:
            if run["run"]["status"] == "cancelled":
                return
            raise RuntimeError("Run graph is unavailable")
        result = await graph.ainvoke(value, {"configurable": {"thread_id": run_id}, "recursion_limit": len(run["nodes"]) + 5})
        if result.get("__interrupt__"):
            return
        if run["run"]["status"] == "cancelled":
            return
        route, source = result.get("route"), result.get("source")
        if route == "pass":
            run["run"]["status"] = "completed"
            await remember_verified(run)
            emit(run, "run.completed", data={"verdict": "pass"})
        elif route in {"rejected", "blocked", "failed"}:
            run["run"]["status"] = "blocked"
            emit(run, "run.blocked", data={"reason": "Approval rejected" if route == "rejected" else route, "source": source})
        elif run["run"]["status"] not in TERMINAL:
            run["run"]["status"] = "failed"
            emit(run, "run.failed", data={"reason": route or "No eligible edge"})
    except asyncio.CancelledError:
        return
    except Exception as exc:
        if run["run"]["status"] != "cancelled":
            run["run"]["status"] = "failed"
            emit(run, "run.failed", data={"reason": str(exc)[:1000]})
    finally:
        if run["run"]["status"] in TERMINAL:
            GRAPHS.pop(run_id, None)


app = FastAPI(title="Graphroom", version="0.2.0")


@app.get("/api/health")
def health():
    return {"ok": True, "codex": bool(os.getenv("CODEX_BIN") or shutil.which("codex")), "supermemory": bool(os.getenv("SUPERMEMORY_API_KEY")), "data_namespace": hashlib.sha256(str(DATA).encode()).hexdigest()[:8]}


@app.get("/api/org")
def get_org():
    return compile_org()


@app.post("/api/runs", status_code=202)
async def start_run(request: StartRun):
    org = compile_org()
    if org["validation"]["errors"]:
        raise HTTPException(400, {"message": "ORG.md is invalid", "errors": org["validation"]["errors"]})
    if request.mode != "simulate" and not (os.getenv("CODEX_BIN") or shutil.which("codex")):
        raise HTTPException(503, "Codex CLI is required for supervised runs")
    run = new_run(request, org)
    GRAPHS[run["run"]["id"]] = build_graph(run)
    task = asyncio.create_task(drive(run["run"]["id"], {"route": "", "source": ""}))
    TASKS[run["run"]["id"]] = task
    return projection(run)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return projection(load_run(run_id))


@app.get("/api/runs/{run_id}/events")
async def run_events(request: Request, run_id: str, after: int = Query(0, ge=0)):
    run = load_run(run_id)
    header_cursor = int(request.headers.get("last-event-id", "0") or 0)
    cursor = max(after, header_cursor)

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            fresh = [event for event in run["events"] if event["seq"] > cursor]
            for event in fresh:
                cursor = event["seq"]
                payload = {"event": event, "projection": projection(run, include_events=False)}
                yield f"id: {cursor}\nevent: run_event\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            terminal_event = f"run.{run['run']['status']}"
            if run["run"]["status"] in TERMINAL and cursor >= run["run"]["last_seq"] and run["events"][-1]["type"] == terminal_event:
                break
            if not fresh:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/runs/{run_id}/approvals/{approval_id}")
async def resolve_approval(run_id: str, approval_id: str, decision: ApprovalDecision):
    run = load_run(run_id)
    approval = next((item for item in run["queues"]["approvals"] if item["id"] == approval_id), None)
    if run["run"]["status"] != "waiting_for_approval" or not approval or approval["status"] != "pending":
        raise HTTPException(409, "Approval is not pending")
    if run_id not in GRAPHS:
        raise HTTPException(409, "This v0 run cannot resume after a server restart")
    approval["status"] = "resolving"
    run["run"]["status"] = "resuming"
    emit(run, "run.resumed", data={"approval_id": approval_id})
    task = asyncio.create_task(drive(run_id, Command(resume=decision.model_dump())))
    TASKS[run_id] = task
    return projection(run)


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    run = load_run(run_id)
    if run["run"]["status"] in TERMINAL:
        return projection(run)
    run["run"]["status"] = "cancelled"
    for approval in run["queues"]["approvals"]:
        if approval["status"] in {"pending", "resolving"}:
            approval.update(status="cancelled", resolved_at=now())
    GRAPHS.pop(run_id, None)
    active = [stop_process(process) for (active_run, _), process in list(PROCESSES.items()) if active_run == run_id]
    if task := TASKS.get(run_id):
        task.cancel()
    if active:
        await asyncio.gather(*active, return_exceptions=True)
    if task:
        with suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, 4)
    for node in run["nodes"]:
        if node["state"] in {"running", "reviewing", "waiting_for_approval"}:
            node.update(state="cancelled", state_reason="Operator cancelled the run", activity="Cancelled by operator")
    emit(run, "run.cancelled")
    return projection(run)


@app.get("/")
def index():
    return FileResponse(ROOT / "prototype" / "index.html")


@app.get("/tokens.css")
def tokens():
    return FileResponse(ROOT / "tokens.css")


app.mount("/prototype", StaticFiles(directory=ROOT / "prototype", html=True), name="prototype")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))

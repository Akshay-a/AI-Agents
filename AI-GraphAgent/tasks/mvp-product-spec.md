# MVP Product Spec: Agent Org Graph Ops Room

Date: 2026-07-21

## Objective

Build the smallest product that proves this idea:

> A user can define an agent organization in Markdown, launch a task, watch the
> graph execute autonomously, inspect every active node, approve risky actions,
> and see questions, assumptions, artifacts, and memory changes as first-class
> state.

This MVP is not a general workflow builder. It is an execution room for
graph-managed autonomous loop agents.

## Primary User

An operator who wants reliable autonomous execution but does not trust hidden
chat sessions.

They care about:

- what is running,
- why it is running,
- what it can access,
- what it remembered,
- what it changed,
- what needs approval,
- what evidence proves completion.

## MVP User Workflow

1. User edits `ORG.md` and `nodes/*.md`.
2. System compiles the org graph and shows validation warnings.
3. User enters one objective.
4. System creates a run graph from the org graph.
5. Planner node wakes and produces a task plan.
6. Builder node runs bounded loop work.
7. Reviewer node checks artifact/evidence.
8. Graph pauses if approval or a blocking question is required.
9. User resolves approval/question from the UI.
10. Graph resumes and eventually completes or fails with a clear reason.

## Required Screens

### 1. Org Overview

Purpose:

- Show the configured organization before execution.

Must show:

- node list,
- edge list,
- entry node,
- approval policy,
- tool/MCP summary,
- validation errors,
- warnings for risky config.

### 2. Run Launcher

Purpose:

- Start a run from a natural-language objective.

Must show:

- selected org,
- objective input,
- run mode: simulate, supervised, autonomous,
- budget limits,
- approval strictness,
- memory mode: ephemeral, run-only, permanent proposals.

### 3. Graph Ops Room

Purpose:

- Main live execution screen.

Must show in first viewport:

- objective,
- run status,
- active node count,
- pending approvals count,
- pending questions count,
- failed/blocked count,
- cost/tokens,
- latest event,
- next expected handoff.

Layout:

```text
[Run Header]
Objective | Status | Active Nodes | Approvals | Questions | Cost | Risk

[Left Rail]          [Live Graph]                    [Inspector]
Queues               Stateful nodes                  Selected node
Nodes                Active edges                    MD contract
Approvals            Minimap                         Context packet
Questions                                             Memory/artifacts
Assumptions                                           Tool calls

[Bottom Timeline]
Events | filters | node lanes | checkpoint markers
```

### 4. Node Inspector

Purpose:

- Explain exactly what a node is, what it saw, and what it is doing.

Tabs:

- Contract: rendered `nodes/<node>.md`.
- Live: current state, loop iteration, state reason.
- Context: exact context packet provided to the node.
- Tools/MCP: allowed tools, recent calls, denied calls.
- Memory: reads, writes, proposals, provenance.
- Artifacts: produced and consumed outputs.
- Events: timeline filtered to this node.

### 5. Approval Inbox

Purpose:

- Resolve graph pauses without modal spam.

Each approval card must show:

- originating node,
- proposed action,
- policy that triggered approval,
- tool args or diff,
- risk level,
- downstream impact,
- approve/edit/reject/escalate actions,
- timeout behavior.

### 6. Questions And Assumptions

Purpose:

- Make uncertainty visible.

Each item must show:

- question or assumption,
- originating node,
- blocking or non-blocking,
- confidence,
- default assumption,
- downstream impact,
- expiry,
- answer/status.

### 7. Memory View

Purpose:

- Show graph-layered memory evolution.

Must split:

- graph memory,
- node memory,
- run memory,
- artifact memory.

Each memory record must show:

- writer node,
- source event,
- scope,
- confidence,
- temporary/permanent,
- whether approval is required,
- reverse/correct action.

### 8. Artifact Shelf

Purpose:

- Make deliverables and evidence inspectable.

Each artifact must show:

- creator node,
- source event,
- type,
- current validity,
- downstream consumers,
- review status.

## Required Runtime Objects

```text
OrgSpec
NodeSpec
EdgeSpec
Run
RunGraph
NodeRun
EdgeActivation
RunEvent
BlackboardItem
Artifact
MemoryRecord
ApprovalRequest
Question
Assumption
ToolCall
RuntimeTrace
```

## Required Node States

```text
idle
ready
running
waiting_for_child
waiting_for_approval
question_wait
blocked
failed
reviewing
completed
skipped
cancelled
```

## Required Event Types

```text
run.started
run.completed
run.failed
node.activated
node.loop.started
node.loop.completed
node.state.changed
edge.activated
tool.requested
tool.approved
tool.denied
tool.completed
approval.requested
approval.resolved
question.raised
question.answered
assumption.recorded
memory.read
memory.write.proposed
memory.write.committed
artifact.created
review.completed
budget.warning
budget.exceeded
```

## Acceptance Criteria

The MVP is credible only if all of these are true:

- `ORG.md` defines nodes and edges.
- Each node is backed by a Markdown file.
- Node Markdown includes behavior, tools, MCP access, memory policy, loop
  limits, approval triggers, and stop conditions.
- UI renders the org graph directly from the compiled Markdown.
- User can start one run from one objective.
- UI shows active node count at all times.
- UI shows exact node states and active edge activations.
- Runner can pause on approval and resume after decision.
- Runner can raise blocking and non-blocking questions.
- Assumptions are visible and tied to originating node.
- Every state transition appends to `RunEventLog`.
- Memory writes are visible and scoped.
- Graph memory and node memory are separate.
- Artifacts are linked to node and event provenance.
- Product event log is separate from LLM observability traces.
- The system can run with a local runner for learning.
- The system can swap in Inngest/Hatchet/Temporal behind `DurableRunEngine`.

## Non-Goals For MVP

- visual graph authoring,
- marketplace for agents,
- 20+ agent templates,
- autonomous org self-modification,
- production merge automation,
- enterprise RBAC,
- Kubernetes workers,
- custom vector database,
- full policy engine,
- multi-company SaaS.

## V0 Stack Recommendation

Learning build:

```text
TypeScript
local runner
events.jsonl
SQLite/JSON state
React Flow
Dagre layout
local memory ledger
OpenAI API runtime
```

Product V0:

```text
TypeScript + React
React Flow + Dagre/ELK
AG-UI-shaped SSE stream
Inngest or Hatchet as DurableRunEngine
Supermemory or Mem0 as MemoryProvider
local RunEventLog mirror
JSON/SQLite BlackboardStore
OpenTelemetry TraceSink
```

## Product Differentiator

The original product idea is not "agents in a graph." Many tools can do that.

The differentiated product is:

> A graph execution room where every autonomous loop is visible, bounded,
> auditable, memory-aware, and approval-safe.

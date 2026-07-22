# Agent Org Product Architecture Blueprint

Date: 2026-07-21

## Position

An Agent Org is an execution control plane for autonomous work.

It is not:

- a chatbot,
- a prompt library,
- a generic LangGraph canvas,
- a no-code workflow builder,
- a giant simulated company.

It is a graph-managed organization where each node owns a bounded autonomous
loop, and the graph owns state, routing, approvals, memory policy, auditability,
and completion.

## The Evolution

Loop engineering solved the behavior of one agent:

```text
observe -> decide -> act -> evaluate -> repeat
```

Graph engineering adds a coordination layer:

```text
condition -> activate node loop -> emit typed result -> update graph state ->
route to next node(s)
```

Agent Org architecture adds operating rules:

```text
role contract + tool permissions + memory scope + approval gates + event log +
human override
```

The important distinction: the node can reason, but the graph must govern.

## First-Principles Objects

### Org Graph

The stable map of the organization.

Owns:

- roles,
- nodes,
- edges,
- permissions,
- tool access,
- MCP access,
- memory scopes,
- approval policies,
- stop policies,
- escalation routes.

This should be defined by `ORG.md` and `nodes/*.md`.

### Run Graph

The per-objective execution graph.

Owns:

- active goal,
- tasks,
- dependencies,
- claimed work,
- current node states,
- active edge activations,
- generated subgraphs,
- blockers,
- questions,
- approvals,
- artifacts,
- completion verdicts.

This is generated from the org graph plus the user's current objective.

### Node

A node is a role-bound loop agent, not just a function.

Each node has:

- Markdown definition,
- role and responsibility,
- input contract,
- output contract,
- allowed tools and MCP servers,
- memory read/write policy,
- loop policy,
- budget policy,
- approval triggers,
- failure policy,
- escalation policy.

### Edge

An edge is a conditional handoff rule.

Examples:

- `Planner.complete -> Builder.ready`
- `Builder.artifact_ready -> Reviewer.ready`
- `Reviewer.rejected -> Builder.ready`
- `Any.needs_approval -> HumanApproval.waiting`
- `Any.blocked -> Supervisor.ready`

Edges should not be vague visual lines. They are executable conditions.

### Event

The event stream is the source of truth.

Every meaningful thing becomes an event:

- run started,
- node activated,
- loop iteration started,
- tool call requested,
- tool call completed,
- memory read,
- memory write proposed,
- artifact created,
- question raised,
- approval requested,
- approval resolved,
- state transition,
- retry scheduled,
- node completed,
- run completed.

The UI is a projection of this event stream.

## Core Runtime Contract

The graph kernel calls a node with a context packet:

```text
goal
node spec
current run state
allowed tools
relevant graph memory
relevant node memory
incoming artifacts
open questions
approval policy
budget remaining
```

The node returns a typed result:

```text
complete
blocked
needs_approval
question
memory_write
artifact
spawn_request
graph_change_request
failure
```

The node does not directly mutate global truth. The kernel validates the result,
records events, updates state, and activates the next edge.

## Product Components

### 1. Authoring Compiler

Turns human-readable files into runtime specs.

Inputs:

- `ORG.md`
- `nodes/planner.md`
- `nodes/builder.md`
- `nodes/reviewer.md`
- optional `memory-policy.md`
- optional `tools.md`

Outputs:

- compiled org spec,
- node specs,
- edge table,
- policy table,
- validation warnings.

### 2. Deterministic Graph Kernel

The kernel is the authority boundary.

Owns:

- scheduler,
- condition evaluator,
- state machine,
- retry policy,
- approval gate,
- event emitter,
- budget enforcement,
- completion criteria,
- replay/fork points.

Agents can suggest changes. The kernel decides whether those changes are
allowed.

### 3. Node Loop Runner

Runs one node's autonomous loop.

Loop:

```text
assemble context -> call model/runtime -> maybe call tool -> evaluate output ->
stop or continue
```

Hard limits:

- max iterations,
- max tool calls,
- max wall time,
- max tokens/cost,
- allowed tool list,
- allowed memory writes,
- required output schema.

### 4. Blackboard

The shared coordination state.

Stores:

- tasks,
- claims,
- dependencies,
- blockers,
- partial results,
- artifacts,
- current owner,
- expected next node,
- verification status.

This prevents conversation history from becoming the coordination substrate.

### 5. Event Store

V0 can be `events.jsonl`.

Later:

- SQLite read model,
- Postgres event table,
- replay API,
- branch/fork history,
- audit export.

The event store should outlive the UI and every node process.

### 6. Memory Provider

Memory is layered:

- graph memory,
- node memory,
- run memory,
- artifact memory.

Memory writes should start as proposals with provenance:

```text
writer node
source event
claim
confidence
scope
expiry
reversibility
```

The first implementation can be local JSON/SQLite. The interface should leave
room for Supermemory, Mem0, Cognee, Graphiti/Zep, or Letta-style memory blocks.

### 7. Approval Gateway

Approval is a runtime state, not a UI pop-up.

Approval requests need:

- proposed action,
- reason,
- originating node,
- policy that triggered approval,
- arguments/diff,
- blast radius,
- downstream nodes affected,
- approve/edit/reject/escalate options,
- timeout branch.

### 8. Projection API

The UI should read projected state, not write directly into runtime truth.

Feeds:

- graph state,
- node states,
- active edges,
- timeline events,
- approvals,
- questions,
- memory changes,
- artifacts,
- worker health.

### 9. Reconciler / Watchdog

Detects drift:

- node heartbeat missing,
- claimed task stale,
- approval timeout,
- loop budget exceeded,
- tool call stuck,
- graph has no runnable node but run is incomplete,
- conflicting memory writes,
- artifact missing.

## Original UI: Graph Ops Room

The product should feel like an operations room for a live agent organization.

### Run Header

Shows:

- objective,
- run status,
- elapsed time,
- cost/tokens,
- active node count,
- pending approvals,
- unresolved questions,
- risk level,
- live/replay mode.

### Center: Live Graph

Use React Flow/XyFlow as the likely V0 canvas.

Custom node surface:

- node role,
- current state ring,
- active loop step,
- last event,
- retry count,
- tool/MCP badges,
- memory delta badge,
- artifact badge,
- blocker badge.

Edges animate only when control or data is moving.

### Left Rail: Org And Queue

Contains:

- node list,
- active workers,
- approvals,
- questions,
- blockers,
- assumptions,
- saved views.

The most important product choice: approvals and questions are queues, not
modal interruptions.

### Right Inspector

For selected node:

- node Markdown contract,
- current context packet,
- current loop iteration,
- allowed tools,
- memory reads,
- memory write proposals,
- artifacts,
- logs,
- output schema,
- approval panel.

### Bottom: Event Timeline

Dense event history with:

- filters,
- Gantt lanes by node,
- structured/raw toggle,
- checkpoint markers,
- replay scrubber,
- fork-from-here action,
- failed/waiting/tool/memory/artifact/approval filters.

### Memory View

Shows:

- graph memory,
- node memory,
- run memory,
- artifact memory,
- provenance links,
- reversible writes,
- memory conflicts,
- stale memories.

### Artifacts View

Artifacts should be attached to nodes and events.

Every artifact needs:

- creator node,
- source event,
- input context,
- approval history,
- downstream consumers,
- current validity.

## Node State Model

Minimum states:

- `idle`
- `ready`
- `running`
- `waiting_for_child`
- `waiting_for_approval`
- `question_wait`
- `blocked`
- `failed`
- `reviewing`
- `completed`
- `skipped`
- `cancelled`

The graph state should always explain why a node is in its current state.

## Lean V0

Build only enough to prove the architecture.

### V0 Files

```text
ORG.md
nodes/planner.md
nodes/builder.md
nodes/reviewer.md
runs/<run_id>/events.jsonl
runs/<run_id>/state.json
runs/<run_id>/blackboard.json
runs/<run_id>/artifacts/
runs/<run_id>/memory.json
```

### V0 Nodes

- Planner: turns objective into task graph.
- Builder: executes one task loop.
- Reviewer: checks evidence and accepts/rejects.
- HumanApproval: virtual node that pauses the graph.

### V0 Flow

```text
objective -> planner -> builder -> reviewer
                         ^          |
                         | rejected |
                         +----------+

any approval trigger -> HumanApproval -> resume graph
```

### V0 Must Prove

- Parse `ORG.md` and node Markdown.
- Start a run from one objective.
- Materialize a run graph.
- Activate nodes by condition.
- Run bounded loops.
- Append `events.jsonl`.
- Store blackboard state.
- Pause for approval.
- Resume after approval.
- Show live graph, inspector, approval queue, and timeline.

### V0 Should Not Build Yet

- visual graph authoring,
- distributed workers,
- marketplace,
- nested subagent trees,
- enterprise RBAC,
- full vector memory,
- Kubernetes runtime,
- auto-merge production changes,
- 25-agent company simulation.

## Enterprise Trust Bar

An enterprise operator will ask:

- What is running right now?
- Why did this node wake up?
- What context did it see?
- What tool did it call?
- What changed?
- Who approved it?
- What memory was written?
- Can I replay it?
- Can I stop it?
- Can I fork from before the mistake?
- Can I prove the final output passed review?

The product architecture should answer these questions before it tries to feel
clever.

## North Star Architecture

```text
Human Objective
      |
      v
Authoring Compiler -----> Org Graph
      |                       |
      v                       v
Deterministic Kernel ---> Run Graph -----> Projection API -----> Graph Ops Room
      |                       |
      v                       v
 Node Loop Runner <---- Blackboard
      |
      v
 Tool/MCP Registry
      |
      v
 Events + Artifacts + Memory + Approvals
```

Core rule:

> The graph owns truth. Nodes own bounded reasoning loops. Humans own approval
> and objective changes.

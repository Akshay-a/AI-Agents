# Agent Org Product Decomposition From First Principles

Date: 2026-07-21

## Product Frame

The product is a control room for autonomous work.

The user should not feel like they are chatting with an agent. They should feel
like they are supervising a small operating system:

- define the organization,
- start a goal,
- watch the graph execute,
- inspect the active node,
- answer questions,
- approve risky actions,
- review evidence,
- replay what happened,
- improve the org definition.

The center of the product is not chat. The center is live state.

## Enterprise Job

The enterprise user is asking five questions:

- Is this real work or theater?
- What is running right now?
- Why is it running?
- What can it do without asking me?
- Where do I intervene before damage happens?

The product should answer those questions in the first viewport.

## The Core Mental Model

There are two graphs:

### 1. Org Graph

Stable structure.

This is the definition of the agent organization:

- roles,
- reporting lines,
- allowed handoffs,
- skills,
- MCP access,
- approval boundaries,
- memory scopes,
- budget rules,
- stop rules.

Source of truth:

```text
ORG.md
nodes/*.md
```

### 2. Run Graph

Live execution.

This is what the organization is doing for one objective:

- tasks,
- active node runs,
- retries,
- blockers,
- questions,
- approvals,
- artifacts,
- memory changes,
- completion verdicts.

Source of truth:

```text
runs/<run_id>/events.jsonl
runs/<run_id>/state.json
runs/<run_id>/blackboard.json
```

The UI must let users switch between:

- "What is this org configured to do?"
- "What is this org doing right now?"

## Master File: `ORG.md`

`ORG.md` is the human-editable org manifest.

It should contain:

```text
name
purpose
default_goal_template
nodes
edges
routing_conditions
global_tool_policy
global_mcp_policy
memory_policy
approval_policy
budget_policy
stop_policy
artifact_policy
ui_layout_hints
```

Example shape:

```md
---
name: lean-agent-org
version: 0.1
entry_node: planner
completion_node: reviewer
---

# Purpose

Run a bounded autonomous agent organization for one user-defined objective.

# Nodes

- planner: nodes/planner.md
- builder: nodes/builder.md
- reviewer: nodes/reviewer.md
- human-approval: virtual

# Edges

- planner.complete -> builder.ready
- builder.artifact_ready -> reviewer.ready
- reviewer.rejected -> builder.ready
- any.needs_approval -> human-approval.waiting

# Global Approval Policy

Stop before any external side effect, paid API usage above budget, filesystem
write outside run artifacts, or memory write marked permanent.
```

## Node File: `nodes/<node>.md`

Each node file is a role contract plus loop policy.

It should contain:

```text
identity
role
responsibilities
non_responsibilities
input_contract
output_contract
allowed_tools
allowed_mcp_servers
memory_read_scope
memory_write_scope
loop_policy
approval_triggers
stop_conditions
failure_policy
escalation_policy
```

This mirrors the direction of modern custom-agent formats: GitHub Copilot,
VS Code, Claude-style agents, and other tools increasingly define agents as
Markdown files with YAML frontmatter, tool access, MCP access, and instructions.

Our difference: the Markdown file is not just a prompt. It compiles into the
graph kernel's permissions and state machine.

## Runtime Components

### 1. Org Compiler

Reads `ORG.md` and `nodes/*.md`.

Outputs:

- `CompiledOrg`
- `NodeSpec[]`
- `EdgeSpec[]`
- validation errors
- UI layout hints

It should reject:

- missing node files,
- invalid edge targets,
- nodes with no output contract,
- approval policies that reference unknown tools,
- cycles without explicit loop limits,
- memory write permissions without scope.

### 2. Graph Kernel

The deterministic authority.

It owns:

- run state,
- node state,
- edge activation,
- scheduling,
- loop budgets,
- approvals,
- retries,
- event append,
- final completion.

Agents do not directly update global state. They return typed results.

### 3. Node Loop Runner

Runs one role in a bounded loop:

```text
observe state -> assemble context -> decide -> act/tool -> evaluate ->
emit typed result
```

The loop runner is replaceable. It could call:

- OpenAI API,
- Codex CLI,
- Claude Code,
- OpenClaw,
- a local model,
- a remote HTTP agent,
- a human worker.

The graph should not care. It only consumes typed node results.

### 4. Blackboard

Shared structured work state.

Stores:

- task graph,
- task claims,
- dependencies,
- blockers,
- evidence,
- artifacts,
- active owners,
- review verdicts.

This is where agents coordinate. They should not coordinate through hidden
conversation history.

### 5. Event Log

Append-only source of operational truth.

Every important transition is an event:

```text
run.started
node.activated
node.loop.started
tool.requested
tool.completed
memory.read
memory.write.proposed
approval.requested
approval.resolved
question.raised
assumption.recorded
artifact.created
edge.activated
node.completed
run.completed
```

The event log powers:

- live UI,
- audit,
- replay,
- debugging,
- timeline,
- memory projection.

### 6. Memory Layer

Memory is four different things and should not be collapsed:

- Graph memory: shared organizational/project knowledge.
- Node memory: role-specific lessons and preferences.
- Run memory: facts from this execution.
- Artifact memory: durable evidence and outputs.

Memory writes should be visible. The UI should show:

- what was written,
- by which node,
- from which event,
- to which scope,
- whether it is temporary or permanent,
- how to reverse it.

### 7. Approval Gateway

Approval is a graph state.

Approval request fields:

```text
approval_id
run_id
node_id
reason
policy
proposed_action
tool_args_or_diff
risk_level
downstream_impact
options: approve | edit | reject | escalate
timeout_behavior
```

The UI should show an approval inbox, not modal spam.

### 8. Projection API

Converts runtime truth into UI-friendly read models:

- graph nodes,
- graph edges,
- active node count,
- state counts,
- current event cursor,
- timeline groups,
- pending approvals,
- pending questions,
- memory deltas,
- artifact lineage.

The UI should not own truth. It should render truth.

## Original UI: Graph Ops Room

### First Viewport

The first screen should answer:

- current objective,
- run state,
- active nodes,
- blocked nodes,
- approvals waiting,
- questions waiting,
- latest event,
- next expected handoff.

Recommended layout:

```text
[Run Header]
Objective | State | Active Nodes | Pending Approvals | Questions | Cost | Risk

[Left Rail]          [Live Graph Canvas]             [Inspector]
Org / queues         Nodes + active edges             Selected node
Approvals            State badges                     MD contract
Questions            Execution motion                 Loop context
Assumptions          Minimap                          Tools/MCP
Blockers                                              Memory/artifacts

[Bottom Timeline]
Events | node lanes | filters | replay cursor | fork markers
```

### Node Visual Language

Each node should show:

- role name,
- state ring,
- active loop step,
- current task,
- last event,
- retry count,
- budget used,
- memory delta,
- tool/MCP icons,
- approval badge,
- question badge.

Node states:

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

### Edge Visual Language

Edges are not decoration. They are executable handoff rules.

The UI should show:

- condition label,
- last activation time,
- payload summary,
- whether the edge is currently eligible,
- animated token only when data/control is moving.

### Questions And Assumptions Queue

Questions need structure:

```text
question_id
node_id
blocking: true | false
question
default_assumption
confidence
expires_at
downstream_impact
answer
status
```

Assumptions should be visible even when they are non-blocking. This is where
the product builds trust.

### Inspector Tabs

For selected node:

- Live: current loop, current task, state reason.
- Contract: rendered `nodes/<node>.md`.
- Context: exact context packet given to the node.
- Tools: allowed tools, recent calls, pending calls.
- MCP: server access and tool scopes.
- Memory: reads, writes, proposals, provenance.
- Artifacts: outputs produced and consumed.
- Events: timeline filtered to this node.

## Product Boundaries

### Build Now

- Org graph from Markdown.
- Run graph from events.
- Three node types: planner, builder, reviewer.
- Human approval virtual node.
- Simple memory ledger.
- Approval queue.
- Live graph UI.
- Event timeline.

### Delay

- visual graph authoring,
- agent marketplace,
- complex RBAC,
- enterprise deployment matrix,
- nested self-organizing orgs,
- full semantic memory engine,
- Kubernetes execution,
- automatic production merges,
- multi-company SaaS.

## Product Principle

The product should feel less like "draw a workflow" and more like:

> I gave an autonomous organization a job, and now I can see exactly what it is
> doing, why, what it knows, where it is stuck, and what needs my decision.

# Agent Org Product Strategy

Date: 2026-07-21

## Product Thesis

An Agent Org is not a chatbot and not just a graph workflow.

It is an operating surface for autonomous work where:

- the user defines a goal,
- the system turns that goal into an execution graph,
- each node is a role-bound loop agent,
- the graph shows exactly what is active, blocked, waiting, failed, or approved,
- shared graph memory and node-local memory evolve as work progresses,
- human approval is a first-class stop condition,
- every assumption, question, artifact, and verdict is visible.

The product promise is:

> Give an enterprise user a live, inspectable organization of agents that can do
> work autonomously without becoming an invisible pile of chat transcripts.

## First Principles

### 1. Work is state, not conversation

The system should not be centered on chat history. Chat is only an input and
notification surface. The durable object is the execution graph:

- Goal
- Node
- Edge
- Task
- Run
- Artifact
- Memory
- Question
- Approval
- Verdict
- Event

If the graph cannot explain what is happening, the product fails.

### 2. Every agent needs a job description

Each node should have a markdown file because markdown is legible, versionable,
and editable by humans.

Node markdown should define:

- role and responsibility,
- behavior,
- allowed tools,
- allowed MCP servers,
- input contract,
- output contract,
- stop conditions,
- approval conditions,
- memory read policy,
- memory write policy,
- failure policy,
- escalation policy.

This gives the product a durable org chart.

### 3. The graph is the manager

Agents should not freely decide the full org structure at runtime.

The graph owns:

- which node wakes next,
- which nodes can run in parallel,
- which node owns a task,
- when to stop for approval,
- when to retry,
- when to replan,
- when to escalate,
- when the work is complete.

Agents can suggest graph changes, but the graph runner applies them only through
explicit rules.

### 4. Autonomy must be bounded

Every loop agent needs a hard boundary:

- max iterations,
- max wall-clock time,
- max tool calls,
- max spend,
- max child agents,
- allowed tool set,
- required output schema,
- stop conditions,
- approval triggers.

Autonomy without visible boundaries will not feel enterprise-grade.

### 5. Memory must be layered

There are at least four memory layers:

- Graph memory: what the org as a whole knows about this goal and project.
- Node memory: what this role has learned over time.
- Run memory: what happened during this execution.
- Artifact memory: concrete outputs, decisions, logs, files, links, diffs.

The important product decision: memory should be explainable. A node should be
able to show why it recalled something and where it came from.

### 6. Questions are first-class outputs

If a node is uncertain, it should not bury uncertainty inside prose.

Questions and assumptions need structured status:

- question text,
- originating node,
- blocking or non-blocking,
- confidence,
- default assumption,
- expiry,
- human answer,
- downstream graph impact.

This turns ambiguity into a visible queue.

## UI Concept

The UI should feel like an operations room for a living org.

Primary surfaces:

- Graph canvas: live state of nodes and edges.
- Node inspector: markdown definition, current context packet, loop state,
  memory reads/writes, tools, MCPs, approvals.
- Execution timeline: append-only event stream.
- Memory map: graph memory plus node-local memory.
- Questions/assumptions queue: what the system needs from the human.
- Artifact shelf: plans, verdicts, files, reports, traces.

The graph canvas should show:

- active nodes,
- sleeping nodes,
- blocked nodes,
- approval-waiting nodes,
- failed nodes,
- completed nodes,
- retry count,
- active edge,
- last event,
- node-local memory delta,
- graph-memory writes.

The UI should not be a static DAG editor. It should show a graph in motion.

## Master Markdown File

The master file is the org manifest.

It should define:

- org name,
- goal template,
- nodes,
- edges,
- routing rules,
- shared memory policy,
- approval policy,
- stop policy,
- runtime limits,
- UI labels,
- human handoff rules.

This file becomes the source of truth for the UI and runner.

Possible name:

- `ORG.md`
- `graph.md`
- `agent-org.md`
- `org.manifest.md`

Recommended: `ORG.md` for human clarity, with optional frontmatter or adjacent
JSON/YAML generated from it later.

## Product Components

### Authoring Layer

Purpose: define the organization.

Includes:

- `ORG.md`
- `nodes/*.md`
- `memory-policy.md`
- optional schema validation

### Runtime Layer

Purpose: execute the graph.

Includes:

- graph runner,
- loop-agent runner,
- scheduler,
- condition evaluator,
- approval gate,
- event emitter,
- retry/replan controller.

### Memory Layer

Purpose: durable context.

Includes:

- graph memory,
- node memory,
- run memory,
- memory provenance,
- retrieval interface.

### UI Layer

Purpose: make execution legible.

Includes:

- graph canvas,
- node inspector,
- event timeline,
- questions queue,
- approval panel,
- artifact viewer,
- memory map.

### Integration Layer

Purpose: tools and MCP.

Includes:

- MCP server registry,
- tool permissions,
- secrets policy,
- tool-call audit log,
- per-node tool scope.

## Enterprise Reliability Requirements

An enterprise buyer will care less about "agentic" and more about whether the
system can be trusted.

Must have:

- visible current state,
- deterministic routing,
- audit trail,
- approval gates,
- replayable runs,
- tool permission boundaries,
- memory provenance,
- human override,
- failure summaries,
- repeatable org definitions,
- easy export of what happened.

Avoid:

- opaque autonomous loops,
- infinite retries,
- hidden memory mutations,
- agents self-approving,
- unstructured "I think it's done" completions,
- graph changes with no audit.

## Initial Lean Strategy

Do not build a full enterprise platform first.

Build a local proof that demonstrates the core value:

1. A human-editable `ORG.md`.
2. Three node markdown files: Planner, Worker, Reviewer.
3. A graph runner that emits events.
4. A graph UI that shows live node status.
5. A simple memory ledger.
6. A human approval stop.

If this works, the architecture is real.

If this does not work, adding more agents will only make failure harder to see.

## Architecture Decision From Recent Repo Sweep

The recent repo search changes the build strategy.

We should not start from a generic graph workflow framework. The best current
Agent Org repos converge on a different structure:

```text
deterministic graph kernel
  owns state, routing, approvals, event log, replay, and completion

bounded loop nodes
  own local observe -> decide -> act -> evaluate cycles

visible coordination substrate
  blackboard, artifacts, task claims, dependencies, memory writes

operator UI
  live graph, timeline, approvals, memory, questions, evidence
```

The strongest inspiration set:

- `levi-qiao/graphkit`: Markdown node graph, durable ledger, clean-context
  supervisor.
- `huleidada/matterloop`: bounded recoverable loops with verification and human
  feedback.
- `ReyJ94/Sol-Orchestrator`: durable goal -> workflow -> versioned work graph.
- `uisee-ai/zaofu`: deterministic kernel, evidence gates, events, read models.
- `Vaskrokodile/parallax`: blackboard MCP, atomic task claims, dependencies,
  artifacts.
- `Mai-xiyu/wide-lens-engineering`: one canonical writer, task DAGs, capability
  probing, downgrade reasons.
- `Codesteward/codesteward`: control plane + workers + graph/tool adapters +
  gate verdict.

The lean model should combine those primitives, not clone any one repo.

## Core Object Model

Minimal objects:

- `Org`: stable definition of roles, tools, memory scopes, and allowed edges.
- `NodeSpec`: markdown-backed role and loop contract.
- `Run`: one user goal in progress.
- `RunGraph`: task/work graph generated for that run.
- `NodeRun`: one activation of a node loop.
- `EdgeActivation`: why control or data moved between nodes.
- `Event`: append-only fact about what happened.
- `Artifact`: durable output or evidence produced by a node.
- `MemoryRecord`: graph/node/run/artifact memory entry with provenance.
- `ApprovalRequest`: structured pause requiring a human decision.
- `Question`: blocking or non-blocking uncertainty surfaced by a node.

## Runtime Contract

The graph runner should be the only writer of graph truth.

Nodes may return:

- `complete`
- `blocked`
- `needs_approval`
- `question`
- `memory_write`
- `artifact`
- `spawn_request`
- `graph_change_request`
- `failure`

The runner decides whether those returned intents become actual state changes.
This preserves autonomy without letting an agent rewrite its own authority.

## V0 Kernel Boundary

V0 should stay local and boring:

- local files for `ORG.md` and `nodes/*.md`,
- `events.jsonl` for append-only runtime history,
- JSON/SQLite blackboard for current state,
- simple memory ledger first,
- React Flow UI projection,
- one process runner,
- no distributed workers,
- no nested subagents by default,
- no visual authoring until monitoring is useful.

First roles:

- Planner: converts goal into a small run graph.
- Worker: executes bounded tasks.
- Reviewer: independently verifies evidence.
- Human: approves risky state transitions.

This is enough to prove the architecture without drowning in product surface.

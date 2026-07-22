# Open-Source Layer Scorecard And Abstraction Decisions

Date: 2026-07-21

## Research Stance

The useful repos are not generic graph templates. They are control planes,
agent organizations, workflow runtimes, memory systems, and operator UIs that
answer one question:

How do autonomous agents do real work without becoming invisible, unbounded, or
un-auditable?

## Strongest Recent Agent Org References

Recent sweep window: GitHub repositories created from 2026-07-14 through
2026-07-21.

| Repo | Fit | What To Borrow | What To Avoid |
|---|---:|---|---|
| [levi-qiao/graphkit](https://github.com/levi-qiao/graphkit) | 5/5 | Markdown agent nodes, visible ledger, supervisor correction edge, red-line halt rules. | Staying stuck at two-node coding-only workflows. |
| [huleidada/matterloop](https://github.com/huleidada/matterloop) | 5/5 | Bounded plan-execute-verify-human-feedback loop, checkpoints, budgets, DAG fan-out/fan-in. | Heavy multi-package runtime before product proof. |
| [Vaskrokodile/parallax](https://github.com/Vaskrokodile/parallax) | 5/5 | Blackboard, atomic task claims, dependencies, artifacts, status view. | File locks as the long-term concurrency model. |
| [0xwilliamortiz/agents-council](https://github.com/0xwilliamortiz/agents-council) | 4/5 | Council/quorum node pattern, independent opinions, chairman synthesizer, pollable jobs. | Consensus for every task. |
| [yashneil75/gitlord](https://github.com/yashneil75/gitlord) | 4/5 | Git-backed checkpoints, branch/fork/rewind/diff mental model. | Git as the only event store for a UI-first system. |
| [Codesteward/codesteward](https://github.com/Codesteward/codesteward) | 4/5 | Specialist-reviewer-judge-gate pattern, graph-aware review, queue/workers/API/UI shape. | Building a full code-review product instead of a generic Agent Org kernel. |
| [Mai-xiyu/wide-lens-engineering](https://github.com/Mai-xiyu/wide-lens-engineering) | 4/5 | Task DAGs, isolated candidates, one canonical writer, capability probing. | Candidate explosion as default. |
| [oil-oil/codex-team-mode](https://github.com/oil-oil/codex-team-mode) | 3/5 | Simple role packets, explorer/executor/reviewer split, main-session verification. | Manual coordination as the product surface. |
| [AyushParkara/syntra](https://github.com/AyushParkara/syntra) | 3/5 | Typed state files and explicit route/cost visibility. | Narrow planner/executor/reviewer assumptions. |
| [cooco119/overlord](https://github.com/cooco119/overlord) | 3/5 | CEO/VP/manager/worker hierarchy, SQLite transitions, missions, deps, handoff files. | Tmux org theater and too many roles early. |

Re-check note:

- `uisee-ai/zaofu` and `ReyJ94/Sol-Orchestrator` appeared in the initial
  sweep notes, but were not reliably re-confirmed in the second verification
  pass. The useful patterns from those notes are still valid as design ideas:
  deterministic kernel, evidence gates, versioned run graphs, and one actor per
  job. Do not treat those two names as firm repo evidence until manually
  re-verified in GitHub.

## Broader High-Signal References

These are not all "created last week", but they are directly useful for
architecture decisions.

| Repo / Product | Layer | Borrow |
|---|---|---|
| [RoboCo](https://github.com/rennf93/roboco) / [roboco.tech](https://roboco.tech/) | Agent org control plane | Role-gated org chart, task lifecycle, isolated agent clones, QA/PR/CEO approval gates, command center. |
| [HaruHunab1320/parallax](https://github.com/HaruHunab1320/parallax) | Agent org control plane | Explicit patterns, org charts, runtime-backed execution, managed threads, event streaming, workspace/memory services. |
| [OpenAgents](https://github.com/openagents-org/openagents) | Agent network/workspace | Shared workspace, heterogeneous agent connectors, channels, files, browser, persistent work context. |
| [MassGen](https://github.com/massgen/massgen) | Consensus node | Parallel agents, live timeline, vote/convergence tracking, bounded collaboration. |
| [OpenSwarm](https://github.com/openswarm-ai/openswarm) | Local agent dashboard | Unified approvals, spatial dashboard, agent chat streams, git worktree isolation, diff viewer, cost tracking. |
| [agent-sh/agentsys](https://github.com/agent-sh/agentsys) | Skills/agent packaging | File-based agents, skills, gated phases, persistent state across sessions. |
| [open-multi-agent/open-multi-agent](https://github.com/open-multi-agent/open-multi-agent) | Task DAG runtime | Goal-to-DAG, MCP support, live tracing, small TypeScript runtime footprint. |
| [RunMaestro/Maestro](https://github.com/RunMaestro/Maestro) | Operator command center | Parallel clean sessions, responsive desktop control surface, long-running unattended execution. |
| [1mancompany/OneManCompany](https://github.com/1mancompany/OneManCompany) | Org metaphor | Browser-based company OS, hierarchical teams, human CEO framing. |

## Layer Decisions

### Agent Org Control Plane

Own this layer.

Reason:

- This is the product's core opinion.
- Existing repos either go too broad, too coding-specific, or too framework-ish.
- The valuable pattern is the authority boundary: graph kernel owns truth,
  agents own bounded reasoning.

V0 decision:

- Build a small deterministic kernel.
- Use Markdown node specs.
- Keep graph/routing/event semantics local and inspectable.

### Runtime / Durable Execution

Keep this as a replaceable port.

Good references:

- [Temporal](https://temporal.io/) for event history, deterministic workflow
  thinking, replay, child workflows.
- [Prefect](https://github.com/PrefectHQ/prefect) for states, workers, queues,
  retries, human-in-the-loop agent workflow positioning.
- [Dagster](https://github.com/dagster-io/dagster) for run details, Gantt/logs,
  asset graph, lineage.
- [Argo Workflows](https://github.com/argoproj/argo-workflows) for DAGs,
  suspend/resume, retries, artifacts, Kubernetes execution.
- [Inngest](https://github.com/inngest/inngest) for fast event-driven functions,
  retries, sleeps, `waitForEvent`-style human approval/resume flows, and
  TypeScript-friendly shipping speed.
- [Hatchet](https://github.com/hatchet-dev/hatchet) for Postgres-backed durable
  task execution, retries, event waits, and worker orchestration.

V0 decision:

- Build the first local runner only if the goal is to learn the architecture in
  the smallest possible code.
- If shipping a real product surface quickly, use Inngest behind a
  `DurableRunEngine` interface.
- If enterprise-grade multi-day execution and auditability are already required,
  use Temporal behind the same interface.
- Do not bind product semantics directly to any one workflow engine.

### Memory

Define an interface now. Keep the first implementation simple.

References:

- [Supermemory](https://github.com/supermemoryai/supermemory): fast memory/context
  API and MCP path.
- [Mem0](https://github.com/mem0ai/mem0): user/session/agent/app scoped memory.
- [Cognee](https://github.com/topoteretes/cognee): graph/vector/session memory
  and `remember`/`recall` style primitives.
- [Graphiti](https://github.com/getzep/graphiti): temporal knowledge graph with
  provenance and changing facts over time.
- [Letta](https://github.com/letta-ai/letta): editable memory blocks and
  inspectable stateful agents.

V0 decision:

- Use local memory records with explicit scope and provenance.
- Add a `MemoryProvider` interface.
- Treat memory writes as events and proposals, not silent hidden mutation.
- Keep semantic memory separate from run history. Semantic memory can merge,
  summarize, correct, and forget. Run history must stay append-only and
  auditable.

Recommended split:

- Graph memory: Graphiti/Zep-style temporal knowledge graph when provenance and
  evolving facts matter.
- Node memory: Letta-style explicit memory blocks, optionally backed by Mem0 or
  LangMem-style extraction/search.
- Run event memory: append-only event log plus workflow history.
- Approval/resume memory: durable runtime state, not semantic memory.

### UI / Operator Surface

Use React Flow/XyFlow for the graph canvas.

Borrow UI patterns from:

- [React Flow/XyFlow](https://github.com/xyflow/xyflow): custom nodes, edges,
  minimap, controls.
- [Node-RED](https://github.com/node-red/node-red): node status badges, debug
  sidebar, flow editor maturity.
- [Temporal UI](https://github.com/temporalio/ui): event history and replay
  mental model.
- [Dagster](https://github.com/dagster-io/dagster): structured/raw logs and
  run timeline.
- [Dify](https://github.com/langgenius/dify): workflow canvas, human review,
  run tracing.
- [Flowise](https://github.com/FlowiseAI/Flowise): Agentflow, shared state,
  loops, tool approval gates.
- [AutoGen Studio](https://github.com/microsoft/autogen): team composition,
  inner monologue, artifact and profiling surfaces.
- [Letta ADE](https://github.com/letta-ai/letta): memory inspection UI.

V0 decision:

- Do not build visual graph authoring first.
- Build live graph projection, inspector, event timeline, approval queue, and
  memory/artifact panels.

### Approval / Human Control

Own this abstraction.

Borrow:

- Argo suspend/resume.
- Dify human review node.
- Flowise/n8n tool-call approval gates.
- OpenSwarm unified approval queue.
- RoboCo CEO-only merge/approval framing.

V0 decision:

- `ApprovalGateway` is a runtime interface.
- Approval requests are durable events.
- UI reads an approval queue.
- Approval can approve, edit, reject, escalate, or time out.

### Worker Isolation

Start local; design for isolation.

Borrow:

- RoboCo per-agent git clones.
- OpenSwarm git worktrees.
- wide-lens isolated candidates.
- Overstory-style mailbox/worktree/watchdog idea from secondary research.
- Parallax atomic claims.

V0 decision:

- One process is acceptable.
- Each node run still gets its own run folder and context packet.
- Later move to workers, worktrees, containers, or remote sessions.

## Interfaces To Own

These abstractions should exist before choosing heavy external systems.

```text
NodeDefinitionStore
OrgCompiler
GraphStateStore
EventStore
BlackboardStore
MemoryProvider
GraphMemory
NodeMemory
RunEventLog
DurableRunEngine
ApprovalGateway
AgentRuntime
ToolRegistry
ProjectionStore
Reconciler
```

## Minimal Data Contracts

### NodeSpec

```text
id
role
description
input_schema
output_schema
tools_allowed
mcp_allowed
memory_read_scope
memory_write_scope
loop_policy
approval_policy
failure_policy
```

### EdgeSpec

```text
from_node
to_node
condition
payload_mapping
priority
```

### NodeRun

```text
run_id
node_id
state
attempt
iteration
started_at
updated_at
budget_used
last_event_id
current_context_hash
```

### Event

```text
event_id
run_id
node_id
type
timestamp
payload
causation_id
correlation_id
provenance
```

### MemoryRecord

```text
memory_id
scope
writer_node
source_event
content
confidence
valid_from
valid_until
tags
reversible
```

### DurableRunEngine

```text
start_run(spec)
signal_run(run_id, signal)
request_approval(run_id, approval_spec)
resolve_approval(approval_id, decision)
cancel_run(run_id, reason)
get_run_status(run_id)
```

## Use / Borrow / Avoid

### Use Directly In V0

- React Flow/XyFlow for graph UI.
- Local JSON/JSONL/SQLite state.
- Markdown specs.
- Simple model/tool runtime adapter.
- Inngest only if we want durable approval/resume without writing our own
  workflow runner.

### Borrow As Patterns

- RoboCo role gates.
- Deterministic-kernel and evidence-gate patterns from the recent sweep.
- Matterloop bounded loops.
- Parallax blackboard.
- Graphkit Markdown graph.
- MassGen consensus as a node type.
- Temporal event history.
- Letta memory inspection.
- Dify/Flowise approval nodes.

### Avoid For Now

- Generic LangGraph templates.
- Full no-code workflow authoring.
- Kubernetes-first runtime.
- 20+ agent company simulation.
- Autonomous graph self-modification without approval.
- Hidden memory writes.
- Chat transcript as source of truth.
- Agent-to-agent freeform communication as the main coordination protocol.

## Recommended Architecture Decision

Build a lean Agent Org kernel:

```text
ORG.md + nodes/*.md
        |
        v
Compiled Org Graph
        |
        v
Deterministic Run Graph Kernel
        |
        +--> bounded node loop runner
        +--> approval gateway
        +--> blackboard
        +--> event store
        +--> memory provider
        +--> projection API
        |
        v
Graph Ops Room UI
```

The product should be inspired by the recent Agent Org repos, but the actual
V0 should be much smaller: three real loop nodes, one approval gate, one event
stream, one memory ledger, and a live graph UI.

# Lean Implementation Layer Map

Date: 2026-07-21

## Goal

Find the smallest reliable implementation path for an Agent Org product without
hand-writing every hard subsystem.

The strategy:

- own the Agent Org semantics,
- borrow mature UI/runtime/memory primitives,
- put interfaces in front of anything likely to change,
- avoid generic graph-template gravity.

## New Search Pass

Focused searches covered:

- agent org control planes,
- agent company dashboards,
- managed agent runtimes,
- multi-agent approvals,
- graph UI libraries,
- agent UI protocols,
- memory/context engines,
- durable approval/resume engines,
- Markdown custom-agent definitions.

Useful additional references found:

- [Paperclip](https://github.com/paperclipai/paperclip)
- [Hermes Studio](https://github.com/JPeetz/Hermes-Studio)
- [AG-UI](https://github.com/ag-ui-protocol/ag-ui)
- [Microsoft Agent Framework + AG-UI demo](https://devblogs.microsoft.com/agent-framework/ag-ui-multi-agent-workflow-demo/)
- [AWS CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator)
- [Horizons](https://github.com/synth-laboratories/Horizons)
- [CORAL](https://github.com/Human-Agent-Society/CORAL)
- [Flock](https://github.com/whiteducksoftware/flock)
- [Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
- [Hatchet](https://github.com/hatchet-dev/hatchet)
- [Inngest HITL docs](https://www.inngest.com/docs/ai-patterns/human-in-the-loop)
- [Trigger.dev](https://github.com/triggerdotdev/trigger.dev)
- [Graphiti](https://github.com/getzep/graphiti)
- [Supermemory](https://github.com/supermemoryai/supermemory)
- [Mem0](https://github.com/mem0ai/mem0)
- [React Flow](https://reactflow.dev/)
- [ELK.js](https://github.com/kieler/elkjs)
- [Dagre](https://github.com/dagrejs/dagre)
- [Langfuse](https://github.com/langfuse/langfuse)
- [OpenLIT](https://github.com/openlit/openlit)
- [Node-RED node status](https://nodered.org/docs/creating-nodes/status)
- [GitHub custom agents](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-custom-agents)

## Layer 1: Agent Org Control Plane

### Best References

#### Paperclip

Why it matters:

- Most product-relevant reference found.
- Explicitly positions itself as an app for managing teams of AI agents.
- Models org charts, budgets, governance, goals, heartbeats, tasks, audit,
  workspaces, plugins, approvals, and cost control.
- Supports bring-your-own agents such as Claude Code, Codex, Cursor, Bash, and
  HTTP agents.

Borrow:

- Agent org chart with roles, titles, reporting lines, permissions, and budgets.
- Heartbeats/event triggers instead of one long blocking run.
- Task checkout and budget enforcement.
- Full activity log and action attribution.
- Goal ancestry: every task knows why it exists.
- Governance: pause, resume, terminate, approve.

Do not copy:

- Full company-management surface.
- Multi-company SaaS scope.
- Agent employee metaphor as the only UX.

Our abstraction:

```text
OrgKernel
RunKernel
AgentRegistry
BudgetPolicy
GovernancePolicy
```

#### RoboCo

Borrow:

- role-gated AI software company,
- isolated agent clones,
- QA/PR/CEO gates,
- command-center approach.

Avoid:

- starting with 25 agents.

#### Parallax

Borrow:

- control plane with explicit patterns and org charts,
- managed threads,
- runtime abstraction across local/Docker/Kubernetes,
- event streaming,
- workspace and memory services.

Avoid:

- Kubernetes/runtime breadth in V0.

#### Hermes Studio

Borrow:

- self-hosted React/TypeScript dashboard,
- multi-agent crews,
- live SSE activity feeds,
- execution approvals,
- MCP server management,
- visual workflow builder,
- audit trail,
- memory knowledge graph.

Avoid:

- tying the product to Hermes Agent.
- pure crew dashboard instead of graph-governed execution.

#### Horizons

Borrow:

- action proposal and approval flow,
- append-only audit trail,
- sandboxed execution,
- MCP configuration/call endpoints,
- event-driven orchestration,
- per-org context stores,
- DAG execution via API.

Avoid:

- multi-tenant platform breadth in V0,
- assuming RBAC enforcement is complete in early versions.

#### CORAL

Borrow:

- isolated git worktrees per agent,
- shared public state visible to all agents,
- grader/evaluator daemon,
- heartbeat prompts that force reflection or pivot,
- runtime registry for Claude Code, Codex, Cursor, OpenCode, Kiro.

Avoid:

- making evolutionary optimization the default product behavior.

## Layer 2: Markdown Agent Definition

### Best References

- GitHub custom agents.
- VS Code custom agent files.
- Claude-style subagent Markdown.

Common pattern:

- YAML frontmatter,
- Markdown body,
- description,
- tools,
- MCP servers,
- instructions,
- optional handoffs/hooks.

Our decision:

- Use Markdown as the authoring format.
- Compile Markdown into stricter runtime contracts.

Interface:

```text
NodeDefinitionStore
OrgCompiler
NodeSpecValidator
```

Minimum V0:

```text
ORG.md
nodes/planner.md
nodes/builder.md
nodes/reviewer.md
```

## Layer 3: Graph UI

### Recommended: React Flow / XyFlow

Why:

- Mature React graph canvas.
- Custom node components.
- Edges, controls, minimap, pan/zoom, selection.
- Good TypeScript fit.

Use for:

- live graph canvas,
- active edge visualization,
- custom stateful nodes,
- minimap colored by runtime state.

### Layout: ELK.js Or Dagre

Use for:

- auto-layout of `ORG.md` graphs,
- layered run-graph layout,
- refitting the graph as nodes become active, blocked, or completed.

Decision:

- Start with Dagre if implementation speed matters.
- Use ELK.js if graph layout complexity becomes visible early.

### Borrow From Node-RED

Useful pattern:

- node status is tiny, visible, and standardized.
- status has shape, color, and short text.
- debug sidebar filters events and can pause stream.

Use for:

- node state badges,
- status strip,
- timeline filters.

### Avoid For V0

- Rete.js processing engine unless we are building visual authoring.
- Langflow/Dify-style full visual builder.

Interface:

```text
ProjectionStore
GraphProjection
TimelineProjection
NodeInspectorProjection
GraphCanvasAdapter
GraphLayoutEngine
```

## Layer 4: Agent UI Event Protocol

### Recommended Pattern: AG-UI-Inspired Events

AG-UI matters because it standardizes agent-to-frontend events:

- streaming,
- tool calls,
- approvals,
- shared state,
- generative UI,
- SSE transport.

Microsoft's AG-UI multi-agent demo is especially relevant because it calls out
the exact product failure mode: when agents hand off, pause, or ask questions,
chat/terminal interfaces become opaque.

Our decision:

- Use an AG-UI-shaped event stream for the frontend.
- Do not make AG-UI the runtime truth.
- Map internal events into UI events.

Interface:

```text
RunEventLog -> UIEventStream
```

V0 events:

```text
RUN_STARTED
NODE_STARTED
NODE_STATUS_CHANGED
EDGE_ACTIVATED
TOOL_CALL_STARTED
TOOL_CALL_FINISHED
APPROVAL_REQUESTED
APPROVAL_RESOLVED
QUESTION_REQUESTED
MEMORY_DELTA
ARTIFACT_CREATED
RUN_FINISHED
```

## Layer 5: Memory

### Recommended Split

Memory must be split by purpose:

```text
GraphMemory      shared org/project knowledge
NodeMemory       role-specific memory blocks
RunEventLog      append-only operational truth
ArtifactMemory   evidence and deliverables
```

Do not let semantic memory become the audit log.

### Supermemory

Best for:

- fast product V0 memory/context,
- RAG + memory + user profiles,
- connectors,
- MCP integration,
- project/container scoping.

Use if:

- we want the fastest useful memory abstraction.

Concern:

- We still need our own memory provenance and approval policy for graph/node
  writes.

### Graphiti / Zep

Best for:

- temporal graph memory,
- provenance,
- facts that change over time,
- enterprise context graph.

Use if:

- graph-layered memory is central to the product promise.

Concern:

- More operational complexity than Supermemory.

### Mem0

Best for:

- simple user/session/agent/run scoped memory,
- TypeScript/Python SDK,
- optional graph memory,
- quick self-hosted/hosted path.

Use if:

- we want a straightforward memory adapter with `agent_id` and `run_id`.

### Cognee

Best for:

- local open-source graph memory,
- document ingestion,
- session memory improving into permanent graph memory.

Use if:

- we want an OSS graph-memory path that is less hosted-product dependent.

Interface:

```text
MemoryProvider
GraphMemory
NodeMemory
MemoryWritePolicy
MemoryProjection
```

V0 choice:

- local JSON/SQLite memory ledger for architecture learning, or
- Supermemory adapter if we want useful memory immediately.

V1 choice:

- Graphiti/Zep for temporal graph memory if provenance becomes a key product
  differentiator.

## Layer 5.5: Blackboard / Artifact Coordination

### Flock

Best for:

- typed artifact contracts,
- blackboard coordination,
- agents that publish/consume structured data,
- automatic parallelism through artifact availability,
- dashboard and trace viewer.

Important idea:

- Agents should not call each other directly.
- Agents should publish typed artifacts and subscribe to the artifacts they can
  consume.

Our decision:

- Keep an explicit graph for product legibility and governance.
- Use Flock's blackboard pattern inside the graph as the shared work state.
- Do not replace the visible graph with implicit artifact subscriptions in V0.

Interface:

```text
BlackboardStore
ArtifactRegistry
ArtifactSubscriptionIndex
ArtifactValidator
```

V0:

- simple JSON/SQLite blackboard,
- typed artifact records,
- edge conditions can inspect artifact availability.

## Layer 6: Durable Runtime / Approval Resume

### Inngest

Best for:

- fast TypeScript V0,
- human-in-the-loop wait/resume,
- step tracing,
- long-running workflows,
- replay/retrigger local dev experience.

Use if:

- we want to ship approval/resume without building durable workflow internals.

### Hatchet

Best for:

- Postgres-backed durable workflows,
- DAGs,
- task queues,
- event waits,
- retries,
- real-time dashboard.

Use if:

- we want more queue/workflow control and self-hosted Postgres simplicity.

### Temporal

Best for:

- enterprise-grade durable execution,
- strong replay model,
- multi-day workflows,
- strict audit and recovery expectations.

Use if:

- regulated or mission-critical customers are the target from day one.

### Trigger.dev

Best for:

- TypeScript-first long-running tasks,
- waits and waitpoints,
- human-in-the-loop approval points,
- run metadata and frontend-friendly monitoring.

Use if:

- Trigger.dev is already preferred in the surrounding product stack.

Concern:

- Check license and hosting fit before making it a core dependency.

Interface:

```text
DurableRunEngine
ApprovalGateway
RunScheduler
RetryPolicy
```

V0 decision:

- Build a local runner if the purpose is understanding.
- Use Inngest if the purpose is product V0.
- Use Hatchet if self-hosted Postgres-first operation matters more.
- Keep Inngest/Hatchet/Temporal/Trigger.dev replaceable behind
  `DurableRunEngine`.

## Layer 7: Worker / Agent Runtime

Supported runtime types:

```text
model_api
codex_cli
claude_code
openclaw
local_process
http_agent
human
```

Interface:

```text
AgentRuntime {
  start(nodeSpec, contextPacket)
  send(input)
  stop(reason)
  streamEvents(cursor)
  getStatus()
}
```

V0:

- one model/API runtime,
- no distributed workers,
- typed output contract.

V1:

- Codex/Claude/OpenClaw runtime adapters,
- per-node workspaces,
- heartbeats,
- recovery,
- worker pools.

### AWS CLI Agent Orchestrator

Borrow:

- supervisor-worker model,
- isolated tmux sessions,
- MCP primitives: `handoff`, `assign`, `send_message`,
- Markdown agent profiles,
- tool restrictions per agent,
- cross-provider CLI support.

Avoid:

- making tmux the product abstraction.

Additional interfaces:

```text
WorkerSessionManager
WorkerMailbox
RuntimeProfileCompiler
```

## Layer 8: Observability And Audit

Borrow from:

- Paperclip: activity and cost events,
- Hermes Studio: audit trail and tool-call timeline,
- Temporal/Dagster/Hatchet: run history and logs,
- Node-RED: debug sidebar.
- Langfuse: LLM traces, evals, prompt management, OpenTelemetry integration.
- OpenLIT: OpenTelemetry-native AI observability across LLMs, vector stores,
  guardrails, evaluations, and GPU monitoring.

Own:

```text
RunEventLog
AuditProjection
CostLedger
ArtifactLineage
```

Minimum:

- every tool call,
- every approval,
- every memory write,
- every state transition,
- every artifact.

Decision:

- Product truth stays in `RunEventLog`.
- LLM/tool traces go to `TraceSink`.
- Start with OpenTelemetry spans.
- Add Langfuse if prompt/model observability becomes important immediately.

Additional interfaces:

```text
TraceSink
OtelExporter
ModelGatewayTelemetry
EvalSink
```

## Layer 9: Governance / Policy Enforcement

### Microsoft Agent Governance Toolkit

Best for:

- policy checks before sensitive agent actions,
- zero-trust identity patterns,
- sandboxing guidance,
- reliability/governance concepts,
- fleet-level dashboards.

Use as:

- later policy-engine reference,
- not the V0 graph kernel.

Interface:

```text
PolicyEngine
ActionEvaluator
RiskClassifier
GovernanceAuditSink
```

V0:

- simple hardcoded approval policies.

V1:

- policy engine for tool calls, MCP egress, memory writes, delegation, budget,
  and high-risk external actions.

## Recommended Lean Stack

### Learning Prototype

```text
TypeScript
ORG.md + nodes/*.md
local graph kernel
events.jsonl
SQLite or JSON state
React Flow UI
local memory ledger
OpenAI API runtime
```

### Product V0

```text
TypeScript + React
React Flow graph UI
ELK/Dagre layout
AG-UI-shaped SSE events
Inngest DurableRunEngine
Supermemory MemoryProvider
JSON/SQLite BlackboardStore
local RunEventLog mirror
Markdown NodeDefinitionStore
ApprovalGateway
OpenTelemetry TraceSink
```

### Enterprise V1

```text
Temporal or Hatchet DurableRunEngine
Graphiti/Zep GraphMemory
Postgres event/audit store
worker runtime adapters
workspace isolation
RBAC and policy engine
artifact store
replay/fork UI
```

## The Code We Should Actually Write

Write only the product-specific skeleton:

```text
OrgCompiler
GraphKernel
NodeLoopContract
RunEventLog
ReplayController
ApprovalGateway
BlackboardStore
MemoryProvider interface
AgentRuntimeAdapter
TraceSink
Projection API
React Flow Graph Ops Room
```

Do not write:

- a vector database,
- a full workflow engine,
- a visual graph editor,
- a general agent framework,
- a custom MCP ecosystem,
- enterprise RBAC before product proof.

## Architecture Decision

The winning shape is:

```text
Markdown-defined organization
        |
deterministic graph kernel
        |
bounded autonomous node loops
        |
append-only operational events
        |
memory and durable runtime behind replaceable ports
        |
live original Graph Ops Room UI
```

That gives us a product that can be small in code but serious in architecture.

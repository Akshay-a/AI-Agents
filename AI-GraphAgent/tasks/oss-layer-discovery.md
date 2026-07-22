# OSS Layer Discovery For Agent Org Product

Date: 2026-07-21

Companion note:

- `tasks/recent-agent-org-repos.md` contains the corrected GitHub sweep for
  repositories created from 2026-07-14 through 2026-07-21. Use that file for
  "recent Agent Org" inspiration; this file keeps the broader layer-by-layer
  references.

## Selection Criteria

We are not looking for generic LangGraph examples.

A useful reference must help with at least one of these:

- graph-connected agent organizations,
- autonomous loop nodes,
- human approval gates,
- live graph execution UI,
- graph/shared memory,
- node-local memory,
- auditable event logs,
- worker isolation,
- task graph/dependency graph execution,
- markdown-defined agents or source-backed agent definitions.

## Layer 1: Agent Org / Runtime Orchestration

### ImL1s/oh-my-grok

Link: https://github.com/ImL1s/oh-my-grok

What it gives:

- Multi-agent orchestration around Grok Build.
- CLI-owned state, evidence stamps, accept/verified model.
- Fan-out only via `spawn_subagent`.
- Modes: `ulw`, `ralph`, `ralplan`, `pipeline`, `autopilot`.
- Separation between agent artifacts and CLI-owned truth.

Borrow:

- The orchestrator owns verification.
- Agents can propose and produce artifacts but cannot stamp final truth.
- One run directory contains state, artifacts, evidence, and report.
- Hard rule: children do not spawn children unless explicitly allowed.

Do not copy:

- Tool-specific Grok assumptions.
- The full CLI surface.

### isheng-eqi/janus-agent

Link: https://github.com/isheng-eqi/janus-agent

What it gives:

- Agent organization model: Gatekeeper -> Planner -> Worker -> Reviewer.
- Hard role boundaries.
- Review verdicts and recovery loops.
- Context discipline.

Borrow:

- Four-role minimum viable org.
- No self-approval.
- Planner and reviewer should be separate nodes.
- Original user goal should remain immutable through the graph.

Do not copy:

- Human-organization metaphor wholesale.
- Deep role hierarchy before proving basic value.

### xmonader/pirs

Link: https://github.com/xmonader/pirs

What it gives:

- Agent loop runtime.
- Tool calls, streaming, hooks, subagents, memory, code graph, and swarm-style extensions.
- Strong loop-engineering patterns.

Borrow:

- Hookable loop lifecycle.
- `should_stop` hooks.
- Tool-call audit events.
- Subagent depth and budget control.
- Code graph optional later.

Do not copy:

- Full Rust runtime.
- Large extension ecosystem.

### webmaxru/sandcastle

Link: https://github.com/webmaxru/sandcastle

What it gives:

- Planner -> Builder -> Fixer.
- Real validator drives the fixer loop.
- Per-agent activity lanes.
- Live preview and run events.

Borrow:

- Validation is a first-class node.
- Fixer loop routes from concrete issues, not vague critique.
- UI should show agent lanes and validation state.

### lyeyixian/border-collie

Link: https://github.com/lyeyixian/border-collie

What it gives:

- Orchestration loop over dispatchable tickets.
- Conditions: open, unassigned, ready label, blockers closed.
- Claims work, spawns worker in isolated worktree, waits for merge.

Borrow:

- Compute active nodes from state.
- Dispatch should be condition-driven.
- Work items need blockers/dependencies, owner, claim, attempt, and artifact.

### barkain/claude-code-workflow-orchestration

Link: https://github.com/barkain/claude-code-workflow-orchestration

What it gives:

- Hook-based delegation enforcement.
- Plan-mode decomposition into phases.
- Dependency analysis and wave scheduling.
- Isolated subagent mode or collaborative team mode.

Borrow:

- Dependency graph -> execution waves.
- Soft enforcement before hard blocking.
- Task metadata should include phase, wave, owner, dependencies.

### jonnyzzz/run-agent

Link: https://github.com/jonnyzzz/run-agent

What it gives:

- Fixed roles.
- Staged workflow.
- Append-only message bus.
- Isolated run folders with prompt, stdout, stderr, metadata.

Borrow:

- Append-only event/message bus as truth.
- Reproducible run folders.
- Structured events: FACT, PROGRESS, DECISION, REVIEW, ERROR.

## Layer 2: Memory / Context Graph

### supermemoryai/supermemory

Link: https://github.com/supermemoryai/supermemory

What it gives:

- Memory and context engine.
- API, MCP server, local mode, plugins.
- Profiles, hybrid search, documents, connectors.
- Project scoping via container tags.

Borrow/integrate:

- Use as first external memory abstraction if speed matters.
- Map graph memory and node memory to container tags.
- Use MCP/API rather than writing our own memory pipeline.

Concern:

- Need to verify how graph-native/provenance-rich it is for task/agent memory,
  not only user/profile memory.

### mem0ai/mem0

Link: https://github.com/mem0ai/mem0

What it gives:

- Universal memory layer for agents.
- User/session/agent memory.
- Optional graph memory over vector memory.
- Self-hosted SDK and hosted service.
- MCP/plugin integrations.

Borrow/integrate:

- Strong fit for graph memory plus node-local memory.
- Useful if we want self-hostable OSS memory quickly.

### getzep/graphiti

Link: https://github.com/getzep/graphiti

What it gives:

- Temporal context graph for agents.
- Entities, relationships, facts, episodes, provenance.
- Hybrid retrieval: semantic, keyword, graph traversal.
- Facts change over time without deleting history.

Borrow/integrate:

- Best conceptual match for graph-layered memory.
- Use if we want explainable memory provenance and temporal evolution.

Concern:

- More operational complexity than a simple memory API.

### letta-ai/letta

Link: https://github.com/letta-ai/letta

What it gives:

- Stateful agents with editable memory blocks.
- API and local/server modes.
- Long-running agent identity and self-improvement.

Borrow:

- Memory blocks for node-local memory.
- Agent state should be explicit and queryable.

Concern:

- It is more of an agent platform than a memory layer.

## Layer 3: Live Graph UI

### React Flow / xyflow

Link: https://reactflow.dev/

What it gives:

- Mature MIT node-based graph UI for React.
- Custom nodes as React components.
- Drag, zoom, pan, select, edges.
- Widely used in workflow builders.

Borrow/use:

- Best first choice for graph canvas.
- Each agent node can render status, active loop count, memory delta,
  approval state, and last event.

### Rete.js

Link: https://retejs.org/

What it gives:

- Visual programming editor.
- Nodes, sockets, connections, plugins, graph processing.

Borrow/use:

- Better if users need to author executable node graphs visually.

Concern:

- More editor-centric than monitoring-centric.

### Cytoscape.js

Link: https://js.cytoscape.org/

What it gives:

- Large-scale graph visualization, graph layouts, compound nodes.

Borrow/use:

- Good for memory graph visualization and dependency graph exploration.

Concern:

- Less natural for workflow-node UI controls than React Flow.

### LangGraph Studio / LangSmith Studio

Link: https://docs.langchain.com/oss/python/langgraph/studio

What it gives:

- Visualize graph architecture.
- Inspect agent steps, prompts, tool calls, state, traces.
- Time-travel style debugging.

Borrow:

- Debugging product pattern, not runtime dependency.
- Our UI should expose state, tool calls, and intermediate decisions.

## Layer 4: Durable Workflow / Human Approval Inspiration

### Prefect

Link: https://github.com/PrefectHQ/prefect

What it gives:

- State tracking, retries, recovery, UI, scheduling, task graph.

Borrow:

- State model vocabulary: Scheduled, Pending, Running, Retrying, Paused,
  Failed, Crashed, Completed.
- Retry/caching/recovery thinking.

### Dagster

Link: https://github.com/dagster-io/dagster

What it gives:

- Run UI, asset graph, event logs, lineage, blast radius.

Borrow:

- Artifact lineage and run-detail UI.
- Show what downstream nodes depend on a failed node.

### Allma

Link: https://allma.dev/

What it gives:

- AI + human orchestration.
- Durable async SOPs, approvals, external-event waits, audit-ready traces.

Borrow:

- Human steps are first-class.
- Evidence bundle and audit export are enterprise features.

### Iqonga

Link: https://iqonga.org/

What it gives:

- Multi-agent workflows with agent teams, approval steps, routers,
  sub-workflows, cron/webhook/manual triggers.

Borrow:

- Product-level workflow primitives for agent teams.
- Useful benchmark for how much UI/product surface exists in a simple full-stack app.

### SpendNod

Link: https://www.spendnod.com/

What it gives:

- Human authorization gateway via MCP.
- Rules, approval dashboard, audit trail.

Borrow:

- Approval gate as an external service/tool.
- Every risky action should become an explicit authorization request.

## Layer 5: Agent Work Management

### saltbo/agent-kanban

Link: https://github.com/saltbo/agent-kanban

What it gives:

- Agent-first task board.
- Leader decomposes goal, assigns workers, workers claim/implement/open PRs,
  leader reviews/merges.

Borrow:

- Task graph as the product substrate.
- Agent identity and claim/ownership model.

### baryhuang/claude-code-by-agents

Link: https://github.com/baryhuang/claude-code-by-agents

What it gives:

- Agentrooms UI for coordinating multiple local/remote coding agents through
  named mentions and a shared workspace backplane.

Borrow:

- Direct agent routing by name.
- Backplane concept: UI, workspace, and runtimes are separate layers.

### workforce0/workforce0

Link: https://www.workforce0.com/

What it gives:

- Product framing: meeting -> PRD -> review -> dev -> QA -> ship -> memory.
- Chief-of-staff agent with human approvals over Slack/Teams.

Borrow:

- Enterprise buyers want business workflow completion, not agent novelty.
- Human approval should happen where executives already work.

## Recommendation

For the lean first build:

- UI: React Flow.
- Memory: start with Supermemory or Mem0 adapter; keep our own memory interface.
- Temporal graph memory: design interface so Graphiti can replace/augment later.
- Runtime: custom tiny graph runner first.
- Workflow state vocabulary: borrow from Prefect.
- Event log/message bus: borrow from run-agent.
- Agent org roles: borrow from Janus and oh-my-grok.
- Approval model: copy the product shape of SpendNod/Allma, but start local.

The architectural trick is to define stable interfaces:

- `MemoryStore`
- `GraphStateStore`
- `NodeDefinitionStore`
- `ApprovalGateway`
- `EventBus`
- `AgentRuntime`
- `GraphRenderer`

Then swap implementations later.

## Updated Direction After Recent Repo Sweep

The strongest recent repos are not generic graph demos. They are control-plane
and coordination systems:

- Markdown graph nodes and ledgers (`graphkit`).
- Recoverable loop runtime with checkpoints and human feedback (`matterloop`).
- Durable goal plus versioned workflow graph (`Sol-Orchestrator`).
- Deterministic kernel plus event/read-model surfaces (`zaofu`).
- Blackboard with task claims, dependencies, updates, and artifacts
  (`parallax`).
- One canonical writer and task-DAG delegation (`wide-lens-engineering`).

Therefore our V0 should be a tiny Agent Org kernel, not a LangGraph clone:

- `ORG.md` and `nodes/*.md` define the stable org graph.
- A run creates a separate work graph.
- The graph runner is the only writer of state.
- Each node is a bounded loop.
- Every transition is emitted as an event.
- Memory and approvals are typed state, not prose buried in transcripts.
- React Flow renders the current projection of state; it does not own state.

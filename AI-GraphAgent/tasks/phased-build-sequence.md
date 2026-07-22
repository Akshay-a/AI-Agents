# Phased Build Sequence: Lean Agent Org

Date: 2026-07-21

## Principle

Build the product in slices that prove the architecture, not in framework-shaped
chunks.

Each phase should create visible user value in the Graph Ops Room.

## Phase 0: Static Org Viewer

Goal:

- Prove `ORG.md` and `nodes/*.md` can define a visible org graph.

Build:

- `ORG.md` parser.
- `nodes/*.md` parser.
- `NodeSpec` and `EdgeSpec` validation.
- React Flow static graph.
- Node inspector showing rendered Markdown.

Acceptance:

- Missing node file is caught.
- Invalid edge target is caught.
- UI shows all nodes and edges from `ORG.md`.
- Selecting a node shows its contract, tools, MCP policy, approval triggers,
  memory policy, and stop conditions.

## Phase 1: Simulated Run Graph

Goal:

- Prove the live UI state model without LLM/runtime complexity.

Build:

- `Run`.
- `RunGraph`.
- `NodeRun`.
- `RunEventLog`.
- simulated event generator.
- active node count.
- event timeline.

Acceptance:

- A run can move planner -> builder -> reviewer.
- Node states update in the graph.
- Active edge is visible when handoff occurs.
- Bottom timeline shows event sequence.
- UI can replay the simulated event stream from zero.

## Phase 2: Local Graph Kernel

Goal:

- Prove deterministic graph state transitions.

Build:

- scheduler,
- condition evaluator,
- edge activation,
- state transition reducer,
- budget counters,
- retry counters,
- completion checks.

Acceptance:

- Kernel activates nodes only when edge conditions are met.
- Kernel blocks completion when approval/question is pending.
- Kernel refuses invalid node result types.
- Every transition appends an event.

## Phase 3: Node Loop Contract

Goal:

- Prove a node can run a bounded autonomous loop and return typed output.

Build:

- `AgentRuntimeAdapter` for one model/API runtime.
- context packet assembler.
- typed node result parser/validator.
- loop policy enforcement.

Acceptance:

- Planner produces a typed task plan.
- Builder produces an artifact.
- Reviewer accepts or rejects based on artifact.
- Loop stops at max iterations/tool calls.
- Node cannot directly mutate global state.

## Phase 4: Approval Gateway

Goal:

- Prove human-in-the-loop is runtime state.

Build:

- `ApprovalRequest`.
- approval queue UI.
- pause/resume path.
- approve/edit/reject decisions.
- approval events.

Acceptance:

- Risky action creates approval request.
- Graph pauses.
- UI shows approval in inbox.
- Approval decision resumes or rejects path.
- Timeline records request and decision.

## Phase 5: Blackboard And Artifacts

Goal:

- Prove agents coordinate through typed work state.

Build:

- `BlackboardStore`.
- `ArtifactRegistry`.
- typed artifact schema.
- artifact shelf.
- artifact lineage view.

Acceptance:

- Builder writes artifact.
- Reviewer consumes artifact.
- Artifact links to creator node and source event.
- Edge conditions can inspect artifact availability.

## Phase 6: Memory Ledger

Goal:

- Prove graph memory and node memory are separate and inspectable.

Build:

- local memory ledger.
- graph memory scope.
- node memory scope.
- run memory scope.
- memory write proposal event.
- memory view.

Acceptance:

- Node can read graph memory and node memory separately.
- Node can propose memory write.
- UI shows memory provenance.
- Permanent memory write can require approval.
- Memory write does not replace event log.

## Phase 7: Product V0 Runtime Backend

Goal:

- Replace local runner durability with a real durable backend if productizing.

Options:

- Inngest for fastest TypeScript approval/resume.
- Hatchet for Postgres/self-host-first durable workflows.

Build:

- `DurableRunEngine` adapter.
- progress publishing.
- resume after approval.
- run cancellation.
- retry policy mapping.

Acceptance:

- Run survives process restart or function wait.
- Approval can resume run from backend.
- Internal workflow history is mirrored into our `RunEventLog`.
- UI still reads our product projections, not backend-specific internals.

## Phase 8: External Memory Adapter

Goal:

- Add useful context without building a memory platform.

Options:

- Supermemory for fast managed context.
- Mem0 for scoped user/agent/run memory.
- Graphiti/Zep later for temporal graph memory.

Build:

- `MemoryProvider` adapter.
- memory retrieval in context packet.
- memory write policy.
- provenance mirror in local ledger.

Acceptance:

- Context packet can include retrieved memories.
- Memory source and scope are visible.
- Memory writes still create local events.
- Adapter can be disabled without breaking run replay.

## Phase 9: Worker Runtime Adapters

Goal:

- Let graph nodes run real external agents.

Build:

- Codex CLI adapter or Claude Code adapter.
- worker session manager.
- context file injection.
- worker heartbeat.
- worker stop/cancel.

References:

- AWS CLI Agent Orchestrator for tmux/session primitives.
- OpenSwarm for local operator UI.
- CORAL/RoboCo for workspace isolation.

Acceptance:

- A node can run an external CLI worker.
- Worker events stream into `RunEventLog`.
- Worker output becomes typed node result.
- Graph can stop or cancel the worker.

## Phase 10: Enterprise Hardening

Goal:

- Move from prototype to serious internal pilot.

Build:

- Postgres event store.
- artifact store.
- audit export.
- RBAC.
- MCP allowlist.
- policy engine.
- cost ledger.
- OpenTelemetry/Langfuse trace sink.
- replay/fork UI.

Acceptance:

- Every user/action/agent has attribution.
- MCP/tool access is policy-enforced.
- Audit log can be exported.
- Cost can be grouped by run/node/provider.
- Run can be replayed from event log.

## What To Avoid During Early Phases

- Starting with enterprise RBAC.
- Starting with Kubernetes workers.
- Starting with visual authoring.
- Starting with complex semantic memory.
- Starting with many agent templates.
- Starting with a generic LangGraph canvas.

## First Coding Milestone

The first useful milestone is:

```text
Static ORG.md graph + node inspector + simulated run timeline
```

Reason:

- It proves the product surface before any LLM, memory, durable runner, or
  external agent complexity.

The second useful milestone is:

```text
Local graph kernel + three bounded node loops + approval pause/resume
```

Reason:

- It proves the Agent Org architecture.

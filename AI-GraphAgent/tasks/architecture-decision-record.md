# Architecture Decision Record: Lean Agent Org

Date: 2026-07-21

## ADR-001: Own The Graph Kernel

Decision:

- Build our own small deterministic graph kernel.

Reason:

- This is the product's core. Outsourcing it to a generic workflow/agent
  framework would make state, approvals, memory writes, and UI projection too
  opaque.

Kernel owns:

- state transitions,
- node activation,
- edge evaluation,
- approvals,
- retries,
- budgets,
- event append,
- completion.

Agents own:

- bounded reasoning loops,
- tool-use proposals,
- artifacts,
- memory-write proposals.

## ADR-002: Markdown Is The Authoring Source

Decision:

- Use `ORG.md` for the master org manifest.
- Use `nodes/*.md` for node contracts.

Reason:

- Markdown is versionable, inspectable, familiar to agent tools, and aligns
  with GitHub/VS Code/Claude-style custom-agent definitions.

Important distinction:

- Node Markdown is not just prompt text. It compiles into permissions, runtime
  policy, memory scope, and state-machine behavior.

## ADR-003: Separate Product Truth From Semantic Memory

Decision:

- `RunEventLog` is append-only product truth.
- Semantic memory is a derived context layer.

Reason:

- Memory systems summarize, merge, forget, and correct.
- Audit logs must not do that.

Implication:

- Supermemory/Mem0/Graphiti can help retrieve context.
- They must not be the only record of what happened.

## ADR-004: Use A Blackboard Inside The Graph

Decision:

- Use an explicit graph for user-visible orchestration.
- Use a typed blackboard for shared work state and artifacts.

Reason:

- Graph explains "who runs next and why."
- Blackboard explains "what evidence/artifacts exist."
- Flock is the strongest reference for typed artifact coordination, but pure
  blackboard subscriptions would hide too much of the product state.

## ADR-005: React Flow For The Graph UI

Decision:

- Use React Flow/XyFlow for the V0 graph canvas.
- Use Dagre first for auto-layout; move to ELK.js if needed.

Reason:

- React Flow is mature, TypeScript-friendly, and supports custom nodes, edges,
  minimap, controls, and live state rendering.

Avoid:

- Rete.js until visual graph authoring becomes a priority.

## ADR-006: AG-UI-Shaped Stream, Not AG-UI-Owned Runtime

Decision:

- Stream frontend events using an AG-UI-like event vocabulary.
- Keep the internal `RunEventLog` as the ordered audit history.

Reason:

- AG-UI gives a useful frontend contract for live agent state, tool calls,
  approvals, and shared state.
- Product event semantics must remain ours.

## ADR-007: Durable Runtime Behind A Port

Decision:

- Define `DurableRunEngine`.
- Local runner is acceptable for learning.
- Inngest is likely fastest for TypeScript product V0.
- Hatchet is attractive for self-hosted Postgres-first deployment.
- Temporal is V1 for enterprise durability.

Reason:

- Approval/resume and long-running execution are hard.
- We should not hand-write all workflow edge cases unless we are proving the
  architecture locally.

## ADR-008: Memory Behind Multiple Ports

Decision:

- Define separate memory interfaces:
  - `MemoryProvider`
  - `GraphMemory`
  - `NodeMemory`
  - `NodeMemoryBlockStore`

Reason:

- Graph memory, node memory, run memory, and artifact memory have different
  retention, provenance, and trust semantics.

Likely choices:

- Supermemory for fastest managed context.
- Mem0 for simple scoped memory.
- Graphiti/Zep for V1 temporal graph memory.
- Local memory ledger for V0 provenance.

## ADR-009: Runtime Adapters, Not A New Agent Framework

Decision:

- Build `AgentRuntimeAdapter`, not a full agent framework.

Supported adapters over time:

- model API,
- Codex CLI,
- Claude Code,
- OpenClaw,
- local process,
- HTTP agent,
- human worker.

Reason:

- Existing agents already have auth, tool behavior, and model-specific
  workflows. Our product coordinates them.

References:

- AWS CLI Agent Orchestrator for supervisor-worker primitives.
- OpenSwarm for operator UI and worktree/session management.
- CORAL/RoboCo for isolated workspaces.

## ADR-010: Approvals Are Runtime State

Decision:

- Approvals are durable graph states, not transient modals.

Reason:

- Enterprise operators need review queues, auditability, timeout behavior, and
  downstream impact, not interruptive popups.

Approval request must include:

- origin node,
- policy,
- proposed action,
- diff/tool args,
- risk,
- downstream impact,
- decision,
- actor,
- timestamp.

## ADR-011: Observability Is Separate From Audit

Decision:

- Product event log is the operational audit.
- OpenTelemetry/Langfuse/OpenLIT traces are debugging and model-quality
  telemetry.

Reason:

- Traces can be sampled, redacted, or vendor-specific.
- Audit must be durable and product-owned.

## ADR-012: No Generic LangGraph Template In V0

Decision:

- Do not start from a generic LangGraph demo/template.

Reason:

- The product is not "workflow with LLM nodes."
- The product is Agent Org control: Markdown contracts, graph state, memory
  provenance, approvals, events, and a live execution room.

LangGraph remains useful as a later adapter or comparison point, not the core
architecture.

Clarification after the working MVP:

- V0 uses LangGraph's low-level `StateGraph`, conditional edges, and
  `interrupt`/`Command` checkpoint as a thin in-process scheduling substrate.
- It does not use a generic agent template, prompt graph, memory abstraction, or
  UI. Graphroom still owns Markdown contracts, approval records, artifacts,
  current projection, and the audit history.
- `state.json` is the current operational projection. `events.jsonl` records
  ordered occurrences for audit; semantic memory is never used as runtime truth.

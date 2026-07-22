# Recent Agent Org Repo Sweep

Date: 2026-07-21

Search window: GitHub repositories created from 2026-07-14 through
2026-07-21.

Queries used:

- `multi-agent created:>=2026-07-14`
- `agent swarm created:>=2026-07-14`
- `subagents created:>=2026-07-14`
- `agent orchestration created:>=2026-07-14`
- `graph engineering created:>=2026-07-14`
- `loop engineering created:>=2026-07-14`
- `agent organization created:>=2026-07-14`
- `agent org created:>=2026-07-14`

Filter:

- Keep repos that expose a useful Agent Org primitive.
- Drop pure demos, obvious spam, generic LangGraph examples, and ordinary apps
  that only happen to use multiple agents.
- Keep a few low-star repos when the architecture is directly relevant.

## Shortlist

Verification note:

- Some repositories from the first sweep were found through GitHub search
  results that are not consistently re-fetchable. Treat this file as an
  architecture-pattern scratchpad, not a final vendor/reference bibliography.
- The durable product decisions are captured in
  `tasks/open-source-layer-scorecard.md`, where uncertain items are separated
  from broader verified references.

### 1. levi-qiao/graphkit

Link: https://github.com/levi-qiao/graphkit

Created: 2026-07-19

Why it matters:

- Most directly matches the user's wording: loop engineering -> graph
  engineering.
- Defines a long-running coding task as a graph of Markdown agent nodes, not a
  single loop.
- Starts with two roles: Executor and clean-context Supervisor.
- Nodes communicate through inspectable files: `ledger.md`, `directives.md`,
  `ops.md`, generated node prompts.
- No orchestration server, no framework dependency.

Borrow:

- Markdown nodes and edges as the first product primitive.
- One durable ledger as source of truth.
- Supervisor as a separate clean-context node.
- One-way correction edge from Supervisor to Executor.
- Red lines that halt the run.

Do not copy:

- Only having two roles forever.
- Coding-task-only assumptions.

Product lesson:

The graph becomes real when nodes do not share hidden context and only exchange
state through visible artifacts.

### 2. 0xwilliamortiz/agents-council

Link: https://github.com/0xwilliamortiz/agents-council

Created: 2026-07-20

Why it matters:

- Parallel council pattern using installed AI CLIs such as Codex and Gemini.
- Three-stage flow: parallel independent opinions, response collection,
  chairman synthesis.
- Has job-style direct script usage: `start`, `status`, `results`, `clean`.
- Designed to work inside host-agent UIs without turning everything into MCP.

Borrow:

- Council/quorum node pattern.
- Chairman synthesizer separate from worker opinions.
- Pollable job state instead of blocking one giant call.
- Simple config-driven members.

Do not copy:

- Treating all agents as equal voters for execution.
- Using council mode for every task.

Product lesson:

Some nodes should be consultative and non-mutating. They improve decisions but
do not write graph truth.

### 3. huleidada/matterloop

Link: https://github.com/huleidada/matterloop

Created: 2026-07-16

Why it matters:

- Explicit loop runtime: plan -> execute -> verify -> human feedback -> replan.
- Claims pause/resume, checkpoints, feedback history, revisions, budgets, tool
  limits, agent-task limits, and DAG fan-out/fan-in.
- Separates step verifier, completion evaluator, and team reviewer.
- Central orchestrator drives the DAG; agents cannot directly mutate global
  state.

Borrow:

- Loop-agent contract: planner, executor, verifier, completion evaluator.
- Checkpoint as a first-class runtime object.
- Human feedback with idempotent semantics.
- Budgets per cycle, attempt, token, cost, tool call, and agent task.
- Central orchestrator as only writer of global state.

Do not copy:

- Twelve-package modular Python system for V0.

Product lesson:

Each graph node needs a bounded loop, but loop progress must be inspectable and
recoverable.

### 4. ReyJ94/Sol-Orchestrator

Link: https://github.com/ReyJ94/Sol-Orchestrator

Created: 2026-07-15

Why it matters:

- Graph-native multi-agent harness for OpenCode.
- Durable goal can span many workflow graphs.
- Workflows have versioned graphs; graphs have steps and jobs.
- Jobs have exactly one actor: orchestrator or worker profile.
- Workers produce bounded evidence; orchestrator owns synthesis, integration,
  review, and next workflow.

Borrow:

- Separate durable goal from workflow graph.
- Versioned run graph when new evidence invalidates unfinished work.
- Job ownership and review state.
- Worker output is evidence, not automatic completion.
- TUI concept that shows goal, graph, worker state, review state, blockers, and
  actions available now.

Do not copy:

- OpenCode-specific plugin model.

Product lesson:

An Agent Org product needs both an org graph and a per-run work graph. They are
related but not the same object.

### 5. uisee-ai/zaofu

Link: https://github.com/uisee-ai/zaofu

Created: 2026-07-14

Why it matters:

- Delivery control plane for long-horizon multi-agent software delivery.
- Explicit deterministic kernel plus agent/skill layer.
- Uses contracts, evidence gates, independent verification, Thin Judge,
  completion gate, recovery loop, and operator surfaces.
- Authority is layered: kernel owns dispatch, identity, gates, replay, state
  transitions, and external effects; agents own planning, implementation,
  review, and diagnosis.
- Runtime truth is not one blob: `events.jsonl`, kernel stores, hash-addressed
  artifacts, SQLite read models.

Borrow:

- Deterministic kernel as authority boundary.
- `events.jsonl` as append-only occurrence ledger.
- Contracted multi-agent execution.
- Independent verification before completion.
- Controlled actions for human approval.
- Read-model projections for UI instead of making UI the state owner.

Do not copy:

- Full delivery platform scope.
- Multiple product surfaces in V0.

Product lesson:

The graph runner should be boring and deterministic. Agents are creative; the
kernel is not.

### 6. Vaskrokodile/parallax

Link: https://github.com/Vaskrokodile/parallax

Created: 2026-07-18

Why it matters:

- Blackboard MCP server for Claude Code and Codex subagents.
- Orchestrator creates tasks with dependencies and disjoint file scopes.
- Subagents atomically claim tasks, post updates, read upstream findings,
  register artifacts, and report done.
- File-backed state with cross-process locking.

Borrow:

- Blackboard as the shared coordination primitive.
- Atomic task claim.
- Dependency-blocked task claiming.
- Artifact registry.
- Compact `get_status` view for the UI and orchestrator.

Do not copy:

- File-lock based concurrency as the only future implementation.

Product lesson:

Parallel agents need a coordination substrate. Conversation history is not that
substrate.

### 7. yashneil75/gitlord

Link: https://github.com/yashneil75/gitlord

Created: 2026-07-16

Why it matters:

- Agent orchestration with Git-backed storage.
- Every turn is a Git commit under `refs/agents/`.
- Subagents get separate branches.
- Supports append turns, rewind, diff, branch tree, subagent drain/trim, context
  assembly, MCP lifecycle, model routing, and vector index.

Borrow:

- Rewindable and forkable run state.
- Git commits as durable checkpoints.
- Subagent branches as isolated work histories.
- CLI inspection commands: log, tree, show, rewind, diff.

Do not copy:

- Git as the only event store for a UI-first product.

Product lesson:

Reproducibility matters. A user should be able to replay, diff, or fork a run.

### 8. Codesteward/codesteward

Link: https://github.com/Codesteward/codesteward

Created: 2026-07-14

Why it matters:

- Self-hosted agentic code review product with structural code graph
  intelligence.
- Product architecture includes UI, API, Postgres state, worker queue, graph
  MCP, model router, sandbox/prove layer.
- Review pipeline: specialists -> optional discourse -> verifier -> judge ->
  noise filter -> gate verdict -> SCM publish.
- Has org policy, learning loop, job queue, and scalable workers.

Borrow:

- Specialist pipeline with verifier and judge.
- Graph intelligence exposed via MCP rather than baked into prompts.
- Product UI with live activity and session detail.
- Postgres as state of truth plus workers claiming jobs.

Do not copy:

- Code-review-only domain.
- Multi-tenant enterprise scope for V0.

Product lesson:

The scalable shape is control plane + stateless UI/API + state store + worker
pool + graph/tool adapters.

### 9. Mai-xiyu/wide-lens-engineering

Link: https://github.com/Mai-xiyu/wide-lens-engineering

Created: 2026-07-16

Why it matters:

- Codex skill for elastic agent teams, task DAGs, isolated candidates, and one
  canonical writer.
- Derives execution mode from host capabilities instead of assuming the tool
  can enforce isolation.
- Uses axes: intent, assurance, depth, coordination.
- Requires frozen scope and acceptance checks.

Borrow:

- One canonical writer.
- Capabilities audit before delegation.
- Task DAG child objectives can only narrow the parent contract.
- Execution modes: main-only, read-only proposals, isolated candidates.
- Downgrade reasons should be recorded.

Do not copy:

- Complex assurance protocol before we have the basic runner.

Product lesson:

The product must know when not to spawn agents. Coordination is a cost.

### 10. oil-oil/codex-team-mode

Link: https://github.com/oil-oil/codex-team-mode

Created: 2026-07-17

Why it matters:

- Codex skill for routing work across four focused agents:
  Explorer, Executor, Complex Executor, Reviewer.
- Main thread owns unresolved decisions and final verification.
- Every child brief has outcome, benefit, sources, scope, checks, stop
  condition, and return contract.
- Children do not spawn descendants.

Borrow:

- Four minimal role profiles.
- Dispatch packet schema.
- "Use no subagents if delegation has no positive marginal value."
- Main thread final acceptance.

Do not copy:

- Static role set as the whole product.

Product lesson:

Agent Org design should start from responsibility boundaries, not persona
names.

### 11. AyushParkara/syntra

Link: https://github.com/AyushParkara/syntra

Created: 2026-07-16

Why it matters:

- Terminal-first control plane for planner/executor/reviewer model routing.
- Stores typed state files: `task.json`, `plan.json`, `decisions.json`,
  `failures.json`, `summary.json`, `cost.json`.
- Shows route, reason, provider, and cost.

Borrow:

- Typed state artifacts instead of one chat log.
- Role-specific model routing.
- Activity/cost trace as part of normal UI.

Do not copy:

- Model-ranking product surface as the core wedge.

Product lesson:

Every node run should have a visible model route, cost, and reason.

### 12. cooco119/overlord

Link: https://github.com/cooco119/overlord

Created: 2026-07-15

Why it matters:

- tmux-based agent organization: CEO -> VP -> Manager -> Worker.
- Missions fan out into verifiable topic tasks with dependency graphs.
- SQLite guarded transitions are state; handoff files are payload.
- Has generator/evaluator loop, policy engine, reconciler, review gateway,
  traces, budgets, and escalation routing.

Borrow:

- DB state plus file payload split.
- Mission -> topic task dependency graph.
- Generator/evaluator loop.
- Reconciler for crashed or stuck tasks.
- One-way vs two-way-door approval routing.

Do not copy:

- tmux as the product runtime.
- Deep management hierarchy for V0.

Product lesson:

Long-running autonomy needs a reconciler. Runs will stall, crash, or wedge.

## Meta / Definition Repos

### ChaoYue0307/awesome-graph-engineering

Link: https://github.com/ChaoYue0307/awesome-graph-engineering

Created: 2026-07-19

Why it matters:

- Not an implementation, but a useful taxonomy for graph engineering.
- Defines the minimum test:
  - multiple independently scoped agent nodes,
  - explicit coordination semantics,
  - inspectable graph artifact.
- Distinguishes org graph from run/work graph.
- Lists nine layers: roles, topology, handoffs, work graphs, state, gates,
  reliability, observability/cost, evolution.

Borrow:

- Use this as our product vocabulary.
- Ensure our graph is load-bearing, not decorative.

### nokku-dev/nokku-ops-architecture

Link: https://github.com/nokku-dev/nokku-ops-architecture

Created: 2026-07-15

Why it matters:

- Design document for a persistent five-agent ops organization.
- Agents run on schedules and event triggers.
- Uses Dispatcher, Executor, Reviewer, Auditor, Briefer.
- Treats escalation to human as a designed normal exit, not failure.

Borrow:

- Persistent org modes: scheduled, event-triggered, weekly audit, daily brief.
- Inline evaluation through Reviewer/Auditor.
- Human decision cards as a product primitive.

## Lean Architecture Synthesis

The product should not begin as a large agent framework.

Build a small deterministic Agent Org kernel:

```text
ORG.md
  stable org graph: roles, tools, memory scopes, approval rules

nodes/*.md
  node-local loop contract: observe -> decide -> act -> evaluate -> stop

run graph
  per-goal graph: tasks, dependencies, active nodes, blockers, approvals

event log
  append-only truth: node started, edge fired, memory written, approval asked

blackboard
  task claims, updates, artifacts, dependencies, current status

approval gateway
  risk, reason, proposed action, state diff, approve/reject/edit

memory provider
  graph memory, node memory, run memory, artifact memory

UI projection
  React Flow canvas + inspector + timeline + approvals + memory
```

Core rule:

```text
Graph owns state and routing.
Node owns only its bounded loop.
Human owns approvals and root objective changes.
```

## V0 Build Decision

First build should prove only this:

1. Parse one `ORG.md` plus three node files: Planner, Worker, Reviewer.
2. Start a run from a user goal.
3. Materialize a run graph with task nodes and dependency edges.
4. Let each node execute a bounded loop.
5. Write every transition to `events.jsonl`.
6. Store task claims, node outputs, and artifacts in a local blackboard.
7. Pause on an approval condition.
8. Show the run live in a React Flow UI.

Do not build first:

- dynamic self-evolving org topology,
- full enterprise auth,
- distributed workers,
- complex graph memory,
- visual authoring,
- multi-tenant SaaS,
- arbitrary nested subagents.

V0 success criterion:

The UI can answer at every moment:

- what is running,
- why it is running,
- what context it is using,
- what changed,
- what is blocked,
- what needs approval,
- what evidence proves completion.

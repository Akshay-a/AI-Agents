---
id: graphroom-demo
name: Graphroom Demo Org
version: "0.2"
entry_node: planner
completion_node: reviewer
nodes:
  planner: nodes/planner.md
  researcher: nodes/researcher.md
  architect: nodes/architect.md
  scaffolder: nodes/scaffolder.md
  builder: nodes/builder.md
  tester: nodes/tester.md
  reviewer: nodes/reviewer.md
edges:
  - {id: plan-to-research, from: planner, when: complete, to: researcher}
  - {id: research-to-architecture, from: researcher, when: complete, to: architect}
  - {id: architecture-to-approval, from: architect, when: complete, to: approval}
  - {id: approval-to-scaffold, from: approval, when: approved, to: scaffolder}
  - {id: approval-rejected, from: approval, when: rejected, to: END}
  - {id: scaffold-to-build, from: scaffolder, when: complete, to: builder}
  - {id: build-to-test, from: builder, when: complete, to: tester}
  - {id: test-to-review, from: tester, when: complete, to: reviewer}
  - {id: test-failed, from: tester, when: failed, to: END}
  - {id: test-blocked, from: tester, when: blocked, to: END}
  - {id: review-passed, from: reviewer, when: pass, to: END}
  - {id: review-failed, from: reviewer, when: failed, to: END}
  - {id: review-blocked, from: reviewer, when: blocked, to: END}
approval_policy: Human approval of the Architect artifact is required before Coding Pattern may activate. Approval authorizes only that architecture handoff; rejection ends the run as blocked.
memory_policy: Supermemory is read-only scoped recall. Runtime truth remains in state.json and events.jsonl; no node writes external memory.
memory_container: graphroom-demo
---

# Purpose

Move one objective through bounded planning, research, an explicitly approved
architecture, constrained scaffolding, implementation, testing, and independent
verification while every handoff remains visible.

# Runtime rule

The graph owns state, policy enforcement, routing, approval, and audit history.
Each Markdown-backed agent owns one bounded Codex loop in the shared run
workspace. The approval gate is runtime state, not an agent. `state.json` is the
current projection; `events.jsonl` is the ordered audit history. LangGraph
checkpoints remain deliberately in-process in v0.2.

# Designer Philosophy: Make Autonomous Work Legible

## Product Idea

Graphroom is not a chat UI with several agents, and the graph is not decoration.
It is an execution room for an agent organisation: a place where an operator can
understand what is happening, why it is happening, what needs a decision, and
what will happen next.

The product earns trust by making autonomous work **visible, bounded,
inspectable, and interruptible**.

## Design Principles

1. **Show causality, not activity.** Nodes and edges should explain why work
   moved. The single blue trace marks the selected causal path; it is not an
   animation added to make the system appear busy.
2. **Separate structure from execution.** `ORG.md` describes the stable
   organisation. The live view is a projection of one run. Users should always
   know whether they are inspecting the design or its current behaviour.
3. **Place control at the decision point.** An approval belongs between the
   action that triggered it and the handoff it blocks. Keep it inline, show the
   policy and downstream impact, and name the action by its consequence.
4. **Make trust inspectable.** A node is more than a status. Its contract,
   context, tools, memory, artifacts, loop boundary, and state reason should be
   reachable without leaving the run.
5. **Treat the event log as product truth.** The graph, queues, inspector, and
   timeline should be projections of the same append-only events. Replay should
   reconstruct state, not tell a separate story.
6. **Prefer honest UI to impressive UI.** Label simulated data, show `—` when a
   value is unknown, and avoid fabricated metrics or decorative motion. State
   must remain understandable without colour alone.
7. **Reveal detail by intent.** The first viewport answers status, cause, risk,
   and next handoff. Deeper evidence appears when a node or event is selected.

## How the Mockup Was Shaped

The design started with the most important trust moment: Builder proposes a
permanent memory write, policy pauses the run, and Reviewer cannot start until a
human decides. The surrounding interface was then built outward from that one
causal event—run summary, graph, inline approval, node inspector, and timeline.

The visual system follows the product model: near-white is the work surface,
near-black carries facts, mono type signals contracts and events, and blue is
reserved for causality and control. Plain HTML and hand-authored SVG keep the
prototype focused on product behaviour rather than frontend machinery.

## Product Architecture Test

Every new feature should help an operator **understand, inspect, decide, or
recover**. If it does none of those, it does not belong in the Graph Ops Room.
The UI should project runtime truth and issue explicit commands; it should not
invent a second state model of its own.

# Graphroom: Graph Engineering for Codex

**The step after Loop Engineering.**

Loop Engineering makes one agent reliable by designing its inner cycle:

```text
goal -> observe -> decide -> act -> evaluate -> repeat
```

That works until one loop has to be the planner, researcher, architect, builder, tester, and reviewer. Its context grows, its permissions blur, and it ends up judging its own work.

Graph Engineering composes several reliable loops into a directed acyclic graph (DAG). Each node is a bounded **Loop Agent** with one job. The graph decides when that loop starts, what context it receives, which result it must return, and where the work goes next.

```text
objective
  -> [Planner loop]
  -> [Researcher loop]
  -> [Architect loop]
  -> [Human approval]
  -> [Coding Pattern loop]
  -> [Builder loop]
  -> [Test Runner loop]
  -> [Reviewer loop]
```

Codex runs each loop. Graphroom runs the graph.

![Graphroom run launcher showing the compiled seven-agent organisation](docs/images/graphroom-run-launcher.jpg)

_Before a run starts, Graphroom compiles the DAG from `ORG.md` and the node contracts. You can see the workflow, runtime mode, approval policy, and memory boundary before any loop begins._

## The evolution from prompts to graphs

These ideas build on one another:

| Layer | The question it answers | The unit being engineered |
| --- | --- | --- |
| Prompt Engineering | What should the model do now? | One instruction and response |
| Loop Engineering | How should one agent keep working until done? | Observe, act, evaluate, repeat |
| Graph Engineering | How should several autonomous loops work together? | A DAG of Loop Agents and conditional handoffs |

Graph Engineering does not replace the agent loop. It turns that loop into a reusable building block.

Codex is good at taking a bounded task, reading a workspace, using tools, changing code, and returning evidence. Graphroom gives each Codex thread that kind of bounded job, then keeps scheduling and policy outside the thread.

The important distinction is simple: **the node can reason, but the graph must govern.**

## A DAG becomes an autonomous workflow

The repository ships with one software-delivery DAG:

> Objective → Planner → Researcher → Architect → Human approval → Coding Pattern → Builder → Test Runner → Reviewer

| Worker | Its one job | Workspace access |
| --- | --- | --- |
| Planner | Turn the objective into a bounded plan | Read-only |
| Researcher | Gather the evidence and constraints | Read-only |
| Architect | Define the smallest workable architecture | Read-only |
| Coding Pattern | Create the scaffold and binding build contract | Workspace write |
| Builder | Implement only inside the approved contract | Workspace write |
| Test Runner | Run the required checks and return evidence | Read-only |
| Reviewer | Independently decide whether the work passes | Read-only |

After launch, Graphroom wakes a Loop Agent when its incoming condition is satisfied. When that agent returns a valid artifact, the graph records the handoff and wakes the next eligible loop. The workflow continues autonomously until it reaches an approval gate, a blocker, a failure, or the final reviewer verdict.

That is bounded autonomy: the DAG moves work forward automatically, but every loop stays inside a visible contract. A node cannot quietly skip ahead, widen its own permissions, invent a new reporting line, or declare the whole run complete.

`ORG.md` and `nodes/*.md` are the workflow source. Change the nodes and edges, and the same Graph Engineering model can describe a research pipeline, a content release, an incident response, or another governed workflow. The current v0.2 example is deliberately sequential and activates one eligible Loop Agent at a time.

## How the graph runs Codex loops

In **Supervised** mode, every eligible node becomes a fresh Codex work loop:

1. The graph sees that an incoming edge condition has been satisfied.
2. Graphroom reads the node's Loop Agent contract from `nodes/*.md`.
3. It builds a small context packet with the objective, relevant earlier artifacts, approval state, build contract, and verified memory.
4. It starts a new `codex exec` thread in the run workspace. The contract decides whether that loop is read-only or may write to the workspace.
5. Codex runs its own observe, decide, act, and evaluate cycle. Graphroom records the thread ID, tool activity, token usage, commands, and result in the run audit log.
6. The final response must match a structured schema and include an artifact plus evidence. A friendly-sounding answer is not enough.
7. Graphroom checks policy, updates graph state, and activates only the matching edge to the next Loop Agent.

Every node activation is therefore a real, separately observable Codex thread—not another character pretending to be an agent inside one shared chat. Codex's own multi-agent delegation is disabled inside these loops so the DAG stays visible and the graph remains in control.

Each supervised run gets an isolated working area:

```text
runs/<run-id>/
├── agents/<node-id>/
│   ├── result.schema.json
│   ├── result-<attempt>.json
│   └── codex-<attempt>.jsonl
├── workspace/
├── state.json
└── events.jsonl
```

`state.json` is the current picture. `events.jsonl` is the append-only story of how the run got there.

## A run is visible from end to end

![The complete seven-agent Graphroom run graph paused at the architecture gate](docs/images/graphroom-live-graph.jpg)

_The same DAG powers deterministic demos and supervised Codex runs. Completed loops, the active handoff, eligible routes, failure routes, and the final reviewer are all visible._

The graph is more than a diagram. Every line is an executable handoff condition. The UI projects the actual runtime state, so a completed node means its Loop Agent returned a valid artifact and evidence—not merely that an animation finished.

### Human approval is a real pause

![Graphroom approval gate showing the architecture handoff policy](docs/images/graphroom-approval-gate.jpg)

_The Coding Pattern worker cannot start until the architecture handoff is approved. Rejecting it ends the run as blocked._

Approvals live in the runtime, not in a prompt. That matters because the next Codex thread is never created until the graph receives the decision. The operator can see what is being released, which worker will receive it, and what boundary still applies.

### The bottom of the page is the run ledger

![Graphroom agent progression and run ledger](docs/images/graphroom-agent-ledger.jpg)

_The ledger makes it easy to compare every worker's state, current activity, attempt count, deliverable, and sandbox without clicking through the graph._

You can also inspect a node's live state, contract, exact context packet, tools, memory, and artifacts. The event timeline provides the ordered audit trail underneath it all.

## Run it locally

```bash
git clone https://github.com/Akshay-a/AI-Agents.git
cd AI-Agents/AI-GraphAgent

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

Use **Simulate** first. It runs the full graph with deterministic workers, including the approval pause, without calling Codex.

For **Supervised** mode, make sure the Codex CLI is installed, authenticated, and available on your `PATH` before starting Graphroom:

```bash
codex --version
```

Then choose **Supervised** in the launcher. Graphroom will start the Codex workers only as their nodes become eligible.

## Shape the organisation in Markdown

- `ORG.md` defines the nodes, edges, entry point, completion node, approval policy, and memory policy.
- `nodes/*.md` defines each worker's responsibility, sandbox, limits, artifact type, and input/output contract.
- `app.py` compiles those files, runs the graph, starts Codex workers, enforces boundaries, and exposes the API.
- `prototype/` contains the browser control room.

Useful optional environment settings:

| Variable | Purpose |
| --- | --- |
| `CODEX_BIN` | Use a specific Codex executable |
| `CODEX_MODEL` | Choose the model used by supervised workers |
| `GRAPHROOM_DATA_DIR` | Store run state somewhere other than `runs/` |
| `GRAPHROOM_SIM_DELAY` | Slow down or speed up simulated nodes |
| `SUPERMEMORY_API_KEY` | Enable scoped, read-only memory recall |

## What this prototype proves

Loop Engineering explains how one agent should work. Graph Engineering explains how several Loop Agents should work together.

Graphroom is deliberately small. It proves that an autonomous workflow does not need seven agents talking endlessly to one another. It needs bounded loops, executable handoffs, visible evidence, and a graph that knows when to continue, pause, fail, or stop.

The current version keeps LangGraph checkpoints in memory, stores run truth locally, uses one explicit approval gate, and executes nodes sequentially. Those constraints are intentional. The goal is to make a graph of real Codex loops understandable and governable before making it larger.

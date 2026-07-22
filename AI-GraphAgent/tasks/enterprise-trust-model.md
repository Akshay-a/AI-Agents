# Enterprise Trust Model For Agent Org

Date: 2026-07-21

## Why Enterprises Would Care

Enterprises do not buy "agentic autonomy" by itself. They buy controlled
delegation.

The product earns trust when it can answer:

- who initiated the run,
- which agent acted,
- on whose behalf,
- what context it saw,
- what tools it could access,
- what tool it called,
- what it changed,
- what memory it wrote,
- what it asked,
- what it assumed,
- who approved it,
- why the graph moved to the next node,
- why the run completed.

This aligns with the direction of GitHub's enterprise AI controls: centralized
agent management, custom agents, session activity, agentic audit logs, and MCP
allowlists.

## Enterprise Controls To Emulate

### 1. Agent Session Activity

Show all active/recent runs:

- run id,
- objective,
- current state,
- active nodes,
- started by,
- runtime,
- duration,
- cost,
- last event,
- failure reason.

### 2. Agentic Audit Log

Every event should include:

```text
event_id
run_id
node_id
actor_is_agent
human_actor_id
agent_session_id
action
timestamp
causation_id
correlation_id
payload_hash
```

This mirrors enterprise audit expectations such as distinguishing agent actors
from the human user they act on behalf of.

### 3. MCP Allowlist

MCP access should be governed at multiple levels:

- global allowlist,
- org allowlist,
- node allowlist,
- run override,
- approval requirement.

Node files should specify MCP access, but the graph kernel should enforce it.

Example:

```yaml
mcp:
  allowed:
    - github/search
    - github/read_issue
  approval_required:
    - github/create_issue
    - slack/send_message
  denied:
    - shell/*
```

### 4. Tool Scope

Tool access should be explicit:

- read-only,
- safe-edit,
- external-side-effect,
- destructive,
- paid,
- secret-access.

Default rule:

- read-only can run autonomously,
- safe-edit can run within run workspace,
- external/destructive/paid/secret actions require approval.

### 5. Memory Governance

Memory is a risk surface.

Memory write policies:

- run-only memory can be automatic,
- node-local memory can be proposed,
- graph memory should require policy checks,
- permanent graph memory should require approval in early versions.

Memory records need:

- scope,
- source event,
- writer node,
- confidence,
- expiry,
- correction history.

### 6. Approval Fatigue Controls

Approvals need risk tiers:

```text
low      auto-approve or batch approve
medium   human approval
high     human approval + stronger explanation
critical multi-step approval or disabled in V0
```

The approval inbox should support:

- grouping by run,
- grouping by risk,
- filtering by node,
- bulk approve only for low-risk deterministic actions.

## Product Trust Surface

### Run Header

Always visible:

- state,
- active nodes,
- pending approvals,
- pending questions,
- cost,
- risk,
- last event.

### Node Inspector

Always answer:

- why this node is active,
- what it is allowed to do,
- what context it saw,
- what memory it read,
- what it produced,
- why it stopped.

### Timeline

Always answer:

- what happened,
- in what order,
- caused by whom,
- with what result.

### Memory Panel

Always answer:

- what the org thinks it learned,
- who taught it,
- from what evidence,
- whether it is still valid.

## Reliability Rules

### Rule 1: No Hidden Global Mutation

Nodes cannot mutate:

- graph state,
- permanent memory,
- approvals,
- artifact validity,
- completion verdicts.

They can only propose typed results.

### Rule 2: No Completion Without Evidence

A run completes only when:

- completion node returns success,
- required artifacts exist,
- reviewer verdict passes,
- no blocking approval is pending,
- no blocking question is unresolved.

### Rule 3: No Infinite Autonomy

Every node has:

- max iterations,
- max tool calls,
- max wall time,
- max cost,
- max retries,
- stop conditions.

### Rule 4: Everything Important Is Replayable

Replay requires:

- `RunEventLog`,
- node context packets,
- artifacts,
- approval decisions,
- memory write events.

It does not require reconstructing chat history from model transcripts.

## Buyer-Friendly Positioning

Avoid saying:

- "autonomous AI company",
- "future of work",
- "agentic intelligence graph",
- "AI workflow builder."

Say:

- "Control room for autonomous agents."
- "See what every agent is doing and why."
- "Approve risky actions before they happen."
- "Every task, tool call, memory write, and decision is auditable."
- "Your agent organization is defined in versioned Markdown."

## Enterprise V1 Requirements

Do not build these first, but design for them:

- SSO,
- RBAC,
- org-level MCP allowlists,
- audit log export,
- retention policies,
- secret scoping,
- workspace isolation,
- run replay,
- policy engine,
- cost budgets,
- model/provider controls,
- environment separation,
- data residency options.

## Trust Thesis

The product wins if the buyer believes:

> I can delegate real work to autonomous agents because I can see their graph,
> bound their actions, inspect their memory, approve their risky moves, and
> audit every decision afterward.

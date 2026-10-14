# 7. The assistant is a hand-written `StateGraph`

Date: 2026-10-14
Status: Accepted. Supersedes ADR 0005's "the rung is the tool loop".

## Context

The product's writes -- create, close and reassign -- each pause for the
owner's approval (`docs/roadmap.md`, slice 4). That control flow needs:
- an `interrupt()` before a write;
- a rejection that ends the run without another model call;
- a write that never repeats its effect.

ADR 0003 says to climb the orchestration ladder when a requirement needs the
control flow. The owner chose the rung on 2026-10-14: a hand-written graph,
over `create_agent` with `HumanInTheLoopMiddleware`
(`openspec/changes/*assistant-as-a-graph/frame.md`).

Three things settled here are expensive to reverse:
- the node names and the state schema, an interface of the local server's
  threads;
- where a budget is enforced;
- the error each budget ends a run with.

## Decision

- **`assistant` is a `StateGraph`** with three nodes:
  - `start_run`, which sets the run's counts to zero;
  - `call_model`, which sends the prompt and messages within the budgets
    and stores the reply;
  - `run_tools`, which runs the well-formed calls through LangGraph's
    `ToolNode` and answers the malformed ones.

  Routing after a reply is the domain policy `route_after_reply`.
- **Its state is a versioned contract**, `AssistantState` at version 1:
  `messages`, `model_calls` and `tool_calls`. A run takes and returns only
  `messages`.
- **Budgets are enforced in the nodes**, from `domain/agents/budgets.py`,
  and raise domain errors.
- **A model retry is `call_model`'s `RetryPolicy`**, on the predicate the
  factory is given.
- **The graph lives in `infrastructure/agents/graphs/assistant/`**, and
  `factory.py` compiles it with a step ceiling of 9,999.
- **The graph id stays `assistant`.**

## Consequences

**Good:**
- Every route is a node or an edge in one table (the change's design.md),
  held equal to the graph by a test.
- Slice 4b adds its approval and write nodes to a graph whose every route
  is already proved.
- No middleware order to get wrong: the malformed-call loop that ran past
  the budget (bound-the-tool-loop, tasks 2.2) cannot recur that way.

**Costly:**
- About a hundred lines of nodes replace six middleware. LangChain's next
  middleware -- summarisation, a fallback model -- is not free to add; each
  would be a node or a wrapper.
- `create_agent`'s improvements no longer arrive with an upgrade. Two
  adopted pieces still do: `ToolNode` and `RetryPolicy`.

**Reversal:** back to `create_agent` is replacing the factory's body. Its
node names and state differ, so a durable thread written by one would not
resume in the other. That reason grows with slice 5.

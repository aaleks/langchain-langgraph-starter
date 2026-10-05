# The orchestration ladder -- choosing the lowest rung

Read this when a request involves more than one model call, tools, routing,
retries, pausing for a human, or long-running work. Choose the lowest rung that
expresses the control flow a requirement needs. Climb a rung when a requirement
needs the control flow -- never in anticipation of one. Moving from a tool loop
to a graph later is a small change; carrying an unused graph meanwhile is not free.

| Situation | Rung |
|---|---|
| One call, no tools | a plain `invoke` inside an application use case |
| A tool loop with standard control flow | `create_agent`, with its middleware for retries, call limits, fallbacks and output checks |
| Control flow this project designs: a review/revise loop with its own state and budget, policy-driven branching, interrupts for human approval, fan-out | a hand-written LangGraph `StateGraph` |

A tool-calling loop is not a single invocation -- "add these, then divide the
result" is model, tool, model, tool, model -- but it does not need a hand-written
graph either: `create_agent` already compiles to one. Like any runtime, it lives
in the adapter layer (`infrastructure/agents/`), never in `application/`.

**Deep Agents is not a rung above the graph.** It is a harness for one class of
task: long-running work that needs planning, delegation to subagents and a
virtual filesystem. Take it only when a requirement needs those, behind its own
capability manifest. Start it with no shell, no write-capable filesystem, no
broad network and no long-term memory. Regulated, transactional or high-impact
actions stay in an explicit graph, where every route and approval can be
audited. Its rules are in `.claude/rules/langgraph/graphs.md`.

## Adopt a graph when at least one is true

- the workflow has more than one material decision or action step;
- it must pause and resume across a human approval or an external delay;
- it branches, loops with a bounded retry or replan, fans out, or delegates;
- it needs durable thread state, streaming progress, replay or time travel;
- a graph view would make the user-visible workflow safer to review.

## Retries are three different problems

- **Transient** (429, timeout, 5xx): not a graph concern. The classification is a
  domain predicate; the loop is an infrastructure helper. On an agent path,
  `ModelRetryMiddleware(retry_on=<the predicate>, on_failure="error")`.
- **Tool failures**: `ToolRetryMiddleware(..., on_failure="error")` for transient
  ones; `ToolErrorMiddleware(on_error=...)` for errors the model can correct --
  the handler returns the message the model sees, or `None` to re-raise. No graph
  needed.
- **Semantic** ("the answer was wrong, try again"): a decision with a budget, and
  the budget is a domain rule. A graph makes the loop visible; only the budget
  makes it safe. An unbounded contract retry runs to the runtime's step ceiling.

## The tool loop's budgets -- the defaults are the trap

Checked against `langchain 1.4.3`. Every default below turns a failure or an
exhausted budget into something that reads like an answer, or into no limit at
all. Set them explicitly:

| Middleware | Default | Set |
|---|---|---|
| `ModelCallLimitMiddleware` | `run_limit=None` -- no limit. On exhaustion `exit_behavior="end"` injects an AI message saying so | `run_limit=<the domain budget>`, `exit_behavior="error"`: `ModelCallLimitExceededError` is a terminal outcome the caller maps |
| `ToolCallLimitMiddleware` | `run_limit=None`; `exit_behavior="continue"` lets the model decide when to stop | `run_limit=`, `exit_behavior="error"`: `ToolCallLimitExceededError` |
| `ModelRetryMiddleware`, `ToolRetryMiddleware` | `on_failure="continue"`: the failure becomes a message | `on_failure="error"` |

The budget's number is a domain rule, proved with `==`; the middleware only
enforces it. Re-check these defaults when `langchain` moves.

## Reviewing output before it is returned

A generate -> review -> (revise | finish) loop is the clearest case for a graph:
the text is non-deterministic, but the route is not. "The reviewer rejects
twice and the run ends `review_exhausted`" can be asserted with `==` against a
fake model. Before building one:

1. **Use the cheapest sufficient reviewer.** If a deterministic check can decide
   it -- schema validation, recomputing a tool's arithmetic -- that is a domain
   rule, not a judge.
2. **A model reviewing its own output shares its blind spots.**
3. **Every review costs at least one more model call.**
4. **An online gate is not an offline judge.** Gate online what is cheap and
   deterministic, or high-stakes; sample the rest offline.

A single-check review needs no `StateGraph`: an `after_model` hook can send a
rejected answer back, bounded by the run's step budget. Write the graph when the
review needs a terminal outcome of its own, state of its own (attempts,
critique history), more than one reviewer, or its own node in the graph and its run history.

## The routes every requirement set names

On the tool-loop or graph rung, the requirements name each observable route,
not only the happy path. Each route below is a requirement, a scenario of one,
or N-A with the reason:

| Route | What the requirement states |
|---|---|
| completion | the terminal outcome, and what the caller sees |
| refusal | a request policy declines, and the outcome it ends in |
| approval, rejection | what each human decision at an `interrupt()` leads to |
| interruption and resume | the pause, its payload, and the same thread resuming -- from another process, too |
| retry exhaustion | transient failures past the retry policy, and the outcome |
| limit exhaustion | each step, tool-call or replan budget spent, and the outcome |
| tool denial | an action the capability or authorisation check refuses |
| malformed model output | a contract the model's output fails |
| retrieval failure, timeout | a dependency that fails or is too slow |
| forbidden access | another tenant's thread or state, refused |

The outcome of each is a status the design names -- never the text.
`accept/references/graph-routes.md` says how each test asserts it.

## Build a graph a vertical slice at a time

The state contract, then one node, then its transition, then a fake-model run
end to end -- and only then persistence, and registration in `langgraph.json`,
when the graph must run outside a test. tasks.md follows that order, one
requirement per group.

When the rung is a graph, design.md's orchestration table is required, and
`.claude/rules/langgraph/graphs.md` applies to every file under
`infrastructure/agents/`.

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

## Adopt a graph when at least one is true

- the workflow has more than one material decision or action step;
- it must pause and resume across a human approval or an external delay;
- it branches, loops with a bounded retry or replan, fans out, or delegates;
- it needs durable thread state, streaming progress, replay or time travel;
- a graph view would make the user-visible workflow safer to review.

## Retries are three different problems

- **Transient** (429, timeout, 5xx): not a graph concern. The classification is a
  domain predicate; the loop is an infrastructure helper. On an agent path,
  `ModelRetryMiddleware` accepts a predicate -- use it with `on_failure="error"`,
  because the default turns the failure into a message that reads like an answer.
- **Tool failures**: `ToolRetryMiddleware` for transient ones; errors the model
  can correct go back to the model. No graph needed.
- **Semantic** ("the answer was wrong, try again"): a decision with a budget, and
  the budget is a domain rule. A graph makes the loop visible; only the budget
  makes it safe. An unbounded contract retry runs to the runtime's step ceiling.

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

When the rung is a graph, design.md's orchestration table is required, and
`.claude/rules/langgraph/graphs.md` applies to every file under
`infrastructure/agents/`.

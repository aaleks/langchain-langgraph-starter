# Frame

## Outcome

**Who benefits:** the owner. Today the assistant's control flow is
`create_agent`'s and six middleware. Slice 4b needs a pause for approval
before a write, and a write node that never repeats its effect. Both need
control flow this project designs and can show node by node.

**The observable signal:**
- every assistant requirement in the living spec is still proved, through
  the same factory, against the new graph;
- the graph's nodes and edges equal design.md's table, in a test;
- the state the graph carries is a contract with a version, pinned in a test;
- the routing is a domain function, proved with `==`;
- the registered graph still serves the live tests through `scripts/serve.sh`
  and the owner's Open WebUI.

**Non-goals:**
- **No write, no interrupt, no new tool:** 4b.
- **No checkpointer of this project's own:** slice 5. The local server
  brings its own in-memory one, as it does today.
- **No change to the prompt, the budgets' values, the retry policy, the
  tools or the model client.**

## Existing options considered

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| `create_agent` + `HumanInTheLoopMiddleware` (langchain 1.4.4, installed) | yes: the installed minor, released this year; the middleware ships the approval request and decision types | the tool loop and an approval pause per tool | the routes are middleware hooks whose order matters -- `AnswerInvalidCalls` had to be listed first, and an `after_model` hook placed wrong looped past the budget (bound-the-tool-loop, 2.2). The write's idempotency key, the audit, and a rejection that ends the run are each another hook |
| a hand-written `StateGraph` (langgraph 1.2.14, installed), reusing `ToolNode` (langgraph-prebuilt 1.1.0) and `RetryPolicy` | yes: the same releases `create_agent` compiles to | every route, as nodes and edges this project names | the loop's three nodes and its budgets, written here -- about what the middleware was |

**Decision:** a hand-written `StateGraph`. Tools still run through
`ToolNode` -- unknown tools and refused arguments answered as today -- and a
model retry is the node's `RetryPolicy`, on the domain's predicate. The
graph's routes become nodes and edges anyone can read in one table, instead
of hook order. Chosen by the owner, 2026-10-14. LangChain's approval request
and decision types are adopted in 4b, as data, so a client that renders
them -- Agent Chat UI, `useStream` -- works unchanged.

## Orchestration rung

**A hand-written graph.** Slice 4b's requirements need an `interrupt()`
before a write, a rejection that ends the run without another model call,
and a write node keyed for idempotency. This change climbs the rung with the
behaviour unchanged, so 4b adds nodes to a graph that is already proved.

Measured with a throwaway graph (deleted): `ToolNode` called inside a node
answers an unknown tool and refused arguments with error tool messages as
today. A tool's own exception propagates. `RetryPolicy` retries the node on a
predicate. An async-only tool runs through `ainvoke`. The budget's 11th call
needs 22 supersteps.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | the living requirements, carried; the new ones each with a counter-example |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | all deterministic: routes, counts, state shape |
| Data -- provenance, freshness, what happens when a source is withdrawn | N-A | no new data; the task list is read as before |
| Untrusted input -- anything ingested that this project did not write | Partial | a caller's run input could carry a counter to reset a budget: refused by the input schema (ASSISTANT-STATE-CONTRACT). Task text: unchanged, its story test kept |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Partial | the graph id stays `assistant`. Changes: the nodes (`start_run`, `call_model`, `run_tools`), the state's fields, and two error classes -- now domain errors. The local server keeps no thread between starts, so no thread migrates (design.md) |
| Failure -- what the user sees when a dependency is down | Clear | unchanged: transient failures retried twice, then raised |
| Cost -- tokens, time, money and storage per run | Clear | no new model call; one superstep more per run (`start_run`) |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Keep raising on an exhausted budget, or end with a status in the state? | decided by the agent | keep raising, as the living spec says: a budget's error is the run's outcome on the server today, and 4a changes no behaviour. The error classes move to `domain/` with the budgets |
| 2 | The step ceiling | decided by the agent | 9,999, `create_agent`'s, set by the factory, so the server's own default never decides it. The budget needs 22 (measured) |

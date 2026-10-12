# Design

Why: `frame.md`. The decisions expensive to reverse -- the graph id, the rung,
the offline model -- are ADR 0005 (`docs/decisions/0005-the-assistant-graph.md`).

## Context

Five empty layers. `tests/architecture/test_graphs.py` already holds three
checks that skip until `langgraph.json` and `infrastructure/agents/` exist:
registration only through the registry, no client imported by the agents
adapter, no model built inline there. The design gives each something real to
check.

## Decisions

**Files, the fewest the requirements need** (the layout in
`.claude/rules/langgraph/graphs.md`, created only as needed):

| File | Holds | Layer rule it keeps |
|---|---|---|
| `src/starter/domain/agents/budgets.py` | `MODEL_CALLS_PER_RUN = 10` | domain: standard library only |
| `src/starter/infrastructure/models.py` | `build_offline_model()` -- the only place a model is built | infrastructure |
| `src/starter/infrastructure/agents/factory.py` | `build_assistant(model, tools)` -- `create_agent` with `ModelCallLimitMiddleware(run_limit=MODEL_CALLS_PER_RUN, exit_behavior="error")`; the only place a graph is compiled | agents adapter: runtimes only; the model arrives as an object |
| `src/starter/infrastructure/agents/registry.py` | `assistant = build_assistant(build_offline_model(), tools=[])` -- the only export `langgraph.json` may name | registration |
| `langgraph.json` | `{"graphs": {"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}, "dependencies": ["."], "python_version": "3.13"}` -- no `env` | ADR 0004 |
| `tests/conftest.py` | `fake_llm`: a `GenericFakeChatModel` subclass whose `bind_tools` returns itself, scripted with `AIMessage`s, counting its calls | fakes subclass the real base class |

- **The model is passed in.** `factory.build_assistant` never builds one, so a
  test hands it the fake and the registry hands it the offline model -- the
  same code path. Alternative considered: the factory reading a setting to
  choose the model. Rejected: there is one model and no setting yet, and
  `config/` arrives in 1b.
- **The offline model** is `GenericFakeChatModel(messages=itertools.cycle([...]))`
  -- one fixed `AIMessage`, forever. Alternative: `ParrotFakeChatModel`, which
  returns the last message as it is: a `HumanMessage` in the model's place,
  which is not an answer the loop expects. A hand-written model: a double that
  agrees with itself.
- **The budget is enforced by middleware, decided in the domain.** The number
  is `domain/agents/budgets.py`'s; `ModelCallLimitMiddleware` only counts.
  `exit_behavior="error"` makes exhaustion `ModelCallLimitExceededError` --
  the default, `"end"`, injects an AI message that reads like an answer.
- **The step ceiling stays above the budget.** Each model call is preceded by
  the middleware's `before_model` step and followed by a tools step, so ten
  calls take about thirty supersteps. If LangGraph's default recursion limit
  is reached first, the run ends in `GraphRecursionError` -- the inherited
  lesson. The factory sets the compiled graph's `recursion_limit` from the
  budget, and ASSISTANT-MODEL-CALL-BUDGET's first scenario fails if it does not.

## Orchestration design

N-A -- the rung is the tool loop (`frame.md`); `create_agent` owns the
topology. What the requirements fix about it:

- **State:** `create_agent`'s `AgentState` -- `messages`, serialisable. Not a
  project contract yet: no checkpointer persists it (no version needed until
  one does -- the durability slice).
- **Identity:** N-A -- no checkpointer, so no thread outlives a run in this
  change. The local server's threads arrive with 1b, ownership with durability.
- **Budgets:** model calls per run, `MODEL_CALLS_PER_RUN = 10`; exhausted ->
  `ModelCallLimitExceededError`. Tool calls are bounded by model calls.
- **Errors:** policy (budget exhausted) -> the error above, never retried.
  A tool's exception -> raised (unexpected); no tool here can fail by design.
  Transient and contract classes need a real model and structured output:
  N-A until one exists.
- **Interrupts:** none -- 1b and the durability slice.
- **Tools:** none registered. Tests inject a recording fake `add(a: int, b: int) -> int`;
  read-only, no side effect, no manifest (a test fake never ships).
- **Streaming:** the runtime's defaults; asserted in 1b through the server.
- **Persistence:** none. The registered graph has no checkpointer; the local
  server supplies its in-memory one in 1b, which is never evidence of durability.
- **Observability:** N-A until there is an entry point (1b). No LangSmith,
  ever (ADR 0004).
- **Runtime:** in tests, `invoke` on the compiled graph. The server is 1b.
- **Test plan:** the tool loop and the budget through the factory with fakes
  (integration); registration and the offline run through `langgraph.json`
  (acceptance, the story test); placement and registration rules
  (architecture, already written, fixture-proved). No `live` test.
- **Graph id:** `assistant`. Renaming it strands every thread created under it
  -- an interface change with a migration (ADR 0005).

## Risks

- [LangGraph's step ceiling ends a long loop before the budget does] ->
  the factory sets `recursion_limit` from the budget; the budget's test asserts
  `ModelCallLimitExceededError`, not `GraphRecursionError`.
- [A middleware default changes in a minor release] -> dependencies bounded to
  the checked minor; the ladder's table is re-checked on a bump.
- [`langgraph-api` 0.16.0 makes a connection 0.15.1 did not] -> nothing in this
  change starts the server; 1b re-runs the probe before it does.
- [The offline model is mistaken for an assistant] -> ADR 0005 and the module's
  docstring say it is a walking skeleton; its fixed answer says so too.

## Migration and rollback

N-A -- nothing persists and nothing depended on a graph before. Rollback is
reverting the change: the three architecture checks skip again.

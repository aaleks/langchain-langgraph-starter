# Design

Why: `frame.md`. The decisions expensive to reverse -- the graph id, the rung,
the offline model -- are ADR 0005 (`docs/decisions/0005-the-assistant-graph.md`).
Amended after verify pass 1 (`verify.md`): the error routes, the measured step
floor, the offline model, and the suite's local-only environment.

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
| `tests/fakes.py` | `ScriptedChatModel`: a `GenericFakeChatModel` whose `bind_tools` records the tools and returns itself; it counts its calls, records each call's input, and raises a scripted exception. `recording_add()`, `propose()`, `answer()` | fakes subclass the real base class |
| `tests/conftest.py` | `LOCAL_ONLY`: the suite's environment, applied before langchain_core is imported; the `fake_llm` and `add_tool` fixtures, importing `tests/fakes.py` lazily | ADR 0004 |

- **The model is passed in.** `factory.build_assistant` never builds one, so a
  test hands it the fake and the registry hands it the offline model -- the
  same code path. Alternative considered: the factory reading a setting to
  choose the model. Rejected: there is one model and no setting yet, and
  `config/` arrives in 1b. **For 1b:** once a setting chooses the model, that
  choice goes into a factory function the registry calls -- not into the
  registry's import-time body, where it would read settings before `.env` is
  loaded (the inherited lesson).
- **The offline model** is `GenericFakeChatModel(messages=itertools.repeat(OFFLINE_ANSWER))`
  -- a string, repeated, which the fake turns into a fresh `AIMessage` on each
  call. A reused `AIMessage` would carry one id across turns, and the second
  answer would replace the first in a thread's history; measured in verify
  pass 1 (`human, ai, human`), and now a scenario of ASSISTANT-REGISTERED.
  Alternative: `ParrotFakeChatModel`, which returns the last message as it is:
  a `HumanMessage` in the model's place. A hand-written model: a double that
  agrees with itself.
- **The budget is enforced by middleware, decided in the domain.** The number
  is `domain/agents/budgets.py`'s; `ModelCallLimitMiddleware` only counts.
  `exit_behavior="error"` makes exhaustion `ModelCallLimitExceededError` --
  the default, `"end"`, injects an AI message that reads like an answer.
- **The budget, not the step ceiling, ends a runaway loop -- above a floor of
  41 supersteps.** Measured: with no budget, a model that never stops proposing
  calls ran to `GraphRecursionError: Recursion limit of 9999 reached`. The
  9,999 is `create_agent`'s own setting (`langchain/agents/factory.py`, a
  `with_config` on the compiled graph), so it moves with the `langchain` pin.
  Each model call takes four supersteps with the budget's two hooks and the
  tools step, so the budget needs 41: a caller passing `recursion_limit` 40 ends
  at the ceiling first. That boundary is a counter-example of
  ASSISTANT-MODEL-CALL-BUDGET, so a change in the step count fails a test.
- **The default suite is local-only.** It runs whatever shell starts it, and
  from this change on it runs LangChain code: with `LANGSMITH_TRACING=true`
  exported, every graph run was uploaded, from a background thread the network
  guard could not see (verify pass 1, finding 1). `tests/conftest.py` applies
  the same twelve variables as `.claude/settings.json`'s `env` before anything
  imports langchain_core, and `addopts` turns off the `langsmith` pytest
  plugin, which loads first. `tests/architecture/test_local_only.py` holds the
  two lists equal and fails when the suite runs with tracing on.
- **Compiling is confined, by a check.** `graphs_compiled_outside_factory` and
  `agent_runtime_imports_outside_agents` (`tests/architecture/contract.py`)
  fail when a graph is compiled anywhere but `factory.py`, or `langchain.agents`
  is imported outside `infrastructure/agents/`. Each is proved on a fixture.

## Orchestration design

N-A for the node table -- the rung is the tool loop (`frame.md`); `create_agent`
owns the topology. What the requirements fix about it:

- **State:** `create_agent`'s `AgentState` -- `messages`, serialisable. Not a
  project contract yet: no checkpointer persists it (no version needed until
  one does -- the durability slice).
- **Identity:** N-A -- no checkpointer, so no thread outlives a run in this
  change. The local server's threads arrive with 1b, ownership with durability.
- **Budgets:** model calls per run, `MODEL_CALLS_PER_RUN = 10`; exhausted ->
  `ModelCallLimitExceededError`. **Tool calls are not bounded per turn:** one
  model message may propose any number, and each runs. Harmless while the
  registered graph has no tools; a tool-call budget (`ToolCallLimitMiddleware`,
  `exit_behavior="error"`) arrives with the first real tool.
- **Errors, by class** (`graphs.md`):

  | Class | In this graph | Handling | Proved by |
  |---|---|---|---|
  | model-recoverable | a call to a tool the model was not given; arguments the schema refuses | a tool message, status `error`, handed back; the run goes on under the budget | ASSISTANT-TOOL-ERROR |
  | policy | the model-call budget spent | `ModelCallLimitExceededError`, never retried | ASSISTANT-MODEL-CALL-BUDGET |
  | unexpected | a tool or the model raises | propagates unchanged -- `langgraph-prebuilt`'s default re-raises, now pinned by a test rather than trusted | ASSISTANT-ERRORS-PROPAGATE |
  | malformed output | `invalid_tool_calls` -- arguments the model emitted unparseably | **OPEN:** today the run ends like an answer. Decided by the first change that installs a provider (`frame.md`, question 3) | -- |
  | transient | a 429, a timeout | N-A: no provider. With one, `ModelRetryMiddleware(retry_on=<domain predicate>, on_failure="error")` and a deadline on the call | -- |
  | contract | structured output invalid | N-A: no structured output | -- |

- **Routes** -- the ladder's checklist, one row each:

  | Route | Here |
  |---|---|
  | completion | ASSISTANT-TOOL-LOOP: the run ends when the model answers without a tool call |
  | refusal | N-A: no request policy declines anything yet -- the safety slice, with authorisation at the tool boundary |
  | approval, rejection | N-A: no `interrupt()` -- the durability slice |
  | interruption and resume | N-A here; 1b's smoke run resumes an interrupt through the server |
  | retry exhaustion | N-A: no retry policy without a provider (transient, above) |
  | limit exhaustion | ASSISTANT-MODEL-CALL-BUDGET, and refused calls spending it (ASSISTANT-TOOL-ERROR) |
  | tool denial | ASSISTANT-TOOL-ERROR covers a tool the model was not given; authorisation-based denial is the safety slice |
  | malformed model output | ASSISTANT-TOOL-ERROR for refused arguments; `invalid_tool_calls` OPEN |
  | retrieval failure, timeout | Retrieval: N-A, none. Timeout: a model's `TimeoutError` propagates (ASSISTANT-ERRORS-PROPAGATE), but no deadline is enforced -- a call that hangs hangs the run. A deadline on the provider call arrives with the first provider (`docs/roadmap.md`) |
  | forbidden access | N-A: no threads persist -- the durability slice |

- **Interrupts:** none -- 1b and the durability slice.
- **Tools:** none registered. Tests inject a recording fake `add(a: int, b: int) -> int`
  and, for the error routes, `explode` (raises) and `explain` (returns an error
  text); read-only, no side effect, no manifest (a test fake never ships).
- **Streaming:** not exercised. The fake's inherited `_stream` cannot stream a
  proposal: with no text it raises (`No generation chunks were returned`), with
  text it drops the `tool_calls`. 1b teaches it before a streamed run is asserted.
- **Persistence:** none. The registered graph has no checkpointer; the local
  server supplies its in-memory one in 1b, which is never evidence of durability.
- **Observability:** N-A until there is an entry point (1b). No LangSmith,
  ever (ADR 0004) -- the suite included.
- **Runtime:** in tests, `invoke` on the compiled graph. The server is 1b.
- **Test plan:** the five requirements' routes through the factory with fakes
  (integration); registration, the factory seam, the offline run under a refused
  network and a second turn, through `langgraph.json` (acceptance, the story
  test); placement, registration, compiling and the local-only environment
  (architecture, each check proved on a fixture). No `live` test.
- **Graph id:** `assistant`. Renaming it strands every thread created under it
  -- an interface change with a migration (ADR 0005).

## Risks

- [The step ceiling ends a loop before the budget does] -> `create_agent` sets
  9,999; the budget needs 41, and a counter-example pins that floor. A caller's
  lower `recursion_limit` is outside the requirement, by its own statement.
- [A middleware or prebuilt default changes in a minor release] -> dependencies
  bounded to the checked minor; the error routes are pinned by tests, not
  trusted; the ladder's table is re-checked on a bump.
- [`langgraph-api` 0.16.0 makes a connection 0.15.1 did not] -> nothing in this
  change starts the server; 1b re-runs the probe before it does.
- [The offline model is mistaken for an assistant] -> ADR 0005 and the module's
  docstring say it is a walking skeleton; its fixed answer says so too.

## Migration and rollback

N-A -- nothing persists and nothing depended on a graph before. Rollback is
reverting the change: the three architecture checks skip again.

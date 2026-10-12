# Frame

## Outcome

A developer who starts from this repository gets one LangGraph graph, the
`assistant`, that runs a tool loop end to end with fake models in the default
suite, is bounded by a domain budget, and is registered for the local server
under a stable id. Before this change nothing graph-shaped existed and three
architecture checks skipped, saying so.

Observable signals:

- `uv run pytest -q` runs every route the requirements name -- a completed tool
  loop, an immediate answer, an exhausted budget -- with fakes, with no service,
  key or network.
- `langgraph.json` registers `assistant`, and the three checks in
  `tests/architecture/test_graphs.py` run and pass instead of skipping.
- The registered graph completes a run with every outbound connection refused.

**Non-goals** -- each is a later slice, through its own intake:

- serving the graph: the local-only entry point, `.env` loading in `config/`,
  the `live` smoke run through `scripts/serve.sh`, the connection probe re-run
  against the pinned versions -- `serve-first-graph-locally` (1b);
- a real model provider, a real tool, a CLI entry point;
- a hand-written `StateGraph`, routing policy, interrupts, checkpointers,
  durability -- the correctness and durability slices.

## Existing options considered

Checked on 2026-10-12 against PyPI's JSON API (latest stable, upload date),
then installed into this project with `uv add` and probed in a scratch
environment with every socket connection blocked: `langchain 1.4.4`
(2026-10-08), `langchain-core 1.6.9` (2026-10-08), `langgraph 1.2.14`
(2026-10-06), `langgraph-prebuilt 1.1.0`, `langgraph-cli 0.4.33` (2026-10-07),
with `langgraph-api 0.16.0` and `langgraph-runtime-inmem 0.36.0` (both
2026-10-10). Each moved since the pack was checked on 2026-10-05 (`langchain
1.4.3`, `langchain-core 1.6.6`, `langgraph 1.2.13`, `langgraph-cli 0.4.32`,
`langgraph-api 0.15.1`): releases days apart are the maintenance signal.

Measured in the probe, and binding on the design:

- `GenericFakeChatModel` and `FakeMessagesListChatModel` emit `tool_calls`
  intact, but every fake in `langchain_core` inherits `bind_tools` from
  `BaseChatModel`, which raises `NotImplementedError` -- so `create_agent` with
  tools fails on a stock fake. A subclass returning itself from `bind_tools` ran
  the full loop. `ParrotFakeChatModel` echoes a `HumanMessage` in the model's
  place.
- `create_agent` returns a `CompiledStateGraph` (nodes `model`, `tools`), the
  same type a hand-written `StateGraph` compiles to; `draw_mermaid()` works
  offline.
- `langgraph validate` checks the file's schema -- JSON, a non-empty `graphs`,
  `python_version`, `dependencies` -- and **not** the graph specs: a path to a
  file that does not exist exits 0. It is a schema check, never proof that a
  graph loads. Like every logged CLI command it POSTs analytics to Supabase
  unless `LANGGRAPH_CLI_NO_ANALYTICS` is exactly `1` (`true` does not count);
  on Windows it needs `PYTHONUTF8=1`, or its emoji help crashes under cp1252.
- A graph compiled with its own checkpointer is refused by the local server
  ("custom checkpointer"): the registry compiles without one.

The runtime itself is not in question: ADR 0003 adopted LangGraph. Two choices
inside it are:

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| **Tool loop:** `langchain.agents.create_agent` | yes -- `langchain 1.4.4`; the ladder's tool-loop rung | the model/tool loop, tool execution, `ModelCallLimitMiddleware` for the budget; returns a `CompiledStateGraph` | the budget's middleware defaults are the trap (`run_limit=None`, `exit_behavior="end"`): set `run_limit` from the domain and `exit_behavior="error"` |
| Tool loop: a hand-written `StateGraph` with `ToolNode` and `tools_condition` | yes -- `langgraph 1.2.14`, `langgraph-prebuilt 1.1.0` | the same loop, with node names this project owns | a state contract, nodes, routes and a budget to write and own -- for control flow no requirement here needs. ADR 0003: climb when a requirement needs it |
| Tool loop: `langgraph.prebuilt.create_react_agent` | still exported by `langgraph-prebuilt 1.1.0` | the same loop | the older path; the ladder and `contract.py` name `create_agent`, whose middleware carries the budget |
| **Fakes:** `langchain_core`'s `GenericFakeChatModel` | yes -- `langchain-core 1.6.9` | scripted `AIMessage`s, tool calls included; subclasses the real `BaseChatModel` | `bind_tools` is the base class's, which raises `NotImplementedError`; a subclass returns itself from `bind_tools` and counts its calls |
| Fakes: a hand-written `BaseChatModel` | -- | anything | a double that agrees with itself (`.claude/rules/sdd/tests.md`) |

**Decision:** adopt `create_agent` with `ModelCallLimitMiddleware`, and
`GenericFakeChatModel` behind a thin test subclass -- because a dependency the
project already owns covers both, and the delta is two settings and one method.
Chosen by the agent under the owner's standing delegation of 2026-10-12, as
ADR 0005 records.

## Orchestration rung

**A tool loop: `create_agent` and its middleware.** ASSISTANT-TOOL-LOOP needs
model, tool, model -- standard control flow. ASSISTANT-MODEL-CALL-BUDGET needs a
bound on it, which `ModelCallLimitMiddleware` enforces. No requirement here
needs routing policy, an interrupt, a review loop or fan-out, so the
hand-written graph waits. The roadmap's "one `StateGraph`" is met by the
`CompiledStateGraph` `create_agent` returns; the recorded disagreement in
wording is resolved by ADR 0003's ladder, which outranks a roadmap proposal.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | the developer starting from the starter; the three signals above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | three requirements, each with a counter-example; the budget's is the off-by-one |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | all deterministic: the routes, counts and types are asserted; no generated text is |
| Data -- provenance, freshness, what happens when a source is withdrawn | N-A | the graph reads no data it did not create |
| Untrusted input -- anything ingested that this project did not write | Partial | a user message reaches a model -- but the registered model is offline and fixed, and the only tool is a test fake. The data-never-instruction requirement and its adversarial case arrive with the first real model or tool (safety slice) |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | a graph id, `assistant` -- ADR 0005. No env var: nothing is read yet. Node names are not yet an interface |
| Failure -- what the user sees when a dependency is down | N-A | no external dependency at run time: the model is offline, the tool is local |
| Cost -- tokens, time, money and storage per run | Clear | no model call costs anything yet; the budget caps model calls per run at 10 for when one does |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the project owner, as usual |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Is 10 model calls per run the right budget? | OPEN -- needs a real model's runs to measure | A starting policy (ADR 0005). Revisited by the first change that installs a provider, against measured runs |
| 2 | Does `langgraph-api 0.16.0` still make the outbound connections the pack measured on 0.15.1? | OPEN -- needs the probe | `serve-first-graph-locally` re-runs the probe; nothing here starts the server |

# 5. The first graph is `assistant`: a tool loop, registered, offline until a provider is required

Date: 2026-10-12
Status: Accepted. Its "no tools" was superseded by ADR 0006 (task-store-read-only),
its "the rung is the tool loop" by ADR 0007 (assistant-as-a-graph).

## Context

The foundation slice (`docs/roadmap.md`) puts the first LangGraph graph into
the starter. Three things it settles are expensive to reverse:

- **A graph id is an interface.** The local server keys assistants, threads and
  runs by it; renaming it later strands every thread created under the old one.
- **The rung.** ADR 0003 says to take the lowest rung that expresses the
  control flow a requirement needs. The first graph's requirements are a tool
  loop and a bound on model calls -- standard control flow, which
  `create_agent` and its middleware already express.
- **The model the registered graph runs.** No provider is installed, and none
  may be until a requirement needs one. A registered graph is built at import,
  so it needs a model object then.

## Decision

- **The graph id is `assistant`.** It is registered in `langgraph.json` as
  `./src/starter/infrastructure/agents/registry.py:assistant`, the registry's
  only export.
- **The rung is the tool loop.** `infrastructure/agents/factory.py` compiles
  the graph with `langchain.agents.create_agent`, the model and tools passed
  in as objects. The roadmap's "one `StateGraph`" is satisfied by what
  `create_agent` compiles; a hand-written `StateGraph` waits for a requirement
  whose control flow needs it (routing policy, an interrupt, a review loop).
- **The run is bounded by a domain budget.** `MODEL_CALLS_PER_RUN = 10` lives
  in `domain/agents/budgets.py`; `ModelCallLimitMiddleware(run_limit=...,
  exit_behavior="error")` enforces it, so an exhausted budget is an error, not
  a message that reads like an answer. The value is a starting policy, chosen
  without a real model to measure against; it is revisited with the first
  provider.
- **The registered graph's model is offline until a requirement names a
  provider.** `infrastructure/models.py` -- the only place a model is built --
  builds a deterministic offline model from `langchain_core`'s fakes. It gives
  the same fixed answer to every message and reaches no network.
- **The registered graph has no tools.** Every tool needs a capability manifest
  (`.claude/rules/langgraph/graphs.md`), and its format is decided in the
  safety slice with the first real tool. Tests drive the tool loop with a
  recording fake tool through the same factory.

## Consequences

**Good.** The registry, `langgraph.json` and the three architecture checks that
waited for them are live; the server has a graph to serve without a key; every
route the requirements name is proved with fakes, through the factory the
registry uses.

**Costly.** The registered graph answers with a fixed sentence until a provider
arrives: it is a walking skeleton, not an assistant anyone uses. Climbing to a
hand-written graph later replaces `factory.py`'s body and keeps the id; the
node names `create_agent` chooses (`model`, `tools`) are not part of the
interface until a requirement says so.

**Reversal.** Renaming `assistant` is an interface change with a migration
(old threads). Moving off the offline model is the point of the first provider
change, not a reversal.

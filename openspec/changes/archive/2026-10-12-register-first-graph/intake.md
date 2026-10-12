# Intake

- **Class:** structural
- **Intent:** For a developer starting from this starter: one LangGraph graph
  runs end to end with a fake model and a fake tool, is exported by
  `infrastructure/agents/registry.py`, and is registered in a root
  `langgraph.json` -- while the default suite still needs no service, no key
  and no model.
- **Because:** it adds the project's first runtime dependencies (`langchain`,
  `langgraph`, pinned), the first graph id -- a deliberate interface -- and the
  first state schema, and it creates a subsystem, `infrastructure/agents/`,
  that three skipped architecture checks are waiting for. Each is expensive to
  reverse.
- **Approved:** the user, 2026-10-12, approved this class and intent as
  presented, choosing to split the roadmap's Foundation slice in two ("Split,
  start 1a"). This change is 1a. The local-only entry point, `.env` loading in
  `config/`, the `live` smoke run through `scripts/serve.sh` and the
  connection-probe re-run are 1b, `serve-first-graph-locally`, which gets its
  own intake after this one lands.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

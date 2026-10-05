# Roadmap

The first changes, in order. Each is a **proposal for `/intake`**, not an
approved plan: the class, the requirements and the design are decided when the
change starts, with the owner, through the loop. Each slice leaves the default
suite free of services.

## Product: LangGraph, a slice at a time

1. **Foundation** (structural). Dependencies: `langchain-core`, `langchain`,
   `langgraph`, and `langgraph-cli[inmem]` in the dev group -- each pinned, each
   justified by a requirement. A `fake_llm` fixture. One `StateGraph` run end to
   end with a fake model and a fake tool. `infrastructure/agents/registry.py`
   and a root `langgraph.json` naming only its exports, with no `env` (the
   architecture checks are waiting for it), validated by `langgraph validate`
   for its schema. **Local only** (ADR 0004):
   - a requirement that every entry point the project ships starts from the
     local-only environment that `scripts/serve.sh` uses;
   - `config/` loads `.env` without overriding what is already set;
   - a local smoke run, `live`: `bash scripts/serve.sh`, then through the
     server's API -- the graph id is served, a fake-model run streams, an
     interrupt resumes on the same thread;
   - the connection probe in `.claude/rules/langgraph/runtime.md` re-run
     against the pinned versions, and its result recorded.
2. **Correctness** (structural). A versioned state contract; routing and budget
   policies in `domain/`; topology tests on node names, transitions, interrupt
   points and terminal outcomes; scenario fixtures for every route; architecture
   tests for nodes (no environment reads, no exits, no inline clients).
3. **Durability** (structural). Interrupt and resume; a checkpointer chosen with
   build-or-adopt (`langgraph-checkpoint-sqlite`, `-postgres`); thread
   ownership, state-version and retention policy; encryption at rest. Proved
   without `langgraph up`, which needs a LangSmith key: a run paused,
   the graph rebuilt on the same store, the run resumed -- on SQLite in the
   default suite, on Postgres as `live`.
4. **Safety** (structural). Capability manifests, authorisation at the tool
   boundary, audit events, adversarial injection tests asserting no
   unauthorised effect; the sandbox decision for Deep Agents.
5. **Operations** (structural). Local tracing and log correlation --
   OpenTelemetry to a collector on this machine, never LangSmith -- runbooks,
   deployment and rollback, checkpoint migration.
6. **Deep Agents** (structural), only if a requirement justifies it: one
   constrained harness, sandboxed, with reviewed profiles and its own evaluations.

Not before their slice: multi-agent delegation, long-term memory, a general
shell, production persistence. Each multiplies the attack surface and makes
early contracts harder to stabilise.

## Method

- **Turn on CI and branch protection.** `docs/ci/README.md` -- one command and
  two settings, done by a person.
- **Pressure-test the discipline skills** (`.claude/sdd/pressure-tests.md`):
  `/accept`, `/tdd`, `/eval`, `/verify` first.
- **Prove portability**: install the method into a project in another language
  and land one change touching only its `sdd.toml`. Every other edit needed is a
  tier violation to record, then fix.
- **Read `sdd stats` after the first five changes**: the stages each class
  skipped, and whether a bounded change takes more steps than it used to.

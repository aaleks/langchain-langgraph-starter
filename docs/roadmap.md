# Roadmap

The first changes, in order. Each is a **proposal for `/intake`**, not an
approved plan: the class, the requirements and the design are decided when the
change starts, with the owner, through the loop. Each slice leaves the default
suite free of services.

## Product: LangGraph, a slice at a time

1. **Foundation** (structural), split in two at intake.
   - **1a, `register-first-graph` -- landed.** Dependencies pinned to the
     checked minor; a `fake_llm` fixture; the `assistant` graph, a
     `create_agent` tool loop bounded by a domain budget, run end to end with a
     fake model and a fake tool; `infrastructure/agents/registry.py` and a root
     `langgraph.json` with no `env`; architecture checks that every registered
     export is a compiled graph and that `langgraph validate` accepts the
     config (ADR 0005).
   - **1b, `serve-first-graph-locally` -- landed.** `live` tests serve
     `assistant` through `scripts/serve.sh` -- the graph id served, a run
     streaming and completing, a second process reading the thread -- from a
     shell that switches LangSmith on, under a connection probe that records
     nothing beyond 127.0.0.1 (`langgraph-api` 0.16.0, measured). Of the five
     items planned:
     - the server's entry point starting from the local-only environment --
       proved end to end on the running server; the suite's own seal landed in
       1a. The project ships no other entry point yet: a CLI brings its own;
     - the local smoke run -- landed, without its interrupt: **an interrupt
       resumed on the same thread moves to Durability (3)**, where interrupts
       are designed -- the registered graph has none to resume;
     - the connection probe -- landed as a test that re-runs at every upgrade;
     - **`.env` loading in `config/` moves to "Before the first provider"**:
       nothing reads a setting yet;
     - teaching the fake model to stream tool calls -- not needed: the served
       graph runs the offline model, whose answer streams as text. It returns
       with the first streamed tool call.
   - **Before the first provider** -- the first change that installs a model
     provider or registers a real tool, whichever slice it belongs to, brings
     these with it (register-first-graph, `verify.md`):
     - a requirement that untrusted text -- user input, tool output, retrieved
       content -- is data, never instruction, and an adversarial case asserting
       no unauthorised effect;
     - a decision on `invalid_tool_calls`: a terminal error, or handed back;
     - a tool-call budget beside the model-call budget,
       `ModelRetryMiddleware(..., on_failure="error")` for transient failures,
       and a deadline on the provider call;
     - `config/` loading `.env` without overriding what is already set
       (python-dotenv's default) -- the first setting read needs it; the model
       chosen in a factory function the registry calls, not at import;
     - `MODEL_CALLS_PER_RUN` re-measured against real runs;
     - the "only `infrastructure/models.py` builds a model" check extended to
       every module, the provider imported inside its builder.
2. **Correctness** (structural). A versioned state contract; routing and budget
   policies in `domain/`; topology tests on node names, transitions, interrupt
   points and terminal outcomes; scenario fixtures for every route; architecture
   tests for nodes (no environment reads, no exits, no inline clients).
3. **Durability** (structural). Interrupt and resume; a checkpointer chosen with
   build-or-adopt (`langgraph-checkpoint-sqlite`, `-postgres`); thread
   ownership, state-version and retention policy; encryption at rest. Proved
   without `langgraph up`, which needs a LangSmith key:
   - a run paused, the graph rebuilt on the same store, and the run resumed;
   - an old checkpoint resuming after a state-schema change;
   - another tenant's thread refused.

   On SQLite in the default suite, on Postgres as `live`.
4. **Safety** (structural). Capability manifests, authorisation at the tool
   boundary, audit events, adversarial injection tests asserting no
   unauthorised effect; the sandbox decision for Deep Agents. **Required:** a
   fixture-proven architecture check that fails when a tool can be registered
   without its capability manifest, or when a write-capable one lacks its
   schemas, its authorisation boundary or its audit event. The manifest's
   format is decided here, with the first real tool. The rule itself is
   already in `.claude/rules/langgraph/graphs.md`.
5. **Operations** (structural). Local tracing and log correlation --
   OpenTelemetry to a collector on this machine, never LangSmith -- runbooks,
   deployment and rollback, checkpoint migration.
6. **Deep Agents** (structural), only if a requirement justifies it: one
   constrained harness, sandboxed, with reviewed profiles and its own evaluations.

Not before their slice: multi-agent delegation, long-term memory, a general
shell, production persistence. Each multiplies the attack surface and makes
early contracts harder to stabilise.

## Method

- **Protect `main`.** CI is on (2026-10-12); `docs/ci/README.md` has the two
  settings, done by a person -- which GitHub offers a private repository only on
  a paid plan.
- **Upstream the suite seal into the langgraph pack** (`docs/learnings.md`,
  2026-10-12): seed `LOCAL_ONLY` in the conftest and its hostile-environment
  check, held equal to `serve.sh` and the settings by the method's tests -- a
  method change, with its version bump.
- **Pressure-test the discipline skills** (`.claude/sdd/pressure-tests.md`):
  `/accept`, `/tdd`, `/eval`, `/verify` first.
- **Prove portability**: install the method into a project in another language
  and land one change touching only its `sdd.toml`. Every other edit needed is a
  tier violation to record, then fix.
- **Read `sdd stats` after the first five changes**: the stages each class
  skipped, and whether a bounded change takes more steps than it used to.

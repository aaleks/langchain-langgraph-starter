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
   and a root `langgraph.json` naming only its exports -- checked against the
   pinned CLI's schema at the time. A Studio smoke guide: graph registered and
   rendered, a fake-model run streams, an interrupt resumes on the same thread.
2. **Correctness** (structural). A versioned state contract; routing and budget
   policies in `domain/`; topology tests on node names, transitions, interrupt
   points and terminal outcomes; scenario fixtures for every route; architecture
   tests for nodes (no environment reads, no exits, no inline clients).
3. **Durability** (structural). Interrupt and resume; a checkpointer chosen with
   build-or-adopt; thread and state-version policy; persistence integration
   tests; a `langgraph up --wait` smoke run against the Docker-backed server.
4. **Safety** (structural). Capability manifests, authorisation at the tool
   boundary, audit events, adversarial injection tests asserting no
   unauthorised effect; the sandbox decision for Deep Agents.
5. **Operations** (structural). Tracing and log correlation, runbooks,
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

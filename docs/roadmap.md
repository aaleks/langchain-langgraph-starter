# Roadmap

The first changes, in order. Each is a **proposal for `/intake`**, not an
approved plan: the class, the requirements and the design are decided when the
change starts, with the owner, through the loop. Each slice leaves the default
suite free of services.

## Product: an approval-gated task assistant

Chosen by the owner on 2026-10-12. The `assistant` manages a **local task
list**: it reads and searches it freely, and **every write -- create, close,
reassign -- pauses for the person's approval** and resumes on the same thread.
Its model is served by the owner's **local Open WebUI**, through its
OpenAI-compatible API, configured in `.env` (written by the owner, never an
agent). Each slice below exists because this product needs it; what the
original plan listed without a product (versioned state, routing policy,
durability, safety) arrives in the slice whose requirement asks for it.

1. **Foundation** -- landed, in two changes.
   - **1a, `register-first-graph`** (#4): dependencies pinned to the checked
     minor; a `fake_llm` fixture; `assistant`, a `create_agent` tool loop
     bounded by a domain budget, run end to end with fakes; the registry and a
     root `langgraph.json` with no `env`; architecture checks on registration,
     compiling and the suite's local-only environment (ADR 0005).
   - **1b, `serve-first-graph-locally`** (#6): `live` tests serve `assistant`
     through `scripts/serve.sh` from a hostile shell, under a connection probe
     that records nothing beyond 127.0.0.1 (`langgraph-api` 0.16.0, measured;
     CI's `live` job green on Linux). Its interrupt moved to slice 4, its
     `.env` loading to slice 2: neither had a requirement yet.
2. **The model: Open WebUI** -- landed, **`connect-openwebui-model`** (#8),
   after six verify passes:
   - settings read by `config/` from the environment, then `.env` -- read as
     written, never written into the environment, the environment winning;
     the three documented in `.env.example`;
   - a partial configuration, or a URL that is not Open WebUI's address,
     refused at start, naming the variable and never quoting the value;
   - `ChatOpenAI` against Open WebUI's `/api`, built only in
     `infrastructure/models.py`, the provider imported inside its builder; the
     registry chooses it from the process's settings, the offline model when
     nothing is configured;
   - transient failures -- a timeout, a failed connection, 408, 429, 500,
     502-504 -- retried twice by `ModelRetryMiddleware(on_failure="error")` on
     a domain predicate; a 120 s timeout on every wait for the model;
   - LOCAL-SERVER-STAYS-LOCAL's one exception: the Open WebUI the owner
     configures; the "only `models.py` builds a model" check over the whole
     package, provider SDK clients included;
   - a `live` test of a real run through Open WebUI -- it reaches the owner's
     server, which has yet to answer it: the model id in `.env` is not one
     that server lists.
3. **The task store, read only** -- split in two by the owner.
   - **3a, `task-store-read-only`** (#9) -- landed after five verify passes.
     - The task list: one SQLite file at `TASKS_DB`, through the standard
       library. Its schema is versioned from the first, and an interrupted
       write is recovered (ADR 0006).
     - The owner's `starter tasks add`.
     - `list_tasks` and `search_tasks`, each with a capability manifest the
       factory checks. A write, or a manifest nothing enforces, is refused.
       Each tool holds a reader its holder cannot make write.
     - A tool-call budget of 20 per run.
     - What one read hands the model is bounded, whatever wrote the file:
       132,713 characters measured.
   - **3b, `bound-the-tool-loop`** (#10) -- landed after four verify passes.
     Every route of the tool loop now ends in a stated outcome:
     - The budgets were measured on the owner's model: N = 20 on
       `gpt-5.4-mini`, at most 2 turns, 2 calls, 16,582 characters and 344
       output tokens. `scripts/measure_tool_loop.py` re-runs it.
     - A malformed call goes back to the model, never ends the run as an
       empty answer.
     - A model call is limited to 150,000 characters.
     - A reply is capped at 4,096 tokens, and a cut-off reply ends the run.
       A local Ollama model needs `num_predict` set in Open WebUI.
     - Calls carrying tools are not streamed: streamed arguments are
       re-parsed worse than linearly. The timeout of 300 s covers a whole
       reply.
     - A short prompt is sent first. Task text giving orders is proved to
       change nothing.

     Not done: search by assignee -- the measurement found it missing, and
     it would be a change of its own.
4. **Approval-gated writes** (structural). Create, close and reassign, each
   proposed by the model and executed only after the person approves:
   `interrupt()` with the proposal as payload, `Command(resume=...)` on the
   same thread, and a rejection that ends without an effect. The rung is
   decided here -- `create_agent` with human-in-the-loop middleware, or a
   hand-written `StateGraph` -- and with a hand-written graph come the old
   Correctness slice's parts: a versioned state contract, routing policy in
   `domain/`, topology tests. Writes are idempotent per thread and step, and
   audited.
5. **Durability** (structural). The approval may wait: a durable checkpointer
   chosen with build-or-adopt (`langgraph-checkpoint-sqlite`); a run paused,
   the graph rebuilt on the same store, and resumed; thread ownership; an old
   checkpoint resuming after a state change; retention.
6. **Operations** (structural). Local tracing and log correlation --
   OpenTelemetry to a collector on this machine, never LangSmith -- and a
   runbook.

Not planned: Deep Agents, multi-agent delegation, long-term memory, a general
shell. Each would need a requirement this product does not have.

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

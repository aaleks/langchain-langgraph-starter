# CLAUDE.md

A LangChain / LangGraph starter, developed spec-first with proof.

**A walking skeleton, on purpose.** What exists is the method, five layers with
their contracts and checks, and one graph: `assistant`, a `create_agent` tool
loop registered in `langgraph.json`, its model the owner's local Open WebUI when
`.env` configures it and an offline fixed-answer model otherwise
(`docs/decisions/0005-the-assistant-graph.md`), and two read-only tools over
the owner's task list -- a SQLite file the owner adds to with `starter tasks
add` -- each with a capability manifest (`docs/decisions/0006-the-task-store.md`).
It is becoming an
**approval-gated task assistant** over a local task list, its model served by
the owner's local Open WebUI -- the slices in `docs/roadmap.md`, each through
the loop like everything else.

## The method

Every change starts with `/intake`. The laws, the non-negotiables and the loop
are in `.claude/rules/sdd/laws.md`, loaded in every session; read it as part of
this file. The reference is `.claude/sdd/METHOD.md`; a walkthrough of one
change is `.claude/sdd/GUIDE.md`.

## Stack

- **Python 3.13 with uv.** The package is `starter`, installed editable by `uv sync`.
- **pytest, ruff, import-linter** (with grimp) -- the dev group in `pyproject.toml`.
- **OpenSpec 1.14** for the spec lifecycle, pinned and run through
  `bash .claude/sdd/sdd.sh openspec <args>`. Needs Node 20.19+.
- **LangChain 1.4, langchain-core 1.6, LangGraph 1.2; langchain-openai 1.7 and
  openai 3.29** (the Open WebUI client); **python-dotenv 1.2** (`.env`) --
  runtime dependencies, each bounded to the minor it was checked against;
  `langgraph-cli[inmem]` in the dev group. They run on this machine only --
  never through LangSmith (below).

## Commands

```bash
uv sync                                   # install, dev group included
bash scripts/check.sh                     # everything CI runs -- the one list
bash scripts/check.sh live                # also tests needing services, models, quota
bash scripts/serve.sh                     # the local LangGraph server, once a graph is registered
uv run starter tasks add "title"          # add to the task list the assistant reads (TASKS_DB)
uv run pytest                             # the suite; no services, no keys
uv run pytest tests/architecture          # the layer contracts
bash .claude/sdd/sdd.sh check             # requirement <-> test traceability
bash .claude/sdd/sdd.sh status            # where each in-flight change stands
bash .claude/sdd/sdd.sh openspec list     # changes in flight (--specs for capabilities)
```

`uv run pytest` excludes `live` tests, so it passes on a machine with nothing
started. Keep it that way: the default suite never depends on a service.

## Architecture

```
cli  ->  infrastructure  ->  (application | config)  ->  domain
```

| Layer | Holds | May import |
|---|---|---|
| `domain/` | pure decisions: precedence, validation, routing, budgets, policies | the standard library only |
| `config/` | finding and loading configuration; the only reader of `os.environ` and `.env` | `domain`, `dotenv` |
| `application/` | use cases, prompts, output contracts | `domain`, `langchain_core`, `pydantic` -- never a runtime |
| `infrastructure/` | adapters: model builders, stores, tracing; every graph, in `agents/` | `domain`, `config`, `application` |
| `cli/` | arguments, output, exit codes; the only `sys.exit` | everything |

`application | config` are independent: a use case takes its settings as
arguments. All of it is enforced by `tests/architecture/`, each rule proved to
fail on a fixture package. Detail: `docs/architecture/overview.md`.

Two conventions carry the weight:

- **Decisions take their inputs as arguments.** `resolve_model(env, override)`,
  never `os.getenv` inside. A test hands it a dict.
- **Everything below the CLI raises; only the CLI exits.** A library that kills
  the interpreter cannot be used from a test, a notebook or an Agent Server.

## LangGraph -- the adoption boundary

- **Take the lowest rung that expresses the control flow a requirement needs**:
  one call in a use case; a `create_agent` tool loop; a hand-written
  `StateGraph`. Climb when a requirement needs the control flow, never before.
  The ladder: `.claude/skills/discover/references/orchestration-ladder.md`.
- **Graphs are adapters.** `langgraph` and `deepagents` are imported only under
  `infrastructure/agents/` -- `create_agent` included, because it compiles a
  graph. Routing, approval, budget and retry *policy* are domain functions.
- **`langgraph.json` registers only compiled graphs exported by
  `infrastructure/agents/registry.py`.** Graph ids are deliberate interfaces.
- **No default test calls a model**: fake models, fake tools, every route proved
  by the route it takes. In-memory checkpointing is never evidence of durability.
- **Local only, never through LangSmith**
  (`docs/decisions/0004-langgraph-runs-locally.md`). No hosted Studio, no
  LangSmith tracing, no `langgraph up` or `langgraph deploy`. The server starts
  only with `bash scripts/serve.sh`: 127.0.0.1, and an environment in which
  nothing reaches LangSmith. This session runs in that same environment, and
  its settings deny the alternatives. The deny rules match text, so a Bash
  command that merely mentions a denied phrase is refused too: search with the
  Grep tool, and write a commit message or PR body that names one to a file
  (`git commit -F`). Topology is
  `draw_mermaid()` text; runs are the local server's API
  (`.claude/rules/langgraph/runtime.md`).
- **A graph seen running is not evidence it is production-ready**, in the local
  server or in a diagram. Its routes are proved by fake-model tests.

The full plan, in slices: `docs/roadmap.md`. The decisions:
`docs/decisions/0003-langgraph-is-an-adapter.md` and
`docs/decisions/0004-langgraph-runs-locally.md`.

## Where things are

```
src/starter/            the package -- five layers, each with its contract; graphs in infrastructure/agents/
tests/                  unit, integration, acceptance; architecture checks the checkers
tests/evals/golden/     evaluation ground truth -- written by a human only
openspec/               specs/ (living truth), changes/ (in flight), the sdd-proof schema
.claude/                the SDD method: skills, agents, rules, hooks, sdd/ (tooling and docs)
sdd.toml                the method's adapter: where specs and tests live, the commands
docs/decisions/         ADRs -- one per decision that is expensive to reverse
docs/roadmap.md         the first changes, in order
docs/ci/                how CI is enabled and changed; a person moves a workflow into .github/
docs/learnings.md       what went wrong, and what it left behind
scripts/                check.sh (every check, one list); serve.sh (the local LangGraph server)
```

## Rules for this project

1. **No product code without an approved change.** `/intake` first, even for
   something small -- the class decides how small the process is.
2. **Do not over-engineer the starter.** No abstraction, framework or pattern
   without a requirement that needs it. Adopting a maintained library that
   already solves the problem is the opposite of over-engineering -- that is
   what the frame's build-or-adopt slot is for.
3. **CI is proposed, never written, by an agent.** `.github/workflows/` is
   refused by the edit guard and denied in settings; write it under `docs/ci/`.
4. **This repository is the method's canonical source.** A change to a shipped
   method file needs a version bump, a `.claude/sdd/CHANGELOG.md` entry and a
   regenerated manifest (`bash .claude/sdd/sdd.sh manifest`) -- `check.sh`
   fails otherwise. Method changes go through the loop too.
5. **When the code and a requirement disagree, the disagreement is the finding.**
   Say which one you think is wrong, with the evidence; the user decides.

## Inherited lessons

Learned in the project this method came from, each because it cost a debugging
session. The project's own lessons go in `.claude/rules/project/lessons.md`.

- **Load `.env` before any setting is read.** A module-level constant evaluated
  at import misses it, and the symptom looks like a server problem.
- **`create_agent` and every LangGraph runtime are infrastructure.** An unbounded
  structured-output retry runs to LangGraph's step ceiling; bound the run, and
  treat a contract failure as an outcome rather than retrying it.
- **`ModelRetryMiddleware` defaults to `on_failure="continue"`**, which turns a
  failure into a message that reads like an answer. Use `"error"`.
- **`localhost` inside a container is the container.** Reach a service on the
  host through its documented host address (`host.docker.internal`).
- **A check that cannot fail is worse than none, because it is believed.**
  import-linter exits 0 when it cannot find the package; an allowlist over an
  empty import set passes. Every check here is proved to fail on a fixture.

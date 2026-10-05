# Frame

## Outcome

A developer who starts from this repository, or installs the method with
`--packs langgraph`, can run, inspect and test graphs on their own machine
without a single connection to LangSmith. The agent is denied every command
that would reach LangSmith or expose the development server. A graph change
arrives with a design record and checks that cover its structure, routes,
errors, persistence and local runtime.

Observable signals:

- **No connection leaves the machine.** `scripts/serve.sh` starts the server
  and a graph runs through its API with **zero** outbound `connect()` calls,
  measured with `strace -f -e trace=connect`. This holds even when the calling
  shell exports LangSmith keys.
- **A fresh install is local-only.** `install --packs langgraph` produces a
  project whose settings deny those commands and whose `scripts/serve.sh`
  exists, without editing anything by hand.
- **The checks fail when they should.** Each new architecture check is red on
  a fixture built to break it.

## Existing options considered

What was checked, on 2026-10-05, with `langgraph-cli 0.4.32`,
`langgraph-api 0.15.1`, `langgraph-runtime-inmem 0.35.1`, `langgraph 1.2.13`,
`langchain-core 1.6.6` and `langsmith 0.14.4` installed in a scratch
environment. The sources were read and the dev server was run under an audit
hook and `strace`.

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| LangGraph Studio, web (`langgraph dev`'s default) | yes -- the current CLI links it | graph view, runs, interrupts, time travel | **It is LangSmith's web app.** `langgraph_api/cli.py:306` builds `https://smith.langchain.com/studio/?baseUrl=<local server>` and opens it in the browser. Refused by the user's constraint. |
| Studio through `--studio-url` | yes -- a CLI flag | the same UI, served by another origin | The flag replaces only the origin (`cli.py:306`), which means a self-hosted LangSmith. It is still LangSmith. Out. |
| `langgraph up` (the Docker server) | yes | a Postgres-backed Agent Server | `langgraph_cli/cli.py:297-298` says it "requires env var LANGSMITH_API_KEY with access to LangSmith Deployment" or an enterprise licence key. With a key, the server reports usage to LangSmith (see below). Out. |
| `langgraph dev` (in-memory Agent Server), local | yes -- langgraph-cli 0.4.32 | the real server API on 127.0.0.1: assistants, threads, runs, streaming, interrupts, `GET /assistants/{id}/graph` | It makes three outbound calls, each to switch off: CLI analytics to Supabase (`langgraph_cli/analytics.py`, off with `LANGGRAPH_CLI_NO_ANALYTICS=1`); a PyPI version check (`langgraph_api/cli.py:524`, off with `LANGGRAPH_NO_VERSION_CHECK=true`); and **with any LangSmith key present**, usage metadata POSTed to `api.smith.langchain.com/v1/metadata/submit` every 300 s (`langgraph_api/metadata.py`) -- **even with `LANGSMITH_TRACING=false`** -- plus tracing switched on when it is not set (`config/__init__.py:581`). |
| Graph diagram: `get_graph().draw_mermaid()` | yes -- langchain-core 1.6.6 | the topology as Mermaid text, produced locally | `draw_mermaid_png()` defaults to `MermaidDrawMethod.API` (`langchain_core/runnables/graph.py:639`), which sends the graph to mermaid.ink. Use the text form. |
| Agent Chat UI (langchain-ai/agent-chat-ui) | not checked in this change | a chat front end for a local server | Optional and run by a person; not adopted. Recorded so it is not re-proposed as if unknown. |

Measured, not assumed. A trivial graph was served and run once through the
local API in each setup:

| Setup | Outbound connections |
|---|---|
| defaults, `--no-browser` | Supabase (CLI analytics), pypi.org (version check) |
| `LANGGRAPH_CLI_NO_ANALYTICS=1`, `LANGGRAPH_NO_VERSION_CHECK=true`, no LangSmith key | **none** -- 0 `connect()` calls under strace |
| the same plus `LANGSMITH_API_KEY` set | `api.smith.langchain.com` -- run traces and usage metadata |
| the same plus `LANGSMITH_TRACING=false` | `api.smith.langchain.com` -- usage metadata: `POST .../v1/metadata/submit` was sent (a 403 came back) |
| any LangChain process, `LANGSMITH_TRACING=true`, **no key at all** | `api.smith.langchain.com` -- `POST /runs/multipart` with the run's inputs and outputs (a 403 came back) |
| the same, with `LANGSMITH_ENDPOINT` and `LANGCHAIN_ENDPOINT` set to `http://127.0.0.1:9` | **none** -- 16 refused attempts on 127.0.0.1:9, and a loud error naming the endpoint |

The 403s may come from this sandbox's egress filter rather than from LangSmith;
either way the request, body included, was sent. So an empty key does not stop
tracing: tracing is switched off, and the endpoint is pointed at a closed local
port as a backstop.

The enforcement has its own build-or-adopt question:

| Option | Covers | Delta |
|---|---|---|
| Claude Code permission `deny` rules (native) | `*` anywhere in a Bash rule; each subcommand of a compound command matched; leading variable assignments skipped for deny | none to build. The reason for a denial is not shown, so CLAUDE.md states the rule. |
| A new PreToolUse hook on Bash | a reason in the refusal | parsing shell in bash 3.2, a new adapter key, and tests -- to do what the native rules already do |

**Decision:** adopt `langgraph dev`, bound to 127.0.0.1, behind a thin wrapper
(`scripts/serve.sh`). The wrapper empties every LangSmith credential, switches
tracing and the CLI's two calls off, and points the LangSmith endpoint at a
closed local port. Adopt Claude Code's native deny rules for the agent.
Build nothing else. Chosen by the user's constraint, with the agent's
recommendation; hosted Studio is not replaced -- its jobs go to the local API,
`draw_mermaid()` and route tests.

## Orchestration rung

N-A -- a method change; no graph is built.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | zero outbound connections, measured; a fresh install is local-only |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | the serve wrapper, the pack seeding, the deny rules and the status fix are each a requirement with a counter-example; the prose rules carry no requirement because no test can prove prose |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | all deterministic |
| Data -- provenance, freshness, what happens when a source is withdrawn | Partial | the evidence is pinned to the versions above. `LANGGRAPH_NO_VERSION_CHECK` is marked "not in public docs ... dev-only" in its source, so an upgrade can silently drop it: the probe is re-run on every upgrade (question 2) |
| Untrusted input -- anything ingested that this project did not write | Clear | `serve.sh` reads `.env` and the configured env file only to find variable names; values are never printed |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | new: `scripts/serve.sh` and its flags, the settings additions, pack seeds in install; no graph id yet |
| Failure -- what the user sees when a dependency is down | Clear | `serve.sh` refuses with the variable or flag named; a missing `langgraph.json` or CLI is reported, not crashed through |
| Cost -- tokens, time, money and storage per run | N-A | no model call; the new checks run in milliseconds |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the repository owner; ADR 0004 records the decision |

## Defect

Found while opening this change -- a defect in the method's own status, fixed
inside this change.

- **Symptom:** `sdd.sh status` reports `next: specs` for a change whose
  `.openspec.yaml` sets `skip_specs: true`, while `openspec status` marks specs
  as skipped and moves on.
- **Reproduction:** in a scratch clone, `openspec new change probe-x`, add
  `skip_specs: true`, write `intake.md` with class structural, run frame:
  `sdd.sh status` prints `specs-` and, once frame exists, `next: specs`.
- **Root cause:** `sddlib/status.py` derives stages from the change's files
  only and never reads `.openspec.yaml`, so a declared skip looks like a
  missing stage. Evidence: `grep -n skip_specs .claude/sdd/sddlib/*.py` finds
  nothing.
- **Requirement that should have caught it:** `HOOKS-NEXT-STAGE` -- amended
  with a scenario for a declared `skip_specs`.

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | May a project using the pack choose LangSmith after all? | answered by the user's constraint for this repository | The pack's default is local-only. A project opts out by editing its own settings and `serve.sh` -- both project-owned once seeded -- and records why in an ADR. |
| 2 | Will the opt-out variables survive upgrades? | OPEN | Resolved per upgrade: re-run the connection probe in `.claude/rules/langgraph/runtime.md` whenever `langgraph-cli` or `langgraph-api` moves. Owner: repository owner. |
| 3 | Which versions does the starter pin? | deferred to the foundation slice | The roadmap's first slice adds and pins the dependencies through the loop. Nothing is installed by this change. |

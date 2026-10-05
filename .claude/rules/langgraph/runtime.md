---
paths:
  - "langgraph.json"
  - "scripts/serve.sh"
  - "src/*/infrastructure/agents/registry.py"
  - "tests/acceptance/**"
---

# Running LangGraph -- on this machine, never through LangSmith

The project's decision: `docs/decisions/0004-langgraph-runs-locally.md`. No
hosted Studio, no LangSmith tracing, no LangSmith Deployment, no `langgraph up`.
The reasons were measured, not assumed: LangGraph's tooling reaches LangSmith by
default, in ways that `LANGSMITH_TRACING=false` alone does not stop.

## Start the server one way

```bash
bash scripts/serve.sh               # http://127.0.0.1:2024
bash scripts/serve.sh --port 8123   # if 2024 is taken -- otherwise the server picks a random port and says so
```

`scripts/serve.sh` binds 127.0.0.1 and never opens a browser. It passes on only
`--port`, `--no-reload`, `--allow-blocking`, `--wait-for-client`,
`--server-log-level`, `--n-jobs-per-worker` and `--debug-port`. It starts the
server from the **local-only environment**:

- tracing off through all four switches;
- every LangSmith credential empty;
- the LangSmith endpoint at a closed local port;
- the CLI's analytics and version check off.

It refuses to start when `langgraph.json` has an `env` key, or when `.env` sets
a LangSmith credential or switches tracing on. The banner still prints a
"Studio UI" link to smith.langchain.com: it is printed, never opened. Leave it.

Never, in any form: `langgraph dev` run directly (it opens Studio and inherits
your shell's keys), `--tunnel`, `--studio-url`, `--host`, `langgraph up`,
`langgraph deploy`, `draw_mermaid_png()` with its default (it posts the graph to
mermaid.ink). The agent's settings deny these commands; a person is trusted to
follow this file.

Every other `langgraph` command -- `validate`, `new`, `build` -- posts usage
analytics unless `LANGGRAPH_CLI_NO_ANALYTICS=1`. The agent's settings set it;
a person running one from their own shell exports it first.

## What replaces Studio

| Job | Use |
|---|---|
| see the topology | `graph.get_graph().draw_mermaid()` -- text, rendered wherever Mermaid is; or `GET /assistants/{assistant_id}/graph?xray=true` on the local server |
| run, stream, inspect state | `langgraph_sdk.get_client(url="http://127.0.0.1:2024")`: `threads.create()`, `runs.wait(...)` or `runs.stream(...)`, `threads.get_history(...)` -- or `curl` |
| interrupt and resume | run until the interrupt, then `runs.wait(thread_id, assistant_id, command={"resume": ...})` on the same thread |
| read the API | `GET /openapi.json`. `/docs` renders the same API, but loads its viewer from a CDN |
| prove a route | a fake-model scenario test -- see `graphs.md`. Inspecting a run is debugging, never evidence |

## langgraph.json

Names only exports of `infrastructure/agents/registry.py`, under stable ids,
and carries **no `env`**: the server loads that file over its own environment,
which would undo the wrapper. Settings reach the graphs through `config/`, the
one loader of `.env` -- which must load without overriding a variable already
set (python-dotenv's default), or `.env` could undo the wrapper from inside. The
project's architecture tests check the file once it exists.

## The in-memory server is for development

Its threads live in `.langgraph_api/`, which is gitignored; delete it freely. It
proves nothing about durability -- a durable checkpointer composed in the
project does, paused and resumed across a rebuilt graph.

## Re-measure at every upgrade

The local-only environment was measured against `langgraph-cli 0.4.32` and
`langgraph-api 0.15.1`. One of its switches, `LANGGRAPH_NO_VERSION_CHECK`, is
undocumented, and its source calls it dev-only. When either package moves:

1. Start the server through the wrapper under
   `strace -f -e trace=connect -o connects.txt`, with LangSmith keys exported in
   the shell.
2. Run one graph through the API.
3. Count the `connect()` calls to anything but 127.0.0.1.

It must be zero. Anything else is a finding, and the wrapper and the agent's
settings change together: one environment, in two places, held equal by the
method's tests.

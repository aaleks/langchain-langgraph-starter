# Design

Why: `frame.md`; scope: `intake.md`. No production code changes: the server,
`scripts/serve.sh`, the registry and `langgraph.json` are used as they are. What
this change adds is their proof -- the project's first `live` tests.

## Context

`scripts/serve.sh` starts `langgraph dev` on 127.0.0.1 from the local-only
environment; the method's tests prove what it passes to `uv`, but nothing has
run the server against this project's registered graph. register-first-graph
proved the graph through `invoke`; the server runs it through its own API,
asynchronously, with an in-memory checkpointer.

## Decisions

| File | Holds |
|---|---|
| `tests/acceptance/agents/test_local_server.py` | `TestServesTheAssistant`, `TestStaysLocal` -- `live`; one server for both, module-scoped |
| `tests/acceptance/agents/probe/sitecustomize.py` | the connection probe: an audit hook appending `socket.connect` and `socket.getaddrinfo` records, and one `start` record with the process's argv, to the file named by `PROBE_LOG` |
| `tests/localserver.py` | the harness: a free port on 127.0.0.1, `bash scripts/serve.sh` started in its own process group, `/ok` awaited, the process tree stopped and the port seen free |

- **One server, from a hostile shell.** The fixture starts the server with
  `LANGSMITH_TRACING=true`, `LANGCHAIN_TRACING_V2=true` and a fake
  `LANGSMITH_API_KEY` exported over the suite's sealed environment -- the shell
  a person might have. Both requirements run against it: serving correctly and
  staying local are one run, not two.
- **The probe rides on `PYTHONPATH`.** `serve.sh` exports its variables and
  passes the rest of the environment on, so a `sitecustomize` on `PYTHONPATH`
  loads into `uv run`'s Python and any process it spawns. The probe records its
  own `start` with the argv, so the test can prove it was loaded in the
  process running `langgraph` -- a probe that never loaded would report
  nothing, and nothing reads like a pass.
- **"Beyond this machine"** is decided by one pure function in the test module,
  `beyond_this_machine(records)`: a connect or lookup whose host is not
  `127.0.0.1`, `::1` or `localhost`. Its counter-example is a scenario.
- **The probe's blind spot is a rule, not a hope.** An asyncio connect to a
  literal IP is invisible to the hook on Windows (frame.md, measured); every
  target the local-only environment guards against is a hostname, caught at
  its lookup. The design says so here, and the probe's docstring says so.
- **Stopping the server is part of the proof.** Windows: `taskkill /T /F` on
  the `bash` process's tree; POSIX: `killpg` on its session. Then the port is
  checked free -- a test that leaves a server running poisons the next one.
- **The second process is a real one:** `sys.executable -c` with
  `langgraph_sdk`, reading `threads.get_state` -- not a second client object in
  the same process.

## Orchestration design

N-A -- no graph is built or changed.

## Risks

- [The probe misses an async connect to a literal IP] -> every guarded target
  is a hostname; recorded in the frame, this design and the probe.
- [A stray server survives a failed test] -> the harness stops the tree in a
  `finally` and asserts the port free.
- [`langgraph-api` changes what it calls home] -> exactly what this test is for:
  it runs at every upgrade, `bash scripts/check.sh live`.
- [The live tier never runs] -> `check.sh live` and CI's on-demand `live` job
  both run it; the default suite never needs a service.

## Migration and rollback

N-A -- tests only. Rollback removes them; the server is unchanged.

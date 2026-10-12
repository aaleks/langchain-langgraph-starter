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
| `tests/acceptance/agents/test_local_server.py` | `TestServesTheAssistant`, `TestStaysLocal` -- `live`; one server for the module, every request made in its lifetime, every assertion read after it stops |
| `tests/acceptance/agents/probe/sitecustomize.py` | the connection probe: an audit hook appending a `start` record with the argv, then every `socket` connect, lookup and datagram send, to the file named by `PROBE_LOG` |
| `tests/localserver.py` | the harness: a hostile environment, a throwaway working copy, Git for Windows' bash, a free port, `/ok` awaited without a proxy, a graceful stop |

- **A shell that is actually hostile** (verify pass 1, finding 1). The server's
  environment is the test process's with every `LOCAL_ONLY` variable removed,
  then all four tracing switches `true`, the LangSmith API and control-plane
  keys set, and both endpoints at `http://langsmith-hostile.invalid`. Every one
  of those, `serve.sh` must override. The endpoint is a `.invalid` name (RFC
  6761): a `serve.sh` that stopped overriding it is caught by the probe at the
  lookup -- measured, 14 lookups -- and can deliver nothing. The CLI's analytics
  and the version check are left unset, not hostile: their only target is a
  real third party, so the probe could catch a regression only by letting one
  request out; the method's tests prove `serve.sh` exports them.
- **One server, in a throwaway working copy** (finding 4). `scripts/serve.sh`,
  `langgraph.json` and `src/` are copied into a temporary directory, and
  `UV_PROJECT` points `uv` at this repository's environment. The in-memory
  store, `.langgraph_api/`, is written there -- never into the developer's own,
  which a test thread would pollute and a developer's own assistant would make
  "exactly one" false. One module-scoped server serves both requirements.
- **Git for Windows' bash** (finding 3), found beside `git` -- never WSL's,
  which `System32` puts first on a PowerShell `PATH` and which would run
  `serve.sh` in Linux, without the probe's variables.
- **Stopped as a person stops it** (finding 2). Windows: `CTRL_BREAK_EVENT` to
  the server's new process group; POSIX: `SIGTERM` to its session. Measured on
  Windows: the server runs its lifespan shutdown ("Stopping dev persistence
  flush loop") and the port frees. It then exits by re-raising the signal, so
  `atexit` handlers do not run -- for a person's Ctrl+C either. Only a server
  that will not stop is killed (`taskkill /T /F`, `SIGKILL` to the group), and
  the test fails on it: the record would be incomplete.
- **The probe rides on `PYTHONPATH`,** which `serve.sh` passes on, and records
  its own `start` with the argv: the test proves it was loaded in the process
  running `langgraph dev`. A probe that never loaded records nothing -- and
  nothing reads like a pass.
- **"Beyond this machine"** is one pure function in the test module,
  `beyond_this_machine(records)`: a connect or lookup whose host is not
  `127.0.0.1`, `::1`, `localhost` or none. Its counter-example is in the default
  suite. A connect to `127.0.0.1:9` -- `serve.sh`'s closed LangSmith endpoint --
  is local, but it means tracing came back on: the traced-run scenario asserts
  there is none.
- **What the probe cannot see,** written in the probe and here: an asyncio
  connect to a literal IP (Windows' Proactor loop raises no event); native code
  opening its own sockets (grpcio's C core); processes that are not Python
  (`uv`). Every target the local-only environment guards against is a hostname
  reached from Python, recorded at its lookup. `strace` on Linux sees
  everything, and stays runtime.md's tool for that.
- **Accepted, not fixed:** a hard kill of pytest itself can orphan the server
  (no job object); the free port is released a moment before the server binds
  it -- a loud, rare flake, never a false pass.

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

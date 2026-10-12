# Frame

## Outcome

A developer can start the starter's graph on their own machine with
`bash scripts/serve.sh`, drive it through the server's API, and know -- by
re-running one command, not by trusting a measurement from another version --
that nothing left the machine.

Observable signals:

- `bash scripts/check.sh live` starts the server through `scripts/serve.sh`,
  runs `assistant` through the API, reads the thread from a second process, and
  passes.
- In the same run, started from a shell that exports a LangSmith key and
  switches tracing on, the server makes no connection and no name lookup beyond
  127.0.0.1 -- including for a run whose request asks for LangSmith tracing.
- The probe that says so re-runs at every upgrade as a test, on Windows and on
  Linux, in place of the one-off `strace` in `.claude/rules/langgraph/runtime.md`.

**Non-goals:** an interrupt and its resume, and `.env` loading in `config/`
(deferred, `intake.md`); a durable store; anything on a port beyond 127.0.0.1;
the method's own runtime rule, which is upstream's to change (`docs/learnings.md`).

## Existing options considered

Measured on 2026-10-12, Windows 11, `langgraph-cli 0.4.33`, `langgraph-api
0.16.0`, `langgraph-runtime-inmem 0.36.0`, `langgraph-sdk 0.4.6`. A probe server
was started with `bash scripts/serve.sh --port 2091 --no-reload` from a shell
exporting `LANGSMITH_TRACING=true`, `LANGCHAIN_TRACING_V2=true` and a fake
`LANGSMITH_API_KEY`, and driven through the API: the graph id was served, a run
streamed `metadata, values, updates, ..., values` and ended `human, ai`, a
second process read the thread as `["human", "ai"]`, and a run whose request
set `langsmith_tracing` completed. Over all of it the server made **one**
connection -- to `127.0.0.1`, asyncio's own self-pipe -- and **no** name lookup.

**The probe:**

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| `strace -f -e trace=connect` (runtime.md's method) | yes -- but Linux only | every `connect()` of every process | not on this machine; a manual step |
| **Python audit hooks** (`sys.addaudithook`, PEP 578), loaded into the server through a `sitecustomize` on `PYTHONPATH` -- which `serve.sh` passes on | stdlib, Python 3.8+ | measured: every synchronous `socket.connect`, and every `socket.getaddrinfo`, synchronous or from asyncio | **blind spot, measured:** an asyncio connect to a *literal IP* raises no `socket.connect` event on Windows' Proactor loop. Every outbound target this guards against -- LangSmith, the CLI's analytics, PyPI -- is a hostname, and is caught at its lookup |
| `pytest-socket` / an in-process monkeypatch | yes | the test process only | the server is another process: covers nothing that matters here |
| A network sandbox (firewall rules, a container with no network) | -- | everything | a privileged, platform-specific setup per run; a container is not this machine |

**The client:** `langgraph_sdk`'s `get_sync_client` -- already installed, as a
dependency of `langgraph` -- over hand-written HTTP: it is the client the
server documents, and the API it wraps is what runtime.md tells a person to use.

**Decision:** adopt the audit hook, with its blind spot written down and the
hostname rule that covers it; adopt `langgraph_sdk`. Build only the test
harness: start the server, wait for `/ok`, stop its process tree. Chosen by the
agent under the owner's standing delegation.

## Orchestration rung

N-A -- this change serves the existing graph; it builds no graph.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | the developer running the server; the three signals above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | two requirements, each with a counter-example |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | deterministic: ids, event kinds, message types, the probe's records -- never text |
| Data -- provenance, freshness, what happens when a source is withdrawn | N-A | the server's in-memory threads; nothing read from outside |
| Untrusted input -- anything ingested that this project did not write | Clear | a client's request is untrusted: one that asks for LangSmith tracing is a scenario of LOCAL-SERVER-STAYS-LOCAL |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | none changes: `serve.sh`'s flags, the graph id and the API are used as they are |
| Failure -- what the user sees when a dependency is down | Clear | a server that never answers `/ok` fails the test with the server's own output attached |
| Cost -- tokens, time, money and storage per run | Clear | no model; seconds per `live` run; threads in `.langgraph_api/`, gitignored |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the project owner, as usual |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Should runtime.md's `strace` probe become this test, in the method? | OPEN -- a method change | Recorded upstream with the suite seal (`docs/roadmap.md`, Method). Owner: the project owner. Review by: 2026-12-31 |

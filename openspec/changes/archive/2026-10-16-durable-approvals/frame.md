# Frame

## Outcome

The owner can leave a write waiting for approval, stop or lose the local
server, start it again, and still approve or reject that write -- applied once.
The signal: a live test pauses a run, restarts `scripts/serve.sh` on the same
files, and resumes it; another kills the server, re-registers the thread under
its id, and resumes it.

Measured before any requirement (2026-10-16, `langgraph-api` 0.16.0, the
stand-in model; probes in the session's scratchpad):

| Stop | The dev server's own files | A SQLite checkpointer named in `langgraph.json` |
|---|---|---|
| graceful (`CTRL_BREAK`) | thread `interrupted`, resumed, task written | the same |
| killed (`taskkill /F`) right after the pause | thread not found | thread not found |
| killed, then `threads.create(thread_id, if_exists="do_nothing")` | `KeyError: 'messages'` -- the checkpoints were lost | resumed, task written |

The dev runtime keeps its thread records and its own checkpoints in pickle
files under `.langgraph_api/`, flushed every 10 seconds
(`langgraph_runtime_inmem/_persistence.py`). A checkpointer named in
`langgraph.json` takes the checkpoints; the thread records stay the runtime's.

Non-goals: thread ownership (5b); retention, deletion, a thread's size (5c);
re-registering lost threads at start-up (the owner chose not to, 2026-10-16);
a production runtime, which ADR 0004 rules out.

## Existing options considered

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| `langgraph-checkpoint-sqlite` | 3.1.2 released 2026-10-12, in `langchain-ai/langgraph` beside the checkpointer the project already uses; installs against `langgraph` 1.2.14 | checkpoints in one SQLite file, async for the server, serialization without pickle | composing it for the server; the version stamp |
| the dev server's own files | part of `langgraph-runtime-inmem`, which the dev group already pins | a graceful restart | pickle; lost on a kill (measured); "for development" |
| `langgraph-checkpoint-postgres` | maintained, same repository | everything | a database service running for every run and test |

**Decision:** adopt `langgraph-checkpoint-sqlite`, named in `langgraph.json`
through the server's custom-checkpointer hook, plus a thin layer that stamps
the state's version. Chosen by the owner, 2026-10-16: "SQLite checkpointer
(Recommended)"; the promise, "Checkpoints, plus re-register (Recommended)".

## Orchestration rung

N-A -- the graph is unchanged; this changes where its checkpoints live.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | the owner; the restart and the kill, resumed, in live tests |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | a rebuilt graph resumes once; a newer checkpoint refused; a lost thread not found until re-registered |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | every requirement deterministic; fakes and the stand-in model |
| Data -- provenance, freshness, what happens when a source is withdrawn | Clear | the checkpoint file is the server's own; a missing file is created empty; retention is 5c |
| Untrusted input -- anything ingested that this project did not write | Partial | a checkpoint file another tool wrote: read with LangGraph's serializer, no pickle; its version stamp decides |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | `CHECKPOINTS_DB`; `langgraph.json`'s `checkpointer` key; the `state_version` metadata key |
| Failure -- what the user sees when a dependency is down | Clear | a file that cannot be opened stops the server at start, naming it; a newer checkpoint refuses the run, naming both versions |
| Cost -- tokens, time, money and storage per run | Partial | a few KB a checkpoint; growth is 5c's |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the owner |

## Defect

N-A

## Open questions

None. Re-registering at start-up, measured unneeded for a graceful stop, was
put to the owner and declined.

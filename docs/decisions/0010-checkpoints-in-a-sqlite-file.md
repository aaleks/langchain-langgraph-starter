# 10. The local server keeps checkpoints in a SQLite file, each stamped with the state's version

Date: 2026-10-16
Status: Accepted. Extends ADR 0009 (writes wait for the owner's approval) and
ADR 0004 (LangGraph runs locally).

## Context

A write waits for the owner's approval in a checkpoint (ADR 0009). The local
server's dev runtime kept checkpoints in pickle files under `.langgraph_api/`,
flushed every 10 seconds. Measured on 2026-10-16 with `langgraph-api` 0.16.0:
a graceful restart kept a paused approval; a kill right after the pause lost it.

The owner chose (2026-10-16):
- the store: "SQLite checkpointer (Recommended)";
- the promise: "Checkpoints, plus re-register (Recommended)" -- after a kill,
  a client re-registers the thread by id; no start-up reconciliation.

## Decision

- **`langgraph-checkpoint-sqlite`** (`AsyncSqliteSaver`, `>=3.1.2,<3.2`) holds
  the threads' checkpoints, in the file the setting `CHECKPOINTS_DB` names
  (`.data/checkpoints.sqlite3` by default).
- **`langgraph.json` names it** through the server's custom-checkpointer hook:
  `"checkpointer": {"backend": "custom", "path":
  "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`.
  This is the second entry beside the graphs that names code, after ADR 0009's
  `http.app`; a test pins it.
- **Each checkpoint carries `state_version`** in its metadata, written by the
  saver. A checkpoint stamped newer than the code is refused before any node
  runs; none or an older one is loaded, the state contract migrating. The
  decision is the domain's `checkpoint_version_refusal`.
- **The thread records stay the dev runtime's.** After a kill, a thread the
  server lost is re-registered with `threads.create(thread_id=...,
  if_exists="do_nothing")`, then resumed from the file.
- **Strict serialization**, set in code: no pickle, and a msgpack value
  naming a constructor outside LangGraph's and LangChain's safe types is
  never called.
- **A copy keeps each checkpoint's stamp**; a thread holding one this code
  refuses is not copied.
- **No encryption at rest yet** -- the owner's choice, 2026-10-16: the file
  is on the owner's disk beside the task list, which holds the same titles
  unencrypted. Revisited with slice 5b's local token.
- **`CHECKPOINTS_DB` never names the task list's file.**

## Consequences

**Good:**
- A paused approval survives a kill, not only a graceful stop.
- Checkpoints are no longer pickle.
- A rollback cannot misread a newer checkpoint.

**Costly:**
- One more dependency, and `langgraph-checkpoint` moves to 4.3.
- After a kill, a thread must be re-registered before Agent Chat UI shows it.
- The file grows until slice 5c decides retention; deleting a run and
  pruning history are unsupported until then.
- Anyone who can read the owner's disk can read past conversations.
- Threads paused before this decision are not carried into the file.

**Reversal:** remove the `checkpointer` key; the dev runtime's checkpointer
returns. Checkpoints written to the file are not carried back.

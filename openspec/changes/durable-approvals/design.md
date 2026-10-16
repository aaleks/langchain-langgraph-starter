# Design

## Context

The assistant pauses each write for the owner's approval (ADR 0009). On the
local server, the pause lived in the dev runtime's own checkpointer, kept in
pickle files under `.langgraph_api/` and flushed every 10 seconds: a graceful
restart kept it, a kill lost it (frame.md, measured). The owner chose a SQLite
checkpointer, and a promise of "checkpoints, plus re-register" (2026-10-16).

## Decisions

1. **The checkpointer is `langgraph-checkpoint-sqlite`'s `AsyncSqliteSaver`**,
   bounded `>=3.1.2,<3.2`. It brings `langgraph-checkpoint` 4.3 (from 4.2) and
   `aiosqlite`; nothing else in the project changes with them -- the suite is
   the proof.
2. **The server composes it through `langgraph.json`**:
   `"checkpointer": {"backend": "custom", "path":
   "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`.
   - `durable_checkpointer()` is an async context manager, as the server's
     hook expects: it reads the process's settings, opens the file
     `checkpoints_db_path(settings)` names, and yields the saver; the server
     closes it at shutdown.
   - The registry's graph still has no checkpointer of its own: the server
     supplies it, a test supplies an `InMemorySaver` or this saver.
   - `langgraph.json` stays free of `env`; `serve.sh` is unchanged.
3. **The state's version is stamped by the saver, not the graph.**
   `VersionedSqliteSaver` subclasses `AsyncSqliteSaver`:
   - `aput` writes `state_version: ASSISTANT_STATE_VERSION` into each
     checkpoint's metadata;
   - `aget_tuple` -- how every run, resume or continue loads its thread's
     checkpoint -- asks the domain's `checkpoint_version_refusal(found,
     current)` and raises `CheckpointVersionError` when it refuses.

   Alternatives: a state channel stamped by `start_run` -- but a resume or a
   continue starts at another node, and the check would be repeated in each;
   the graph's config metadata -- read by nothing before a node runs.
4. **What a version means is a domain decision**,
   `domain/agents/state_versions.py`: none -- written before the stamp --
   and any version up to the code's are loaded, the state contract migrating
   (v1 has no `write_decisions`, which `start_run` sets); a newer one, or
   anything that is not a positive whole number, is refused.
5. **The setting `CHECKPOINTS_DB`**, beside `TASKS_DB` in `config/`: the same
   resolution, default `.data/checkpoints.sqlite3` -- gitignored with `.data/`.
6. **After a kill, the thread is re-registered by the client.** The server's
   own thread records stay the dev runtime's, flushed every 10 seconds. A
   thread it lost is found again with
   `threads.create(thread_id=<id>, if_exists="do_nothing")`, after which the
   approval resumes it from the file. The owner declined a start-up
   reconciliation: it would lean on the dev runtime's internals.
7. **Serialization is LangGraph's, without pickle.** The saver's serializer is
   `JsonPlusSerializer` as `langgraph-checkpoint-sqlite` builds it, no
   `pickle_fallback`. The file is the server's own, written by nothing else.

## Orchestration design

N-A -- the topology, the nodes and the routes are unchanged (ADR 0007's
table, as amended by ADR 0009).

## Risks

- **[A thread lost after a kill]** -> its checkpoints are in the file; the
  client re-registers it by id. Agent Chat UI does not list it until then.
- **[`.langgraph_api/` deleted]** -> the same: the thread records go, the
  checkpoints stay.
- **[A rollback meets a newer checkpoint]** -> refused by the stamp, naming
  both versions, nothing written. Deleting that thread's checkpoints, or
  moving forward again, is the owner's choice.
- **[The custom-checkpointer hook changes with `langgraph-api`]** -> the live
  tests restart the real server; re-measure at every upgrade, with the
  local-only probe (runtime.md).
- **[The file grows]** -> retention and a thread's size are 5c.

## Migration and rollback

- **Threads paused before this change** lived in the dev runtime's pickles;
  they do not move to the file. A thread whose checkpoints are not in the
  file is not found by the new checkpointer: the owner starts it again.
- **Rollback:** revert the merge. `langgraph.json` loses the key, and the dev
  runtime's checkpointer returns; the file stays, unread.

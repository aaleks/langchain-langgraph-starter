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
   - **The stamp is the version of the code that wrote the checkpoint.** A
     future version that changes a channel's shape migrates it on load, in
     this saver, so a checkpoint written by version N always holds N's
     state; versions 1 and 2 need none (verify pass 1).
   - **A copy keeps each stamp** (`acopy_thread`): the server's own copy
     wrote each checkpoint through `aput`, re-stamping newer state as this
     code's -- measured, a rollback's refusal bypassed. A thread holding a
     refused checkpoint is not copied.
   - **History is listed as stored**, unrefused: it only reads.
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
7. **Serialization is LangGraph's, strict.** The saver's serializer is
   `JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)`,
   set in code, whatever `LANGGRAPH_STRICT_MSGPACK` says: the default let a
   msgpack value name any importable callable and called it on load
   (measured: `os.mkdir`, verify pass 1). The file outlives the process
   that wrote it.
8. **No encryption at rest yet** -- the owner's choice, 2026-10-16. The
   file is on the owner's disk beside the task list, which holds the same
   titles unencrypted. Revisited with 5b's local token. Nothing is scrubbed
   before a checkpoint: what the run holds -- the transcript, the tools'
   answers, the run's metadata -- is what the file holds.
9. **`CHECKPOINTS_DB` never names the task list's own file**: the task store
   is the only module that opens it (ADR 0006), and the saver would add its
   tables and switch it to WAL (measured, verify pass 1).

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
- **[What the SQLite saver lacks]** -> `adelete_for_runs` and `aprune`: the
  server's `DELETE /threads/{id}/runs/{id}` answers 500, a `rollback`
  cancel leaves the cancelled run's checkpoints, and history is not pruned.
  5c, with retention.
- **[A thread copied while a write waits]** -> the key holds the thread
  (ADR 0009): approved on both, the write is applied twice. Two approvals
  by the owner; 5b decides who may copy.
- **[A kill between a write's commit and its checkpoint]** -> the thread
  comes back paused at `review_writes`, and the owner is asked again about
  a write already applied; any answer is the recorded outcome, applied
  once. 5c.
- **[One graph's version for the whole server]** -> the saver stamps every
  thread with the assistant's version. A second registered graph needs its
  own, by graph id.

## Migration and rollback

- **Threads paused before this change** lived in the dev runtime's pickles;
  they do not move to the file. Such a thread's record still reads
  `interrupted`, but approving it runs the graph from its start on an empty
  transcript: nothing is written, nothing refused (measured). The owner asks
  again. Refusing a resume with no checkpoint is 5c's.
- **Rollback:** revert the merge. `langgraph.json` loses the key, and the dev
  runtime's checkpointer returns; the file stays, unread.

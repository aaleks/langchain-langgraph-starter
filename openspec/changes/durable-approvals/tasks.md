# Tasks

Critical path: the setting, then the version policy, then the saver, then the
server's composition. The story test is LOCAL-SERVER-DURABLE-APPROVAL's live
`TestDurableApprovals`: red until the last group lands.

## 1. The story test

- [x] 1.1 `tests/acceptance/agents/test_local_server.py::TestDurableApprovals`
  -- graceful restart, kill and re-register, kill and not re-registered, the
  checkpointer pinned in `langgraph.json`; `tests/localserver.py` learns to
  restart on the same working copy and to kill

## 2. SETTINGS-CHECKPOINTS-DB, SETTINGS-ENVIRONMENT-WINS (modified)

- [x] 2.1 `TestCheckpointsDb` red, then `CHECKPOINTS_DB` and
  `checkpoints_db_path` in `config/settings.py`; `.env.example` documents it
- [x] 2.2 `TestEnvironmentWins`' spaces row with `CHECKPOINTS_DB`

## 3. ASSISTANT-CHECKPOINT-VERSION

- [x] 3.1 `tests/unit/domain/test_state_versions.py::TestCheckpointVersion` red,
  then `domain/agents/state_versions.py`: `checkpoint_version_refusal`,
  `CheckpointVersionError`
- [x] 3.2 `tests/integration/agents/test_durable_checkpoints.py::TestCheckpointVersion`
  red, then `infrastructure/agents/checkpointers.py`: `VersionedSqliteSaver`

## 4. ASSISTANT-PAUSED-ON-DISK

- [x] 4.1 `TestPausedOnDisk` red, then green on the saver: rebuilt, approved
  once; rebuilt, rejected

## 5. LOCAL-SERVER-DURABLE-APPROVAL -- the wiring, the story test green

- [x] 5.1 `durable_checkpointer()`; `langgraph.json`'s `checkpointer`;
  `langgraph-checkpoint-sqlite` bounded in `pyproject.toml`
- [x] 5.2 `TestDurableApprovals` green through `scripts/serve.sh`

## 6. Close

- [x] 6.1 Mutations of the new code, 9, each red; `durable_checkpointer()`
  itself proved live, by the restarts
- [x] 6.2 Documents: CLAUDE.md, ADR 0010, the getting-started and
  walkthrough guides, `.env.example`; the roadmap at archive

## 7. Verify pass 1 -- the fixes

- [x] 7.1 Strict deserialization set in code -- `TestStrictDeserialization`,
  the planted constructor red first
- [x] 7.2 `acopy_thread` keeps each stamp and refuses a newer thread -- red
  first
- [x] 7.3 The server's hook loaded by its file's path, handed settings; the
  folder created; the registered graph without a checkpointer -- red first
- [x] 7.4 An older and an unstamped pause resume; a refused run leaves the
  file's rows as they were
- [x] 7.5 `CHECKPOINTS_DB` naming the task list refused -- red first
- [x] 7.6 Live: the stop asserted graceful, or not; the checkpoints in the
  file `CHECKPOINTS_DB` names; the kill counter-example no longer a race
- [x] 7.7 The suite's `CHECKPOINTS_DB` isolated; SQLite's `-wal`/`-shm`
  ignored; the encryption decision, the limits and the migration recorded

## 8. Verify pass 2 -- the MINORs

- [x] 8.1 A copy of a thread holding any newer checkpoint refused; a paused
  thread's copy keeps its checkpoints, parents, writes and interrupt, its
  metadata its own thread id; history listed by the checkpointer itself
- [x] 8.2 The hook called with no argument, as the server calls it
- [x] 8.3 The kill counter-example approves before re-registering: not found,
  or applied once
- [x] 8.4 `LANGGRAPH_STRICT_MSGPACK` removed from the suite's environment; the
  refusal of the default file worded as it is -- red first
- [x] 8.5 `serve.sh`'s comment; the headers in each checkpoint, the refused
  copy's empty thread, the Windows alias, the copy applied twice -- recorded
- [x] 8.6 The proof lens's 7 surviving mutants, each now red

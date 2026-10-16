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

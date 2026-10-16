## ADDED Requirements

### Requirement: LOCAL-SERVER-DURABLE-APPROVAL
`langgraph.json` SHALL name the project's durable checkpointer, `{"backend": "custom", "path": "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`, so the local server keeps every checkpoint in the SQLite file `CHECKPOINTS_DB` names (SETTINGS-CHECKPOINTS-DB) the moment it is written, its folder created; the registered graph carries no checkpointer of its own, the server supplies it. A run paused for the owner's approval SHALL survive the server's stop and start: after a graceful stop, the thread is `interrupted` at `review_writes` and an approval on it applies the write once; after the server is killed, the server may not know the thread -- its own record of threads is flushed on a 10-second clock (measured, `langgraph-api` 0.16), so a flush may or may not have caught it -- and once a client re-registers it under its id, `threads.create(thread_id=..., if_exists="do_nothing")`, an approval applies the write once.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestDurableApprovals`, `tests/integration/agents/test_durable_checkpoints.py::TestTheServersCheckpointer`

#### Scenario: Stopped gracefully, started again
- **GIVEN** the server, its model the stand-in proposing `add_task(title="Call the plumber")`, a run on a new thread paused for approval
- **WHEN** the server is stopped gracefully and started again on the same files, and the thread resumed with an approval
- **THEN** the stop was graceful; after the start, the thread's status is `interrupted` and its next node `review_writes`; after the approval, its status is `idle`, the list holds `Call the plumber`, once, and the thread's checkpoints are in the file `CHECKPOINTS_DB` names

#### Scenario: Killed, the thread re-registered
- **GIVEN** the same pause, then the server killed -- its process tree ended at once
- **WHEN** it is started again on the same files, the thread re-registered under its id, and resumed with an approval
- **THEN** the list holds `Call the plumber`, once, and the thread's checkpoints are in the file `CHECKPOINTS_DB` names

#### Scenario: Counter-example -- killed, not re-registered
- **GIVEN** the same pause, the server killed and started again
- **WHEN** a client asks for the thread before re-registering it
- **THEN** the server finds it or not -- a flush may have caught it -- and the list holds no task

#### Scenario: Loaded as the server loads it
- **GIVEN** `durable_checkpointer`, loaded from the file `langgraph.json` names, handed settings whose `CHECKPOINTS_DB` is `<tmp>/nested/checkpoints.sqlite3`
- **WHEN** a run pauses on it
- **THEN** it is a `VersionedSqliteSaver`, `<tmp>/nested/` and the file exist, and the file holds the thread's checkpoints
- **AND** the registered graph's own checkpointer is none

#### Scenario: The checkpointer named, not by chance
- **THEN** `langgraph.json`'s `checkpointer` is exactly `{"backend": "custom", "path": "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`

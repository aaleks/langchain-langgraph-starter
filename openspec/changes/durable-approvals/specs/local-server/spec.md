## ADDED Requirements

### Requirement: LOCAL-SERVER-DURABLE-APPROVAL
`langgraph.json` SHALL name the project's durable checkpointer, `{"backend": "custom", "path": "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`, so the local server keeps every checkpoint in the SQLite file `CHECKPOINTS_DB` names (SETTINGS-CHECKPOINTS-DB) the moment it is written. A run paused for the owner's approval SHALL survive the server's stop and start: after a graceful stop, the thread is `interrupted` at `review_writes` and an approval on it applies the write once; after the server is killed, the server may not know the thread -- its own record of threads is flushed every 10 seconds (measured, `langgraph-api` 0.16) -- and once a client re-registers it under its id, `threads.create(thread_id=..., if_exists="do_nothing")`, an approval applies the write once.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestDurableApprovals`

#### Scenario: Stopped gracefully, started again
- **GIVEN** the server, its model the stand-in proposing `add_task(title="Call the plumber")`, a run on a new thread paused for approval
- **WHEN** the server is stopped gracefully and started again on the same files, and the thread resumed with an approval
- **THEN** after the start, the thread's status is `interrupted` and its next node `review_writes`; after the approval, its status is `idle` and the list holds `Call the plumber`, once

#### Scenario: Killed, the thread re-registered
- **GIVEN** the same pause, then the server killed -- its process tree ended at once
- **WHEN** it is started again on the same files, the thread re-registered under its id, and resumed with an approval
- **THEN** the list holds `Call the plumber`, once

#### Scenario: Counter-example -- killed, not re-registered
- **GIVEN** the same pause, the server killed and started again
- **WHEN** a client asks for the thread before re-registering it
- **THEN** the server answers that it is not found, and the list holds no task

#### Scenario: The checkpointer named, not by chance
- **THEN** `langgraph.json`'s `checkpointer` is exactly `{"backend": "custom", "path": "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`

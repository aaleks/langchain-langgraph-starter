## ADDED Requirements

### Requirement: ASSISTANT-PAUSED-ON-DISK
A run of the assistant paused for the owner's approval on the durable checkpointer SHALL resume on a checkpointer and a graph built anew on the same file -- as after the server's restart -- and the owner's decision SHALL decide the write once: approved, it is applied, and a second approval on a graph built anew again applies nothing more; rejected, nothing is written. Proved on `ainvoke`, the path the server runs.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_durable_checkpoints.py::TestPausedOnDisk`

#### Scenario: Paused, rebuilt, approved
- **GIVEN** a task list holding task 1, `Renew passport`, and a run on the thread `t1` whose model proposes `add_task(title="Call the plumber")`, paused on the durable checkpointer at `<tmp>/checkpoints.sqlite3`
- **WHEN** the checkpointer and the graph are built anew on that file and the run resumed with `{"decisions": [{"type": "approve"}]}`
- **THEN** the call is answered `{"outcome": "applied", "task_id": 2}`, the list holds `Renew passport` and `Call the plumber`, and `task_writes` holds one row, `approve`, `applied`
- **AND** resumed once more with an approval on a graph built anew again, the list and `task_writes` are unchanged

#### Scenario: Counter-example -- rebuilt, rejected
- **GIVEN** the same pause
- **WHEN** the run is resumed on a graph built anew with `{"decisions": [{"type": "reject"}]}`
- **THEN** the list holds `Renew passport` alone, and `task_writes` one row, `reject`, `rejected`

### Requirement: ASSISTANT-CHECKPOINT-VERSION
Every checkpoint the durable checkpointer writes SHALL carry the state's version in its metadata, `state_version`, `ASSISTANT_STATE_VERSION`: the version of the code that wrote it. A thread whose latest checkpoint carries a version newer than the code's SHALL be refused before any node runs -- `CheckpointVersionError`, naming both versions, nothing written to the task list or the checkpoint file and the model not called -- and its state cannot be read through the checkpointer either; its history is listed as stored. One that carries no version -- written before the stamp -- or an older one SHALL be loaded as it is, the state contract deciding the rest (ASSISTANT-STATE-CONTRACT). A thread's copy SHALL keep each checkpoint's stamp, and a thread holding a checkpoint the code refuses SHALL not be copied. What a version found means is the domain's `checkpoint_version_refusal`.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_state_versions.py::TestCheckpointVersion`, `tests/integration/agents/test_durable_checkpoints.py::TestCheckpointVersion`, `tests/integration/agents/test_durable_checkpoints.py::TestCheckpointVersionAcrossVersions`

#### Scenario: What a version found means, the code at version 2
| `state_version` found | Refused |
|---|---|
| none -- written before the stamp | no |
| `1` | no |
| `2` | no |
| `3` | yes: `3`, newer than `2` |
| `"2"` | yes: not a version |
| `true` | yes: not a version |
| `0` | yes: not a version |

#### Scenario: Stamped
- **GIVEN** a run paused on the durable checkpointer
- **THEN** every checkpoint row in the file carries `state_version` `2`

#### Scenario: Counter-example -- older code meets a newer checkpoint
- **GIVEN** a thread whose checkpoints carry `state_version` `3`
- **WHEN** code at version 2 runs it with new input
- **THEN** `CheckpointVersionError` is raised naming `3` and `2`, the model is not called, the list and `task_writes` are unchanged, and the file's checkpoints are the same rows, each stamped `3`

#### Scenario: An older checkpoint resumes
| The pause written by | Approved on code at version 2 |
|---|---|
| code at version 1, stamped `1` | applied once, task 2 |
| a checkpointer before the stamp, none | applied once, task 2 |

#### Scenario: A copy keeps each stamp
| The thread `t1`, stamped | Copied to `t2` by code at version 2 |
|---|---|
| `1` | copied, each checkpoint stamped `1` |
| `3` | refused: `CheckpointVersionError`, nothing under `t2` |

### Requirement: ASSISTANT-CHECKPOINT-STRICT
The durable checkpointer SHALL read a checkpoint with LangGraph's serializer in its strict mode, whatever the environment says: a msgpack value naming a constructor outside LangGraph's and LangChain's safe types SHALL NOT be called, and a value stored as pickle SHALL be refused. The file outlives the process that wrote it, so what it holds is read as untrusted.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_durable_checkpoints.py::TestStrictDeserialization`

#### Scenario: A planted constructor
- **GIVEN** a checkpoint in the file whose channel value is a msgpack extension naming `os.mkdir` on `<tmp>/made-by-a-checkpoint`
- **WHEN** the durable checkpointer loads the thread
- **THEN** `<tmp>/made-by-a-checkpoint` does not exist

#### Scenario: Counter-example -- a pickled value
- **GIVEN** a checkpoint row whose value is stored as `pickle`
- **WHEN** the durable checkpointer loads the thread
- **THEN** it is refused, the error naming `pickle`

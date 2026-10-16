# settings Specification

## Purpose
Settings are how the owner configures the assistant without touching code: read by `config/` from the process environment and from `.env`, the environment always winning, and handed inward as plain values.

## Requirements

### Requirement: SETTINGS-ENVIRONMENT-WINS
A setting SHALL be read from the process environment when the environment holds it -- an empty value included -- and from the repository's `.env` only when the environment does not, as written there: `${NAME}` is not expanded. Every value SHALL be read with the spaces around it removed, so a value of only spaces reads as empty. A missing `.env` SHALL read as empty, a `.env` that is not UTF-8 SHALL be refused naming the file, and reading SHALL change neither the environment nor the file -- nor open the file when the environment holds every setting.

- **Kind:** deterministic
- **Proved by:** `tests/integration/config/test_settings.py::TestEnvironmentWins`

#### Scenario: The environment, then .env
| Environment | `.env` | `OPENWEBUI_MODEL` read |
|---|---|---|
| `OPENWEBUI_MODEL=qwen3:8b` | `OPENWEBUI_MODEL=llama3.1:8b` | `qwen3:8b` |
| not set | `OPENWEBUI_MODEL=llama3.1:8b` | `llama3.1:8b` |
| `OPENWEBUI_MODEL=` (empty) | `OPENWEBUI_MODEL=llama3.1:8b` | empty |
| `OPENWEBUI_MODEL=   ` (spaces) | `OPENWEBUI_MODEL=llama3.1:8b` | empty |
| not set | `OPENWEBUI_MODEL="   "` (quoted spaces) | empty |
| not set, `PROBE=leaked` | `OPENWEBUI_MODEL=${PROBE}` | `${PROBE}` |

#### Scenario: Spaces around a value
| Each of `OPENWEBUI_URL`, `OPENWEBUI_API_KEY`, `OPENWEBUI_MODEL`, `TASKS_DB`, `CHECKPOINTS_DB` in the environment | Read |
|---|---|
| `   ` | empty |
| `  sk-local` followed by a tab | `sk-local` |

#### Scenario: The process's own settings
- **GIVEN** the process environment holding `OPENWEBUI_MODEL=qwen3:8b` and no other setting, and the repository's `.env` holding `OPENWEBUI_URL=http://localhost:3000`
- **WHEN** the process's settings are read
- **THEN** the model reads `qwen3:8b` and the URL `http://localhost:3000`, and the `.env` read is the one at the repository's root

#### Scenario: No .env, or one that is not UTF-8
| `.env` | Reading |
|---|---|
| none | every setting empty, no error |
| saved as UTF-16 | refused, naming the file |
| saved as UTF-16, the environment holding every setting | not opened: no error |

#### Scenario: Counter-example -- reading leaves the process environment as it was
- **GIVEN** a `.env` holding `OPENWEBUI_URL=http://localhost:3000` and a process environment without `OPENWEBUI_URL`
- **WHEN** the process's settings are read -- from its environment itself
- **THEN** `OPENWEBUI_URL` reads as `http://localhost:3000`, the process environment still does not hold it, and the file is unchanged

### Requirement: SETTINGS-KEY-NEVER-SHOWN
The Open WebUI API key SHALL appear neither in a settings object's text nor in the message of a configuration refused.

- **Kind:** deterministic
- **Proved by:** `tests/integration/config/test_settings.py::TestKeyNeverShown`

#### Scenario: A settings object, printed
- **GIVEN** settings holding the key `sk-secret-123`
- **THEN** their text contains `<set>` and not `sk-secret-123`

#### Scenario: A configuration refused
| Settings | Refusal names | Its message contains `sk-secret-123` |
|---|---|---|
| the URL and the key `sk-secret-123`, no model | `OPENWEBUI_MODEL` | no |
| all three, the URL's and the key's lines swapped: `OPENWEBUI_URL=sk-secret-123` | `OPENWEBUI_URL` | no |

#### Scenario: Counter-example -- what is not secret is shown
- **GIVEN** settings with the URL `http://localhost:3000` and the model `llama3.1:8b`
- **THEN** their text contains both

### Requirement: SETTINGS-TASKS-DB
The task list's file SHALL be the setting `TASKS_DB` -- a relative path taken from the repository's root, an absolute one as it is -- and `.data/tasks.sqlite3` under the repository's root when the setting is empty.

- **Kind:** deterministic
- **Proved by:** `tests/integration/config/test_settings.py::TestTasksDb`

#### Scenario: Where the task list is
| `TASKS_DB` | The task list's file |
|---|---|
| empty | `<repository>/.data/tasks.sqlite3` |
| `lists/home.sqlite3` | `<repository>/lists/home.sqlite3` |
| an absolute path, `<tmp>/tasks.sqlite3` | `<tmp>/tasks.sqlite3` |

#### Scenario: Counter-example -- the working directory does not decide
- **GIVEN** `TASKS_DB=lists/home.sqlite3`, read from a working directory other than the repository's root
- **THEN** the file is `<repository>/lists/home.sqlite3`

### Requirement: SETTINGS-CHECKPOINTS-DB
The threads' checkpoint file SHALL be the setting `CHECKPOINTS_DB` -- a relative path taken from the repository's root, an absolute one as it is -- and `.data/checkpoints.sqlite3` under the repository's root when the setting is empty; never the task list's own file: a `CHECKPOINTS_DB` naming the file `TASKS_DB` names SHALL be refused, naming both settings.

- **Kind:** deterministic
- **Proved by:** `tests/integration/config/test_settings.py::TestCheckpointsDb`

#### Scenario: Where the checkpoints are
| `CHECKPOINTS_DB` | The checkpoint file |
|---|---|
| empty | `<repository>/.data/checkpoints.sqlite3` |
| `state/threads.sqlite3` | `<repository>/state/threads.sqlite3` |
| an absolute path, `<tmp>/checkpoints.sqlite3` | `<tmp>/checkpoints.sqlite3` |

#### Scenario: Counter-example -- the working directory does not decide
- **GIVEN** `CHECKPOINTS_DB=state/threads.sqlite3`, read from a working directory other than the repository's root
- **THEN** the file is `<repository>/state/threads.sqlite3`

#### Scenario: Counter-example -- the task list's own file
- **GIVEN** `TASKS_DB` and `CHECKPOINTS_DB` both `<tmp>/tasks.sqlite3`
- **THEN** the checkpoint file is refused, naming `CHECKPOINTS_DB` and `TASKS_DB`

#### Scenario: Counter-example -- the default, the task list's own file
- **GIVEN** `CHECKPOINTS_DB` empty and `TASKS_DB` `.data/checkpoints.sqlite3`
- **THEN** it is refused: `the checkpoint file, <repository>/.data/checkpoints.sqlite3, is the task list's own (TASKS_DB): set CHECKPOINTS_DB to a file of its own`

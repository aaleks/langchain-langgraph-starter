## ADDED Requirements

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

## MODIFIED Requirements

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
| Each of `OPENWEBUI_URL`, `OPENWEBUI_API_KEY`, `OPENWEBUI_MODEL`, `TASKS_DB` in the environment | Read |
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

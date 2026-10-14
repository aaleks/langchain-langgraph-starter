## Purpose

The task list is what the assistant works on: one SQLite file on the owner's machine, written by the owner's `starter tasks add` and, from slice 4, by approved proposals; read by the assistant's tools.

## ADDED Requirements

### Requirement: TASKS-ADD
`starter tasks add TITLE [--assignee NAME] [--notes TEXT]` SHALL add one open task to the task list `TASKS_DB` names -- its title (at most `TITLE_MAX`, 200 characters), assignee (at most `ASSIGNEE_MAX`, 100) and notes (at most `NOTES_MAX`, 1,000), each with the spaces around it removed -- print its id alone on standard output, and exit 0. A blank title, or a field over its limit, SHALL be refused with exit status 2 and a message on standard error naming it -- `TITLE`, `--assignee`, `--notes` -- nothing written, the file not even created. A task list that cannot be opened or written -- TASKS-SCHEMA refusing it, or the file system -- and settings that cannot be read SHALL end the command with exit status 1 and a message on standard error naming the file, never a traceback.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/cli/test_tasks_cli.py::TestTasksAdd`

#### Scenario: Two tasks added
- **GIVEN** `TASKS_DB` naming a file that does not exist yet
- **WHEN** the owner runs `starter tasks add "  Renew passport " --assignee " sam "`, then `starter tasks add "Call the plumber" --notes " after 5pm  "`
- **THEN** the first prints `1` and the second `2`, the `starter` script exiting 0 each time
- **AND** the list's open tasks are, in order, `(1, "Renew passport", "sam", "")` and `(2, "Call the plumber", "", "after 5pm")` -- id, title, assignee, notes

#### Scenario: Counter-example -- refused, nothing written
| Given | Exit | Standard error names | Afterwards |
|---|---|---|---|
| the title `"   "` | 2 | `TITLE` | no file |
| the title `""` | 2 | `TITLE` | no file |
| a title of 201 characters | 2 | `TITLE` | no file |
| an assignee of 101 characters | 2 | `--assignee` | no file |
| notes of 1,001 characters | 2 | `--notes` | no file |
| `TASKS_DB` naming a task list at schema version 2 | 1 | the file | the file unchanged |
| `TASKS_DB` naming a directory | 1 | the directory | the directory unchanged |
| a `.env` saved as UTF-16, `TASKS_DB` not in the environment | 1 | the `.env` | no task list |

### Requirement: TASKS-LIST
The tool `list_tasks`, taking no arguments, SHALL return the open tasks in the order they were added -- at most `TASK_RESULTS_LIMIT` (50) -- as the JSON object `{"tasks": [{"id", "title", "assignee", "notes"}, ...], "more": n}`, `n` being how many more open tasks there are, its text as written: a letter outside ASCII as itself, not escaped. A task list another process holds locked SHALL end the run with the store's error after waiting `TASK_STORE_TIMEOUT_SECONDS` -- SQLite's own wait, which overshoots it (measured: 1 s given, 1.8 s taken; 5 s, 7.4 s).

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_tools.py::TestListTasks`

#### Scenario: The open tasks, in order
- **GIVEN** the tasks `Renew passport` (assignee `sam`) and `Call the plumber` (notes `after 5pm`), added in that order
- **WHEN** `list_tasks` is called
- **THEN** it returns `{"tasks": [{"id": 1, "title": "Renew passport", "assignee": "sam", "notes": ""}, {"id": 2, "title": "Call the plumber", "assignee": "", "notes": "after 5pm"}], "more": 0}`

#### Scenario: Text as written
- **GIVEN** the task `Čestitka za Ivana ☕`
- **WHEN** `list_tasks` is called
- **THEN** its result's text contains `Čestitka za Ivana ☕` as it is

#### Scenario: Past the limit
| Open tasks | Tasks returned | Their ids | `more` |
|---|---|---|---|
| 51 | 50 | 1 to 50 | 1 |
| 50 | 50 | 1 to 50 | 0 |
| 0 | 0 | -- | 0 |

#### Scenario: A list another process holds locked
- **GIVEN** a task list another connection holds in an exclusive transaction, and the store's wait set to 1 s
- **WHEN** the assistant runs, its model proposing `list_tasks`
- **THEN** the run raises `sqlite3.OperationalError` after at least 1 s and under 4 s, the model called once

#### Scenario: Counter-example -- a closed task is not listed
- **GIVEN** the tasks 1, 2 and 3, task 2 closed in the file
- **WHEN** `list_tasks` is called
- **THEN** it returns tasks 1 and 3, and `more` is 0

### Requirement: TASKS-SEARCH
The tool `search_tasks(query)` SHALL return the open tasks whose title or notes contain the query -- the spaces around it removed, ASCII letters matched regardless of case, every other character as itself, `%`, `_` and `\` included -- in the order they were added, at most `TASK_RESULTS_LIMIT`, in `list_tasks`' shape. A blank query, or one over `TITLE_MAX` characters, SHALL be handed back to the model as an error answering its call, the list not read.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_tools.py::TestSearchTasks`

#### Scenario: What a query matches
- **GIVEN** the open tasks `1 Renew passport`, `2 Call the plumber` (notes `bring the PASSPORT copy`), `3 Pay 100% deposit`, `4 Pay 1000 deposit`, `5 file_tax`, `6 file tax`, `7 copy a\b`, `8 copy ab`
| Query | Ids returned |
|---|---|
| `passport` | 1, 2 |
| `  PassPort ` | 1, 2 |
| `100%` | 3 |
| `file_tax` | 5 |
| `a\b` | 7 |
| `plumber` | 2 |
| `holiday` | none |

#### Scenario: Past the limit
- **GIVEN** 51 open tasks titled `Task 1` to `Task 51`
- **WHEN** `search_tasks("task")` is called
- **THEN** it returns tasks 1 to 50, and `more` is 1

#### Scenario: Counter-example -- a query refused, or a closed task
| Call | Result |
|---|---|
| `search_tasks("   ")`, through the assistant | an error tool message answering that call; the list not read |
| `search_tasks` with 201 `%`, through the assistant | an error tool message answering that call; the list not read |
| `search_tasks("passport")`, task 1 closed in the file | task 2 only |

### Requirement: TASKS-SCHEMA
Opening the task list SHALL create the file -- its directory included -- and its schema at version 1, in one transaction, when the file does not exist or holds no table at version 0; use a version-1 list as it is, first recovering a write that was interrupted; and refuse any other file -- a newer version, or a file that is not a task list -- naming the file, nothing written. The schema SHALL hold each field to its limit (TASKS-ADD).

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_store.py::TestTaskSchema`

#### Scenario: Which file is opened
| The file | Opening | Afterwards |
|---|---|---|
| does not exist, nor its directory | succeeds | the file exists at schema version 1, with no task |
| exists, 0 bytes | succeeds | schema version 1, with no task |
| a SQLite file at version 0 with no table | succeeds | schema version 1, with no task |
| a version-1 list holding 2 tasks | succeeds | the same 2 tasks, version 1, the file's bytes unchanged |
| a version-1 list holding 1 task, a write of 2,000 more interrupted, its journal left beside it | succeeds | 1 task, the journal gone |

#### Scenario: The schema holds the limits
- **GIVEN** a version-1 list
- **WHEN** a title of 201 characters is inserted into it directly
- **THEN** SQLite refuses the insert

#### Scenario: Counter-example -- a file that is not this task list is refused
| The file | Refusal names | The file afterwards |
|---|---|---|
| a SQLite file at schema version 2 | the file, and version `2` | unchanged |
| a SQLite file at version 0 holding another table | the file | unchanged |
| a text file, not SQLite | the file | unchanged |

# tasks Specification

## Purpose
The task list is what the assistant works on: one SQLite file on the owner's machine, written by the owner's `starter tasks add` and, from slice 4, by approved proposals; read by the assistant's tools.

## Requirements

### Requirement: TASKS-ADD
`starter tasks add TITLE [--assignee NAME] [--notes TEXT]` SHALL add one open task to the task list `TASKS_DB` names -- its title (at most `TITLE_MAX`, 200 characters), assignee (at most `ASSIGNEE_MAX`, 100) and notes (at most `NOTES_MAX`, 1,000), each with the spaces around it removed, free of C0 control characters and DEL but newline, carriage return and tab, and of characters UTF-8 cannot encode -- print its id alone on standard output, and exit 0. A blank title, or a field over its limit or holding such a character, SHALL be refused with exit status 2 and a message on standard error naming it -- `TITLE`, `--assignee`, `--notes` -- nothing written, the file not even created. A task list that cannot be opened or written -- TASKS-SCHEMA refusing it, or the file system -- and settings that cannot be read SHALL end the command with exit status 1 and a message on standard error naming the file, never a traceback.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/cli/test_tasks_cli.py::TestTasksAdd`

#### Scenario: Two tasks added
- **GIVEN** `TASKS_DB` naming a file that does not exist yet
- **WHEN** the owner runs `starter tasks add "  Renew passport " --assignee " sam "`, then `starter tasks add "Call the plumber" --notes " after 5pm  "`
- **THEN** the first prints `1` and the second `2`, the `starter` script exiting 0 each time
- **AND** the list's open tasks are, in order, `(1, "Renew passport", "sam", "")` and `(2, "Call the plumber", "", "after 5pm")` -- id, title, assignee, notes

#### Scenario: Notes over several lines
- **WHEN** the owner adds `Renew passport` with the notes `line one`, a carriage return and a newline, `line two`, a tab, `end`
- **THEN** the script exits 0, and the task's notes are stored as given
- **AND** notes holding U+0085, a C1 control character, are stored as given too

#### Scenario: Counter-example -- refused, nothing written
| Given | Exit | Standard error names | Afterwards |
|---|---|---|---|
| the title `"   "` | 2 | `TITLE` | no file |
| the title `""` | 2 | `TITLE` | no file |
| a title of 201 characters | 2 | `TITLE` | no file |
| an assignee of 101 characters | 2 | `--assignee` | no file |
| notes of 1,001 characters | 2 | `--notes` | no file |
| a title holding U+0001 | 2 | `TITLE` | no file |
| a title holding U+001B | 2 | `TITLE` | no file |
| a title holding U+001F | 2 | `TITLE` | no file |
| notes holding U+007F (DEL) | 2 | `--notes` | no file |
| an assignee holding U+001B | 2 | `--assignee` | no file |
| notes holding U+0007 | 2 | `--notes` | no file |
| a title holding a lone surrogate, U+D800 | 2 | `TITLE` | no file |
| an assignee holding U+D800 | 2 | `--assignee` | no file |
| notes holding U+D800 | 2 | `--notes` | no file |
| `TASKS_DB` naming a task list at schema version 3 | 1 | the file | the file unchanged |
| `TASKS_DB` naming a directory | 1 | the directory | the directory unchanged |
| `TASKS_DB` naming a file under a file | 1 | the path | the file unchanged |
| a `.env` saved as UTF-16, `TASKS_DB` not in the environment | 1 | the `.env` | no task list |

### Requirement: TASKS-LIST
The tool `list_tasks`, taking no arguments, SHALL return the open tasks in the order they were added -- at most `TASK_RESULTS_LIMIT` (50) -- as the JSON object `{"tasks": [{"id", "title", "assignee", "notes"}, ...], "more": n}`, `n` being how many more open tasks there are -- the rows and `n` seeing one state of the list -- its text as written: a letter outside ASCII as itself, not escaped. Whatever the file holds, each field SHALL reach the model at most its limit long (TASKS-ADD), without a C0 control character or DEL but newline, carriage return and tab, a value that is not text as empty, and text that is not UTF-8 with U+FFFD in place of what cannot be decoded: one read hands it at most 50 tasks of 1,300 characters, each at most doubled by JSON's escapes (measured: 132,713 characters, ids 1 to 50). A task list another process holds locked SHALL end the run with the store's error after waiting `TASK_STORE_TIMEOUT_SECONDS` -- SQLite's own wait, which overshoots it (measured: 1 s given, 1.8 s taken; 5 s, 7.4 s).

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_tools.py::TestListTasks`

#### Scenario: The open tasks, in order
- **GIVEN** the tasks `Renew passport` (assignee `sam`) and `Call the plumber` (notes `after 5pm`), added in that order
- **WHEN** `list_tasks` is called
- **THEN** it returns `{"tasks": [{"id": 1, "title": "Renew passport", "assignee": "sam", "notes": ""}, {"id": 2, "title": "Call the plumber", "assignee": "", "notes": "after 5pm"}], "more": 0}`

#### Scenario: Text as written
- **GIVEN** the task `Čestitka za Ivana ☕`, its notes `line one`, a carriage return and a newline, `line two`, a tab, `end`
- **WHEN** `list_tasks` is called
- **THEN** its result's text contains `Čestitka za Ivana ☕` as it is, and the notes read back exactly as given

#### Scenario: A list written without the limits
- **GIVEN** a version-1 list another program wrote without the schema's limits, holding two tasks:
  - the first titled `Pay`, U+0001 and 300 `t`; its assignee U+001B and 2,000 `a`; its notes U+0007, U+007F and 2,000,000 `n`
  - the second with a blob for its notes
  - a third with a NULL title, an integer assignee and notes that are text but not UTF-8 (the byte FF)
  - a fourth with a blob in every field
- **WHEN** `list_tasks` is called
- **THEN** the first reaches the model titled `Pay` and 197 `t` (200 characters), assigned to 100 `a`, its notes 1,000 `n` -- no control character in any
- **AND** the second's notes are empty; the third's title and assignee are empty and its notes U+FFFD; every field of the fourth is empty

#### Scenario: At the bound
- **GIVEN** 51 open tasks, every field `"` repeated to its limit
- **WHEN** `list_tasks` is called
- **THEN** its result is 132,713 characters long

#### Scenario: One state of the list
- **GIVEN** the open tasks 1 and 2, and another process adding task 3 between the read's rows and its count
- **WHEN** `list_tasks` is called
- **THEN** it returns tasks 1 and 2, and `more` is 0

#### Scenario: Past the limit
| Open tasks | Tasks returned | Their ids | `more` |
|---|---|---|---|
| 51 | 50 | 1 to 50 | 1 |
| 50 | 50 | 1 to 50 | 0 |
| 0 | 0 | -- | 0 |

#### Scenario: A list another process holds locked
- **GIVEN** a task list another connection holds in an exclusive transaction, and the store's wait set to 1 s
- **WHEN** the assistant runs, its model proposing `list_tasks`
- **THEN** the run raises `sqlite3.OperationalError` after at least 1 s and under 3 s, the model called once

#### Scenario: Counter-example -- a closed task is not listed
- **GIVEN** the tasks 1, 2 and 3, task 2 closed in the file
- **WHEN** `list_tasks` is called
- **THEN** it returns tasks 1 and 3, and `more` is 0

### Requirement: TASKS-SEARCH
The tool `search_tasks(query)` SHALL return the open tasks whose title or notes contain the query -- the spaces around it removed, ASCII letters matched regardless of case, every other character as itself, `%`, `_` and `\` included -- in the order they were added, at most `TASK_RESULTS_LIMIT`, in `list_tasks`' shape and bounds, its text as written. A blank query, or one over `TITLE_MAX` characters, SHALL be handed back to the model as an error answering its call, the list not read.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_tools.py::TestSearchTasks`

#### Scenario: What a query matches
- **GIVEN** the open tasks `1 Renew passport`, `2 Call the plumber` (notes `bring the PASSPORT copy`), `3 Pay 100% deposit`, `4 Pay 1000 deposit`, `5 file_tax`, `6 file tax`, `7 copy a\b`, `8 copy ab`, `9 Sale` (notes `save 50% off`), `10 Promo` (notes `save 500 off`), `11 Čestitka`
| Query | Ids returned |
|---|---|
| `passport` | 1, 2 |
| `  PassPort ` | 1, 2 |
| `100%` | 3 |
| `file_tax` | 5 |
| `a\b` | 7 |
| `50% off` | 9 |
| `čestitka` | none -- a letter outside ASCII matches in its own case only |
| `Čestitka` | 11, its title as written |
| 200 characters, matching nothing | none -- accepted, not refused |
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
Opening the task list SHALL create the file -- its directory included -- and its schema at version 2, in one transaction, when the file does not exist or holds no table at version 0; migrate a version-1 list forward to version 2 -- adding the table `task_writes` (TASKS-AUDIT), its tasks unchanged -- in one transaction; use a version-2 list as it is; recover a write that was interrupted first; and refuse any other file -- a newer version, or a file that is not a task list -- naming the file, nothing written. The schema SHALL hold each field to its limit (TASKS-ADD).

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_store.py::TestTaskSchema`

#### Scenario: Which file is opened
| The file | Opening | Afterwards |
|---|---|---|
| does not exist, nor its directory | succeeds | the file exists at schema version 2, with no task and no record |
| exists, 0 bytes | succeeds | schema version 2, with no task |
| a SQLite file at version 0 with no table | succeeds | schema version 2, with no task |
| a version-1 list holding 2 tasks | succeeds | the same 2 tasks, version 2, `task_writes` empty |
| a version-2 list holding 2 tasks | succeeds | the same 2 tasks, version 2, the file's bytes unchanged |
| a version-1 list holding 1 task, a write of 2,000 more interrupted, its journal left beside it | succeeds | 1 task, version 2, the journal gone |

#### Scenario: The schema holds the limits
| Inserted into a version-2 list directly | SQLite |
|---|---|
| a title of 201 characters | refuses it |
| an assignee of 101 characters | refuses it |
| notes of 1,001 characters | refuses it |

#### Scenario: Created in one transaction
| Creating the list | Afterwards |
|---|---|
| fails after its table is made, before its version is set | the file holds no table at version 0 -- blank, as before |
| migrating a version-1 list fails after `task_writes` is made, before its version is set | the list at version 1, its tasks, no `task_writes` -- as before |
| finds the list another opener made after the file was first looked at | that list, as it was, and no error |

#### Scenario: Counter-example -- a file that is not this task list is refused
| The file | Refusal names | The file afterwards |
|---|---|---|
| a SQLite file at schema version 3 | the file, and version `3` | unchanged |
| a SQLite file at version 1 holding another table, no `tasks` | the file | unchanged |
| a SQLite file at version 2 holding `tasks` but no `task_writes` | the file | unchanged |
| a SQLite file at version 0 holding another table | the file | unchanged |
| a text file, not SQLite | the file | unchanged |

#### Scenario: Counter-example -- a busy list is not "not a task list"
- **GIVEN** a version-2 list another connection holds in an exclusive transaction
- **WHEN** the list is opened with a wait of 1 s
- **THEN** opening raises `sqlite3.OperationalError` -- the store's error, not a refusal calling the file "not a task list"

### Requirement: TASKS-WRITE-VALUES
A write to the task list SHALL be built only from valid values: `task_creation(title, assignee, notes)` by TASKS-ADD's rule for each field; `task_closing(task_id)` and `task_reassignment(task_id, assignee)` from a task id that is a whole number from 1 to `TASK_ID_MAX` (2^63 - 1, the largest SQLite stores), not a boolean, and an assignee by TASKS-ADD's rule for one -- empty unassigns. A value refused SHALL raise `TaskRefused`, naming the field: `title`, `assignee`, `notes` or `task_id`.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_task_writes.py::TestTaskWriteValues`

#### Scenario: Writes built
| Built from | The write |
|---|---|
| `task_creation(" Renew passport ", " sam ", "")` | `CreateTask(NewTask("Renew passport", "sam", ""))` |
| `task_closing(7)` | `CloseTask(7)` |
| `task_closing(2**63 - 1)` -- `TASK_ID_MAX` | `CloseTask(2**63 - 1)` |
| `task_reassignment(7, " ana ")` | `ReassignTask(7, "ana")` |
| `task_reassignment(7, "")` | `ReassignTask(7, "")` -- unassigned |

#### Scenario: Counter-example -- values refused
| Built from | Refused, naming |
|---|---|
| `task_creation("   ", "", "")` | `title` |
| `task_closing(0)` | `task_id` |
| `task_closing(-1)` | `task_id` |
| `task_closing(True)` | `task_id` |
| `task_closing("7")` | `task_id` |
| `task_closing(2**63)` | `task_id` |
| `task_reassignment(0, "ana")` | `task_id` |
| `task_reassignment(7, "a" * 101)` | `assignee` |
| `task_reassignment(7, "x\x1b")` | `assignee` |

### Requirement: TASKS-WRITES
The task list's writer SHALL apply a write in one transaction and return its outcome: a creation SHALL add an open task -- `applied`, with the new task's id; a closing SHALL set an open task closed, and a reassignment an open task's assignee -- `applied`, with the task's id. A closing or reassignment of a task that does not exist, or is closed, SHALL change nothing -- `refused`, with the reason `no task 7` or `task 7 is closed`. A writer SHALL write only to a list at schema version 2, as `open()` makes or migrates it: on a missing file it SHALL raise `sqlite3.OperationalError`, and on any other file -- a list at version 1 or 3 -- `ValueError` naming the file, creating and changing nothing.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_writes.py::TestTaskWrites`

#### Scenario: Each write applied
- **GIVEN** a list holding task 1, `Renew passport`, open and assigned to `sam`

| Applied | Outcome | The list afterwards |
|---|---|---|
| `task_creation("Call the plumber", "", "after 5pm")` | `applied`, task 2 | task 2 open, `Call the plumber`, unassigned, notes `after 5pm` |
| `task_closing(1)` | `applied`, task 1 | task 1 closed: `list_tasks` no longer returns it |
| `task_reassignment(1, "ana")` | `applied`, task 1 | task 1 open, assigned to `ana` |
| `task_reassignment(1, "")` | `applied`, task 1 | task 1 open, unassigned |

#### Scenario: Counter-example -- refused, nothing changed
| Applied | Outcome | The list afterwards |
|---|---|---|
| `task_closing(7)`, no task 7 | `refused`, `no task 7` | unchanged |
| `task_reassignment(7, "ana")`, no task 7 | `refused`, `no task 7` | unchanged |
| `task_closing(1)`, task 1 already closed | `refused`, `task 1 is closed` | unchanged |
| `task_reassignment(1, "ana")`, task 1 closed | `refused`, `task 1 is closed` | unchanged |

#### Scenario: Counter-example -- a writer on a list not opened
| The file | Applying `task_closing(1)` | Afterwards |
|---|---|---|
| missing | raises `sqlite3.OperationalError` | no file |
| a version-1 list holding task 1, never opened by this version | raises `ValueError`, naming the file | version 1, task 1 open |
| a version-2 list holding task 1, its version then set to 3 | raises `ValueError`, naming the file | unchanged |

### Requirement: TASKS-WRITE-ONCE
A write SHALL be applied at most once under its key: applying it, or rejecting it, under a key the task list already records SHALL change nothing and return the outcome recorded for that key. A key already recording a different write SHALL be refused with `ValueError`, nothing written. A key SHALL be 1 to `WRITE_KEY_MAX` (300) characters.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_writes.py::TestWriteOnce`

#### Scenario: The same key again
| First, under the key `t1:4:call_1` | Then, under the same key | The second returns | The list |
|---|---|---|---|
| `task_creation("Renew passport", "", "")` applied | the same, applied | `applied`, task 1 -- recorded | one task |
| `task_closing(1)` applied | the same, applied | `applied`, task 1 | task 1 closed once |
| `task_closing(7)` applied, no task 7 | task 7 created by the owner meanwhile; the same closing applied | `refused`, `no task 7` -- recorded | task 7 still open |
| `task_creation("Renew passport", "", "")` rejected | the same, applied | `rejected` -- recorded | no task |
| `task_closing(1)` applied | the same, rejected | `applied`, task 1 -- recorded | task 1 closed |
| `task_closing(1)` rejected | the same, rejected | `rejected`, task 1 -- recorded | task 1 open |

#### Scenario: Counter-example -- a key reused for another write, or out of bounds
| Under the key | Applied | Raises | The list and its record |
|---|---|---|---|
| `t1:4:call_1`, which records `task_closing(1)` | `task_closing(2)` | `ValueError` | unchanged |
| `t1:4:call_1`, which records `task_closing(1)` | `task_closing(2)`, rejected | `ValueError` | unchanged |
| the empty text | `task_closing(1)` | `ValueError` | unchanged |
| 301 characters | `task_closing(1)` | `ValueError` | unchanged |
| 300 characters | `task_closing(1)` | -- | task 1 closed |

### Requirement: TASKS-AUDIT
Every decision on a write SHALL be recorded in the table `task_writes`, in the same transaction as its effect: its key, its action -- `create`, `close` or `reassign` -- its arguments as JSON, the decision -- `approve` when applied, `reject` when rejected -- the outcome -- `applied`, `refused` or `rejected` -- the task's id when there is one, the reason, and when it was recorded. A write whose transaction fails SHALL leave neither its effect nor its record. The owner's own `starter tasks add` SHALL NOT be recorded: the record is of decisions on proposed writes.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_task_writes.py::TestAudit`

#### Scenario: One row per decision
- **GIVEN** a list holding task 1, open
- **WHEN** `task_creation("Call the plumber", "sam", "")` is applied under `k1`, `task_closing(7)` under `k2`, and `task_reassignment(1, "ana")` rejected under `k3`
- **THEN** `task_writes` holds, in order:

| Key | Action | Arguments, a JSON object equal to | Decision | Outcome | Task | Reason |
|---|---|---|---|---|---|---|
| `k1` | `create` | `{"title": "Call the plumber", "assignee": "sam", "notes": ""}` | `approve` | `applied` | 2 | empty |
| `k2` | `close` | `{"task_id": 7}` | `approve` | `refused` | 7 | `no task 7` |
| `k3` | `reassign` | `{"task_id": 1, "assignee": "ana"}` | `reject` | `rejected` | 1 | empty |

- **AND** each row's time of recording is set, and task 1 is still assigned as it was

#### Scenario: Counter-example -- a write that fails leaves nothing
- **GIVEN** a list holding no task, and a failure raised after the creation's task is inserted, before its record is
- **WHEN** `task_creation("Renew passport", "", "")` is applied under `k1`
- **THEN** the failure propagates, the list holds no task, and `task_writes` no row
- **AND** so it is when the disk fills while the record is written: the disk's own error, `database or disk is full`, propagates

#### Scenario: Counter-example -- the owner's own add is not recorded
- **WHEN** the owner adds `Renew passport` with `starter tasks add`
- **THEN** the list holds task 1, and `task_writes` no row

# Verify

- **Verdict:** DO NOT SHIP -- pass 3 (one MAJOR). First fix: prove the
  control-character rule in every field, at the write and at the read (finding
  34). Pass 2: DO NOT SHIP (three MAJOR). Pass 1: DO NOT SHIP (eight MAJOR).
- **Reviewed at:** pass 3: `98d4714`, the fix diff `de61389..98d4714`. Pass
  2: `976d7c2`, the fix diff `0962b1d..976d7c2`. Pass
  1: `0a8b80f`, the whole change (`git diff
  main..0a8b80f`), committed before the lenses read it.
- **Evidence (pass 1):**
  - `bash scripts/check.sh live` on the reviewed tree: every default check
    passed -- architecture 52, OpenSpec 5 passed, `sdd check` OK, suite 205.
  - Live: 8 passed and 1 failed. MODEL-OPENWEBUI-LIVE failed on the owner's
    model id (`400 Model not found`), as on main.
  - Twenty mutations red (tasks.md 7.3).
  - Five fresh-context lenses over the diff:
    - proof (`spec-compliance`, 11 mutations, 7 survived);
    - defects (`code-reviewer`);
    - placement (`architecture-guardian`);
    - capabilities (`agent-capability-auditor`);
    - graph (`graph-architecture-guardian`).

    All experiments ran on scratch copies. No `.env` was read, and no live
    test was run by a lens.
- **Found by a lens, cleaned up:** the default suite had created
  `.data/tasks.sqlite3` in the repository (finding 1). A mutation had created
  `.data/tasks.db`. Both were empty -- version 1, no task -- and were removed.

## Findings

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | placement, defects, proof | The default suite opens -- and creates -- the repository's own task list. `registered_assistant(Settings("", "", ""))` leaves `tasks_db` empty, the default path. A version-2 file planted there turned the suite red: the result depends on whose machine runs it | `test_registered_assistant.py:88`; `settings.py` (`tasks_db = ""`) | `Settings.tasks_db` without a default, so every construction names its file; the test uses a temporary one |
| 2 | MAJOR | defects | A write killed mid-commit leaves a hot journal. Every read, the schema check included, uses a `mode=ro` connection, which cannot roll it back. Every later open is refused with "is not a task list", which invites deleting a list of tasks. Reproduced | `stores/tasks.py:92,107` | Inspect and read through read-write connections set `query_only`, which SQLite recovers. Only `SQLITE_NOTADB` is "not a task list" |
| 3 | MAJOR | capabilities | "read" is self-declared over an object that can write. Both tools close over the whole `TaskStore`, `add()` and read-write connections included | `registry.py:31`; tools | The tools get a reader: no write method, and connections that refuse a write |
| 4 | MAJOR | capabilities, placement, graph | The check accepts manifests the assistant cannot honour: `calls_per_run` other than the run budget, `retry="transient"`. The requirement names three refusals; it is what is short | `capabilities.py:33-43` | Refuse both, with rows |
| 5 | MAJOR | capabilities, defects | A read is two statements outside one transaction. A lock between them doubles the wait (5 s declared, 7.4 s measured). `tasks` and `more` can disagree. Nothing ties the manifest's timeout to the store's, and no test proves the wait | `stores/tasks.py:77-84` | One read transaction; the reader's timeout taken from the manifest; a locked-list scenario |
| 6 | MAJOR | capabilities, defects | Nothing bounds what a tool sends to the model: one task with 2 MB of notes was returned whole. Non-ASCII text is escaped (`Č`), costing tokens and handing the model escapes | tools; `domain/tasks.py` | Field lengths bounded at write and in the schema; `ensure_ascii=False`; rows |
| 7 | MAJOR | proof | TASKS-ADD's "nothing written" accepts a newly created list. Opening the store before checking the title stays green | `test_tasks_cli.py:62` | `assert not tasks_db.exists()` |
| 8 | MAJOR | proof | TASKS-ADD claims the assignee's and the notes' spaces removed; nothing pads them. Not stripping stays green | `test_tasks_cli.py`; spec | Padded values in the scenario and the test |
| 9 | MINOR | defects | Creating the schema is two commits (`executescript` commits on its own), and two openers can race. A failure between them leaves a file refused forever | `stores/tasks.py:48-51` | `BEGIN IMMEDIATE`, the version re-read, then create, in one transaction |
| 10 | MINOR | defects, proof | `starter tasks add` prints a traceback for a directory as `TASKS_DB`, a parent that is a file, a lock, a full disk. A `.env` that is not UTF-8 exits 1 as if the list could not be opened -- claimed by nothing | `cli/main.py:26-33` | Catch `sqlite3.Error` and `OSError` and name the file; claim the settings failure |
| 11 | MINOR | capabilities | A query of 30,000 `%` raises `LIKE or GLOB pattern too complex` and ends the run, where a schema error would go back to the model | `search_tasks.py:19` | A `max_length` on the query |
| 12 | MINOR | proof | TOOLS-MANIFEST: only `write` is tried, so `== "write"` stays green. The `errors` field and `list_tasks`' "no arguments" are never asserted | `test_tool_manifests.py` | Rows: another side effect; the fields |
| 13 | MINOR | proof | The `starter` script itself is untested: `run()` always exiting 0 stays green | `cli/main.py:run` | One test through `run()` |
| 14 | MINOR | proof | TASKS-SEARCH's "every other character as itself": a backslash is untested, so not escaping it stays green | `stores/tasks.py:_escape_like` | A backslash row |
| 15 | MINOR | proof, graph | ASSISTANT-TOOL-CALL-BUDGET's test catches `Exception` and "run limit", which the model-call budget's error also says | `test_assistant.py:389-393` | `ToolCallLimitExceededError`, and the limit `20` named |
| 16 | MINOR | graph | A real store error (`sqlite3.Error`, the manifests' declared error) is never driven through the graph | `test_assistant.py` | A locked list, through the tool loop (with 5) |
| 17 | MINOR | proof, graph | ASSISTANT-MODEL-CALL-BUDGET's scenario title says "below 41"; its body, 50 and 51. OpenSpec keeps a title, so it stays | spec | A line saying 41 is a bound and 51 the measured value |
| 18 | MINOR | placement | `"TITLE is blank"` is the CLI's metavar, in the domain. `TASK_READ_TIMEOUT_SECONDS` is also the owner's write's wait, in the agents' budgets | `domain/tasks.py:24`; `budgets.py` | The domain names the title; the CLI names `TITLE`. The timeout moves to `domain/tasks.py` as the store's |
| 19 | MINOR | placement | "The only module that opens the file" is enforced by nothing: `sqlite3.connect` in a tool, or I/O in the domain, stays green | ADR 0006; `contract.py` | An AST check refusing `sqlite3.connect` outside `infrastructure/stores/`, proved on a fixture |
| 20 | MINOR | placement | Stale or partial docs. The overview still says the graph checks skip until a graph exists, and has no row for `stores/`. `graphs.md` asks for the check "immediately before execution"; this one runs at compile time, and the design does not say so | `overview.md`; `design.md` | Reword; record the compile-time check, sound for a fixed set of reads, before slice 4 |

Summarised, not counted:
- The schema decision sits in the adapter (placement). It would be a pure
  function of `(version, tables)`.
- No read is audited (capabilities): the deferral to the first write is not
  in a requirement.
- The tool descriptions the model reads are claimed by nothing. "Ignoring
  case" covers ASCII only.
- A version-0 SQLite file with no tables, but not 0 bytes, gets the schema.
- `TASKS_DB` shows in `Settings`' text.
- `~` is not expanded.
- The suite's temporary directory is never removed.
- No tier streams a tool call on the served path (graph).

**Pass 1 verdict:** DO NOT SHIP -- eight MAJOR. Fixed in a separate commit
with the MINORs; that diff is read in pass 2.

## Not checked -- pass 1

- MODEL-OPENWEBUI-LIVE: the owner's model id is not one their Open WebUI
  lists.
- The POSIX-only clauses of the live server tests: CI's `live` job.

## Pass 2 -- the fix diff `0962b1d..976d7c2`

- **Evidence:** `bash scripts/check.sh live` at `976d7c2`:
  - Every default check passed; suite 225.
  - Live: 8 passed and 1 failed, on the owner's model id. That run found
    8.7, fixed before the commit. No key-shaped line.
  - Nineteen pass-1 mutations red (tasks.md 8.6).
- **Lenses:** fresh context, over the fix diff:
  - proof (`spec-compliance`): 19 mutations, 4 red and 15 survived;
  - defects (`code-reviewer`);
  - capabilities (`agent-capability-auditor`).

  The placement and graph lenses were not run: their pass-1 findings were
  MINOR, and the diff answers them. Scratch copies only, no `.env` read, no
  live test run, and no `.data/` left behind.
- **Pass 1 resolved:**
  - 1, 2, 4, 7, 8, 13-18 and 20 fixed and proved.
  - 3, 5, 6, 9-12 and 19 fixed in code, but their proof is incomplete
    (below).

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 21 | MAJOR | capabilities | The length bound rests on a schema `open()` never checks. A version-1 list without the CHECKs -- one `0a8b80f` wrote -- returned 2,000,078 characters. `ignore_check_constraints` in another writer gets past them too | `stores/tasks.py:21,172` | Bound each field at the read (`substr`), whatever the file holds |
| 22 | MAJOR | capabilities | The bound counts stored characters, not what reaches the model. A control character is accepted, then sent as `\u0001`: 6 characters. Worst case per read is 392,713; per run, 7.85M. No context budget exists | `domain/tasks.py:40`; tools | Refuse control characters but newline and tab before a write, and remove them at the read. State the per-read bound, and defer a token budget to 3b in the frame |
| 23 | MAJOR | proof | TASKS-ADD's unreadable-`.env` row is not sealed. It removes `TASKS_DB` but leaves the default path alone, and "no task list" is not asserted. Opening the default list after the settings error stayed green and created `.data/tasks.sqlite3` | `test_tasks_cli.py:164-180` | The default redirected to a temporary path, asserted absent |
| 24 | MINOR | capabilities, defects | The reader's guard is a convention. `PRAGMA query_only = OFF` on its connection, then an INSERT, succeeded. `ATTACH` created a file | `stores/tasks.py:109,157` | An authorizer allowing reads, selects, transactions and pragma reads only; rows for both |
| 25 | MINOR | proof, defects | The architecture check misses `c = sqlite3.connect`, `sqlite3.Connection(...)` and `sqlite3.dbapi2.connect` | `contract.py:209` | Any reference to `connect` or `Connection` on `sqlite3` or `dbapi2`; fixture rows |
| 26 | MINOR | proof, defects | One read, one transaction, is unproved: without BEGIN and COMMIT, the suite stays green | `stores/tasks.py:_page` | A writer between the rows and the count; claimed in TASKS-LIST |
| 27 | MINOR | proof | TASKS-SCHEMA: only the title's CHECK is tried. "In one transaction" and the re-check inside it are unproved | `test_task_store.py` | Rows for the assignee and the notes; a failure after the CREATE leaves the file blank; a second creation leaves the list as it is |
| 28 | MINOR | proof | TASKS-LIST's locked list: "the model called once" is not asserted. The upper bound of 4 s lets one retry through | `test_task_tools.py:104` | Assert the calls; bound under 3 s |
| 29 | MINOR | proof | TASKS-SEARCH gaps: notes matched without ESCAPE, a query exactly at the limit, and text as written are all untested | `test_task_tools.py` | Rows for each; "text as written" claimed |
| 30 | MINOR | proof | TOOLS-MANIFEST: one row each for "other than `none`" and "other than the budget"; "only a view" unproved, since a tool closing over the store too stays green | `test_tool_manifests.py` | Rows for a rate limit of 21 and another retry class; no `TaskStore` in the closure |
| 31 | MINOR | proof | Unclaimed: only `SQLITE_NOTADB` is "not a task list", and a busy file at open propagates. TASKS-ADD's `OSError` branch is unproved | `stores/tasks.py:76`; `cli/main.py:41` | A TASKS-SCHEMA row for a locked file at open; a TASKS-ADD row for a parent that is a file |
| 32 | MINOR | capabilities | The declared timeout still overshoots (7.43 s for 5 s): SQLite's busy wait | `domain/tasks.py:20` | Stated in TASKS-LIST already; accepted |
| 33 | MINOR | defects | A task list on a network share (UNC) is created once, then refused: SQLite rejects the URI's authority | `stores/tasks.py:155` | Accepted, recorded: a share is not a supported place for the list |

**Pass 2 verdict:** DO NOT SHIP -- 21, 22 and 23 are MAJOR. They are fixed
in a separate commit with the MINORs, and that diff is read in pass 3.

## Not checked -- pass 2

- MODEL-OPENWEBUI-LIVE: the owner's model id.
- The placement and graph lenses (above).
- A list on a network share, which needs a share (33).

## Pass 3 -- the fix diff `de61389..98d4714`

- **Evidence:** `bash scripts/check.sh live` at `98d4714`:
  - Every default check passed; suite 241.
  - Live: 8 passed and 1 failed, on the owner's model id. No key-shaped
    line, and no `.data/` left behind.
  - Twenty-two pass-2 mutations red (tasks.md 9.6).
- **Lenses:** fresh context, over the fix diff:
  - proof (`spec-compliance`): 17 mutations, 8 red and 9 survived;
  - defects (`code-reviewer`), who probed the authorizer on SQLite 3.50.4;
  - capabilities (`agent-capability-auditor`).

  Scratch copies only, no `.env` read, no live test run.
- **Pass 2 resolved:**
  - 21-31 fixed. 21 and 22 are only partly proved (34 below).
  - 32 and 33 accepted. The authorizer denies every write the lenses tried:
    a pragma with a value, `ATTACH`, `VACUUM INTO`, a temp table,
    `SAVEPOINT`, `load_extension`.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 34 | MAJOR | proof | The control-character rule is proved for one character in one field. Checking the title only on a write stays green; so does `readable` missing from the assignee and notes, or stripping U+0001 alone | `domain/tasks.py:57`; `stores/tasks.py:145` | Rows: `--assignee` and `--notes` with a control character, U+001B in a title; control characters in every field of a list written without the limits |
| 35 | MINOR | proof | The assignee's bound at the read is unproved; the title's is asserted `<=` only | `test_task_tools.py:128` | An assignee of 2,000 characters, read as 100; exact lengths |
| 36 | MINOR | proof, defects | Newline and tab are allowed but untested, so refusing them stays green. CR is refused, so text with Windows line endings cannot be added -- yet JSON sends `\r` in 2 characters, like `\n` | `domain/tasks.py:42` | CR allowed too; a row adding notes with all three, read back unchanged |
| 37 | MINOR | proof, capabilities | "Control character" in the spec; C0 and DEL in the code. U+0085 passes | `domain/tasks.py:42` | The spec names C0 and DEL: JSON does not escape C1, so the bound's reason holds |
| 38 | MINOR | proof, capabilities, defects | The stated bound names JSON's escapes of newline and tab only. `"` and `\` double too; 133,323 characters were measured per read | spec TASKS-LIST; frame question 6 | "at most doubled by JSON's escapes"; the measured figure |
| 39 | MINOR | capabilities, defects | A value that is not text -- a blob another program put in -- crashes the read with `TypeError`, an error no manifest declares | `stores/tasks.py:136-148` | Read anything but text as empty, in SQL; a row |
| 40 | MINOR | defects | A lone surrogate in the arguments passes `new_task`, creates the file, then exits 1 | `domain/tasks.py:46` | Refuse a field UTF-8 cannot encode, naming it; a row |
| 41 | MINOR | proof, defects | The database check misses `_sqlite3` and `from sqlite3 import *`, and flags a type annotation of `sqlite3.Connection` | `contract.py:209-247` | `_sqlite3` and the star import caught; `Connection` flagged where called; fixture rows, the annotation a counter-example |
| 42 | MINOR | proof | "No store" is checked one level deep: a reader holding the store stays green | `test_tool_manifests.py:103` | The reader's own attributes checked too |
| 43 | MINOR | capabilities | The OPEN per-run budget has no Owner or Review by, no figure, and no line in the roadmap | frame question 6; roadmap | All three |
| 44 | MINOR | capabilities, proof | Search scans the whole of an oversized field but returns it cut. The SQL `substr` is unproved: `readable` cuts too | `stores/tasks.py:124,135` | Accepted, recorded: both concern only lists written without the limits; the `substr` is a memory guard |

**Pass 3 verdict:** DO NOT SHIP -- 34 is MAJOR. It is fixed in a separate
commit with the MINORs, and that diff is read in pass 4.

## Not checked -- pass 3

- MODEL-OPENWEBUI-LIVE: the owner's model id.
- The placement and graph lenses: their pass-1 findings were MINOR, and are
  answered.

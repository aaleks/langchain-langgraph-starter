# Sequence

- **Order:**
  1. The setting, since nothing can find the file without it.
  2. The schema, since nothing can read a file that is not opened.
  3. The owner's `add`, so a list has rows.
  4. The two read tools.
  5. The manifest check and the tool-call budget in the factory.
  6. The registry wiring that joins them.
- **Wiring point:** `src/starter/infrastructure/agents/registry.py` -- the
  store opened from the settings, its two tools handed to the factory.
- **Story test:**
  `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`
  -- ASSISTANT-REGISTERED, modified. Its scenario "A task the owner added,
  read through the registered graph" stays red until the registry hands the
  tools over.

## 0. Foundation

- [x] 0.1 The suite sealed from the owner's task list: `TASKS_DB` set to a
  temporary file in `tests/conftest.py`; `.data/` in `.gitignore`;
  `.env.example` documents `TASKS_DB`
- [x] 0.2 The Open WebUI stand-in takes scripted replies, a tool call among
  them (`tool_call(...)`); the suite still green, 165
- [x] 0.3 The story test, red: `No module named 'starter.cli.main'`

## 1. SETTINGS-TASKS-DB and SETTINGS-ENVIRONMENT-WINS (modified)

- [x] 1.1 /accept -- red: `cannot import name 'tasks_db_path'`; the
  every-setting rows spelled out, so `TASKS_DB` missing from `NAMES` turns them
  red
- [x] 1.2 /tdd -- `TASKS_DB` in `NAMES`, `Settings.tasks_db`, `tasks_db_path`;
  27 passed

## 2. TASKS-SCHEMA

- [x] 2.1 /accept -- red: `No module named 'starter.infrastructure.stores'`
- [x] 2.2 /tdd -- `TaskStore.open()`, inspecting through a read-only
  connection before writing; 6 passed

## 3. TASKS-ADD

- [x] 3.1 /accept -- red: `No module named 'starter.cli.main'`
- [x] 3.2 /tdd -- `domain.tasks.new_task`, `TaskStore.add`, `cli/main.py`;
  `[project.scripts] starter`, `uv sync`; run for real, it printed `1` and
  refused a blank title with exit status 2; 4 passed

## 4. TASKS-LIST and TASKS-SEARCH

- [x] 4.1 /accept -- red: `No module named 'starter.infrastructure.agents.tools'`
- [x] 4.2 /tdd -- `open_tasks`, `search` with `LIKE ... ESCAPE`, the two tool
  modules; 14 passed

## 5. TOOLS-MANIFEST

- [x] 5.1 /accept -- red: `No module named 'starter.domain.agents.capabilities'`
- [x] 5.2 /tdd -- `Capability`, `check_capability`, the factory checking every
  tool; the existing tests' tools given a manifest (`tests.fakes.manifested`)

## 6. ASSISTANT-TOOL-CALL-BUDGET, and ASSISTANT-MODEL-CALL-BUDGET (modified)

- [x] 6.1 /accept -- red: the over-budget turn's calls ran
- [x] 6.2 /tdd -- `ToolCallLimitMiddleware(run_limit=20, exit_behavior="error")`.
  The step ceiling the model-call budget needs, re-measured: 50 ends at the
  ceiling, 51 in the budget's error -- one more superstep per turn. That made
  ASSISTANT-MODEL-CALL-BUDGET's "41" false, so it is MODIFIED (its scenario's
  title kept, which OpenSpec requires, and still true)

## 7. ASSISTANT-REGISTERED (modified) -- the story test green

- [x] 7.1 /tdd -- the registry opens the store and hands both tools over. That
  surfaced the offline model's `bind_tools`, which raised `NotImplementedError`
  now that the graph has tools; `OfflineChatModel` accepts them and proposes
  nothing. The story test green; a task list at version 2 refused at load
- [x] 7.2 Each live server gets its own task list in its work directory;
  `bash scripts/check.sh live`: every default check passed, suite 205; live 8
  passed and 1 failed -- MODEL-OPENWEBUI-LIVE, the owner's model id (`400 Model
  not found`), unchanged from connect-openwebui-model
- [x] 7.3 Proved by mutation, twenty in a full-suite run, each red: `TASKS_DB`
  from the working directory, another default, `TASKS_DB` not read, a newer
  version accepted, a version-1 list re-created, the title not stripped, a
  blank title exiting 1, `LIKE` unescaped, notes not searched, closed tasks
  listed, one row past the limit, `more` never counted, the query not
  stripped, a write accepted, another tool's manifest accepted, no manifest
  accepted, the budget ending instead of raising, a budget of 21, the
  registry giving no tools, the registry not opening the list

## 8. Verify pass 1 -- the fixes (`verify.md`, reviewed at `0a8b80f`)

- [x] 8.1 The suite sealed in code: `Settings.tasks_db` without a default;
  the offline registered test names its own list, and asserts that list is
  the one opened (1)
- [x] 8.2 The store: a tool given a `TaskReader` -- no write method,
  `query_only` connections that SQLite can still recover through; only
  `SQLITE_NOTADB` is "not a task list"; an interrupted write recovered,
  reproduced by a copy taken mid-write (2, 3); one read, one transaction, its
  wait the manifest's, a locked list proved through the tool loop (5, 16);
  creation in one `BEGIN IMMEDIATE` transaction (9)
- [x] 8.3 TOOLS-MANIFEST amended: not a manifest, another side effect, a
  retry class, a rate limit other than the run's refused; the fields asserted
  (4, 12)
- [x] 8.4 What reaches the model bounded: field limits 200/100/1,000 refused
  before a write and held by the schema; text as written; a query at most 200
  characters (6, 11)
- [x] 8.5 TASKS-ADD amended and proved: "no file" after a refusal, padded
  assignee and notes, the `starter` script's exit status, a directory and an
  unreadable `.env` exit 1 without a traceback (7, 8, 10, 13); a backslash row
  (14); the tool budget's own error (15); the 41/51 line (17); the store's
  timeout in `domain/tasks.py`, the domain naming the field and the CLI
  `TITLE` (18); `sqlite3.connect` outside `stores/` refused, on a fixture (19);
  the overview, ADR 0006 and the design (20)
- [x] 8.6 Proved by mutation, nineteen in a full-suite run, each red -- the
  survivors of the proof lens among them: the store opened before the title
  check, the assignee not stripped, another side effect, `run()` exiting 0, a
  backslash unescaped
- [x] 8.7 Found by the live run after 8.1: the live Open WebUI test read the
  owner's `.env` alone, so it created the default task list in the
  repository. It now runs with the owner's model and a temporary task list,
  and no `.data/` is left. Every default check passed, suite 225; live 8
  passed, 1 failed on the owner's model id, as before

## 9. Verify pass 2 -- the fixes (`verify.md`, reviewed at `976d7c2`)

- [x] 9.1 Bounded at the read, whatever the file holds: each field cut in SQL
  and made `readable` by the domain -- no control character but newline and
  tab, at most its limit; control characters refused before a write; a list
  written without the limits proved (21, 22). A run's budget on what reaches
  the model: OPEN for 3b, frame question 6
- [x] 9.2 The CLI's unreadable-`.env` row sealed: the default list redirected
  and asserted absent (23); a file under a file exits 1 (31)
- [x] 9.3 The reader's authorizer: an INSERT, `PRAGMA query_only = OFF` and an
  `ATTACH` refused, the tool holding no store (24, 30)
- [x] 9.4 The database check: any reference to `connect` or `Connection` of
  `sqlite3` or `dbapi2`, on fixture rows (25)
- [x] 9.5 Rows: one state of the list, with a writer between the rows and the
  count (26); the assignee's and notes' CHECKs, a creation failing midway, a
  list another opener made, a busy list not "not a task list" (27, 31); the
  locked list's one model call and its bound under 3 s (28); notes matched
  with ESCAPE, a query at the limit, text as written in a search (29); retry
  `always`, a rate limit of 21 (30)
- [x] 9.6 Proved by mutation, twenty-two in a full-suite run, each red --
  every survivor of the proof lens among them (M1-M5, M7-M16). Accepted and
  recorded: the timeout's overshoot (32); a list on a network share (33)

## 10. Verify pass 3 -- the fixes (`verify.md`, reviewed at `98d4714`)

- [x] 10.1 The control-character rule in every field (34): U+001B in a title,
  the assignee and notes refused at the write; control characters in every
  field of a list written without the limits stripped at the read, the
  assignee cut to 100 exactly (35)
- [x] 10.2 "Control character" is C0 and DEL in the spec too; CR allowed;
  notes over several lines added and read back unchanged (36, 37)
- [x] 10.3 The stated bound: each task at most doubled by JSON's escapes,
  133,323 characters measured (38); frame question 6 given an owner, a review
  date and the run's figure, and a line in the roadmap's slice 3 (43)
- [x] 10.4 A value that is not text reads as empty, in SQL; the read cuts at
  four times the limit, `readable` makes the final cut (39); a field UTF-8
  cannot encode refused before the file is touched (40)
- [x] 10.5 The database check: `_sqlite3`, a star import, the DB-API
  module's `connect` by name; `Connection` flagged where called, a type that
  names one a counter-example (41); the reader holds no store (42)
- [x] 10.6 Proved by mutation, sixteen in a full-suite run: fifteen red. The
  survivor, `readable`'s own guard on a value that is not text, was dead code
  behind the SQL's; it is removed, and the SQL's guard alone turns the suite
  red. Accepted: search over an oversized field; the SQL cut a memory guard
  (44)

## 11. Verify pass 4 -- the MINORs (`verify.md`, reviewed at `f95333f`)

- [x] 11.1 The database check: a `Connection` subclassed or aliased caught
  again; only a type annotation or `isinstance`'s and `issubclass`'s class
  argument spared (45)
- [x] 11.2 Text that is not UTF-8 reads with U+FFFD (46); `_cut`'s docstring
  honest (47); a NULL, an integer and a blob in every field read as empty (50)
- [x] 11.3 Rows: U+001F, DEL, U+D800 in the assignee and the notes refused;
  U+0085 stored as given (48, 49); the bound measured and asserted, 132,713
  characters (51); no method bound to a store on the reader (52). A NUL never
  reaches the domain -- SQLite stops at it, a command line cannot carry it --
  recorded in the design
- [x] 11.4 Proved by mutation, ten in a full-suite run, each red

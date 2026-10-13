# Verify

- **Verdict:** DO NOT SHIP -- pass 1 (eight MAJOR). First fix: seal the
  default suite from the repository's own task list (finding 1).
- **Reviewed at:** pass 1: `0a8b80f`, the whole change (`git diff
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

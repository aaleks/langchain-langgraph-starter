# Design

Why: `frame.md`. Scope: `intake.md`. The store's decisions:
`docs/decisions/0006-the-task-store.md`.

## Context

The registered `assistant` has no tools (ADR 0005). Its factory takes any
`BaseTool` and checks nothing about it. Settings hold the three Open WebUI
names. No CLI entry point exists. The suite seals the owner's `.env` by
setting those names empty in its environment.

## Decisions

| File | Holds | Layer rule |
|---|---|---|
| `src/starter/domain/tasks.py` | `TASK_RESULTS_LIMIT = 50`; `new_task(title, assignee, notes)` -- the spaces around each removed, a blank title refused naming `TITLE`; the output types `TaskRow`, `TaskPage` (TypedDicts) | domain: pure |
| `src/starter/domain/agents/capabilities.py` | `Capability`, a frozen dataclass: `name`, `output` (a type), `errors`, `idempotent`, `timeout_seconds`, `retry` (`"none"` or `"transient"`), `calls_per_run`, `side_effect` (`"read"` or `"write"`), `audit_event` (`None` for reads). `check_capability(tool_name, capability)` raises `ValueError` naming the tool | domain: the policy every tool passes |
| `src/starter/domain/agents/budgets.py` | `TOOL_CALLS_PER_RUN = 20` | domain |
| `src/starter/config/settings.py` | `TASKS_DB` in `NAMES`; `Settings.tasks_db` (default `""`, so `Settings(url, key, model)` still reads); `tasks_db_path(settings)` -- the repository's `.data/tasks.sqlite3`, a relative path from the root, an absolute one as it is | config: finding configuration |
| `src/starter/infrastructure/stores/tasks.py` | `TaskStore(path, timeout)`: `open()` -- the version decision of ADR 0006; `add(...)`; `open_tasks(limit)` and `search(query, limit)`, each returning `TaskPage`. `LIKE ... ESCAPE '\'` with `\`, `%` and `_` escaped | infrastructure: the only module that opens the file |
| `src/starter/infrastructure/agents/tools/list_tasks.py`, `search_tasks.py` | `build(store) -> BaseTool`, one tool each, its `Capability` in `tool.metadata["capability"]`; the result is `json.dumps(page)`. `search_tasks`' query is `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]`: a blank query fails the tool's own schema, and `create_agent` hands that back to the model as an error tool message (measured) | agents adapter: tools |
| `src/starter/infrastructure/agents/factory.py` | `check_capability` for every tool before `create_agent`; `ToolCallLimitMiddleware(run_limit=TOOL_CALLS_PER_RUN, exit_behavior="error")` beside the model-call budget | composition |
| `src/starter/infrastructure/agents/registry.py` | settings, then the model, then `TaskStore(tasks_db_path(settings))` opened -- refused at load -- then the two tools | registration |
| `src/starter/cli/main.py` | `main(argv) -> int`: `tasks add` through argparse. `run()` calls `sys.exit(main())`. `[project.scripts] starter = "starter.cli.main:run"` | cli: the only exit |

- **Where a manifest lives.** It sits on the tool, in `metadata`. The factory
  receives the tools it composes, so it can check every one, and no second
  list of tools can drift from the first. The manifest has no field for the
  input schema: a LangChain tool's `args_schema` is its input's type already.
- **What each field is held to.** `side_effect` is held by the factory: a
  `write` is refused until slice 4. `timeout_seconds` is the store's busy
  timeout. `calls_per_run` is `TOOL_CALLS_PER_RUN`, which the middleware
  enforces for every tool together. `retry` is `none`: a store error
  propagates (ASSISTANT-ERRORS-PROPAGATE). `idempotent` and `audit_event`
  are declared now and enforced with the first write.
- **The budget's error.** `exit_behavior="error"` raises
  `ToolCallLimitExceededError` before executing any call of the turn that
  would pass the limit. Measured with `langchain` 1.4: 3 calls a turn, a
  limit of 20, and the run raised with 18 executed.
- **The suite is sealed from the owner's task list.** `tests/conftest.py`
  sets `TASKS_DB` to a file in a temporary directory, beside the empty Open
  WebUI settings. A test that needs its own list sets its own path. The live
  server's environment (`tests/localserver.py`) points `TASKS_DB` into the
  server's work directory.
- **The CLI's output.** On success the id goes to standard output, so a
  script can read it. Every refusal goes to standard error. Exit status 2 is
  a usage error, as argparse uses it. Exit status 1 is a task list that
  cannot be opened.
- **The Open WebUI stand-in learns tool calls.** `tests/openwebui_stub.py`
  takes scripted replies, each either text or a tool call in the
  chat-completions shape. The story test drives a real `ChatOpenAI` through a
  `list_tasks` call, which proves the request and the parsing as well as the
  tool.

- **Verify pass 1's corrections** (`verify.md`):
  - *The suite is sealed in code too.* `Settings.tasks_db` has no default, so
    a settings object built in a test names its own list.
  - *A tool holds a reader, never the store.* `TaskReader` has no write
    method, and its connections are `query_only`. They are read-write so that
    SQLite can recover an interrupted write; a read-only connection cannot,
    and the list would be refused as "not a task list". Only `SQLITE_NOTADB`
    is called that.
  - *One read is one transaction.* The rows and `more` agree, and a lock is
    waited on once. The wait is SQLite's, and it overshoots the timeout it is
    given (measured: 1 s given, 1.8 s taken; 5 s given, 7.4 s taken). The
    requirement states the overshoot rather than hiding it.
  - *The manifest check refuses what nothing enforces:* a retry class other
    than `none`, and a rate limit other than the run's budget. The reader
    takes its wait from the manifest.
  - *The check runs once, at composition.* That is sound for a fixed set of
    reads. A write's check, immediately before it runs (`graphs.md`), arrives
    with slice 4.
  - *What reaches the model is bounded.* Each field has a length limit (200,
    100, 1,000), refused before a write and held by the schema, and a read
    returns at most 50 rows. Text is sent as written, never escaped. A query
    is at most 200 characters, so SQLite never refuses its pattern mid-run.
  - *Creation is one transaction.* `BEGIN IMMEDIATE`, with the file looked at
    again inside it, means two openers cannot both create the list, and a
    failure leaves no half-made one.
  - *The CLI never prints a traceback.* Settings or a list that cannot be
    read or written exit 1, naming the file.
  - *Accepted and recorded:*
    - The schema's version decision stays in the store: its inputs come from
      the file, and it is three lines.
    - Reads are not audited; the transcript records each call. An audit event
      arrives with the first write.
    - No requirement claims the tool descriptions the model reads. "Ignoring
      case" covers ASCII only, as TASKS-SEARCH says.
    - `TASKS_DB` shows in `Settings`' text. It is a path, not a secret.
    - `~` is not expanded.
    - The suite's temporary directory outlives the run.
    - No tier streams a tool call on the served path, because the fake cannot
      stream a proposal. The live server test streams an answer.

- **Verify pass 2's corrections** (`verify.md`):
  - *Bounded at the read, whatever the file holds.* Each field is cut in SQL
    (`substr`) and made `readable` in the domain: no control character but
    newline and tab, at most its limit long. The schema's CHECKs guard writes
    through this code; the read guards everything else, including a list
    another program wrote, or one written before the CHECKs.
  - *Control characters refused before a write,* since JSON would send each
    as six characters.
  - *The reader's guard is an authorizer.* SQL cannot remove it, and it lets
    through reading and reading a pragma only. `query_only` stays as the
    second wall.
  - *A run's budget on what reaches the model* is OPEN for 3b (frame,
    question 6).
  - *The database check sees any reference* to `connect` or `Connection` of
    `sqlite3` or its `dbapi2`, called or not.
  - *Accepted and recorded:*
    - The timeout overshoots: SQLite's busy wait, measured and stated in
      TASKS-LIST.
    - A list on a network share is unsupported: SQLite refuses the URI's
      authority after the first add.

- **Verify pass 3's corrections** (`verify.md`):
  - *The control-character rule in every field*, at the write and at the
    read. "Control character" means C0 and DEL, but newline, carriage return
    and tab: JSON sends those three in two characters, and does not escape C1
    at all. CR is allowed, so Windows text can be added.
  - *The read takes text only*, cutting each field in SQL at four times its
    limit -- never the whole of an oversized one -- and anything but text
    reads as empty. The domain's `readable` drops control characters, then
    makes the final cut, so a field reaches its limit exactly.
  - *A field UTF-8 cannot encode is refused* before the file is touched.
  - *The database check* reaches `_sqlite3` and a star import, and flags a
    `Connection` only where it is called: a type names one and opens
    nothing. A module imported by `importlib` from a string is out of reach,
    and the docstring says so.
  - *Accepted and recorded:* search matches the whole of an oversized field
    but returns it cut; the SQL cut is a memory guard no test can see. Both
    concern only lists written without the limits.

- **Verify pass 4's corrections** (`verify.md`):
  - *A connection subclassed or aliased* is caught again. Only a type
    annotation, or `isinstance`'s or `issubclass`'s class argument, names
    `Connection` without opening anything.
  - *Text that is not UTF-8* reads with U+FFFD rather than making the whole
    list unreadable.
  - *The bound per read is measured and asserted:* 132,713 characters, ids 1
    to 50.
  - *Accepted and recorded:* a NUL never reaches the domain. SQLite's string
    functions stop at the first one, so text after a NUL in a list another
    program wrote is not read, and a command line cannot carry one. Keeping
    NUL in `CONTROL` costs nothing, and no entry point can prove it.

## Orchestration design

N-A for the node table: the tool loop is unchanged, with one more middleware.

- **Budgets.** `MODEL_CALLS_PER_RUN = 10` turns; `TOOL_CALLS_PER_RUN = 20`
  calls per run; `TASK_RESULTS_LIMIT = 50` rows per result. All are starting
  policies, re-measured in slice 3b.
- **Errors.** A blank query goes back to the model. A store failure raises.
  A turn that would pass the tool-call budget raises.

## Risks

- [A middleware node shifts the step ceiling] -> the existing budget test
  pins the supersteps (40 and 41). It is re-measured when the tool-call
  middleware lands, and the test changes with the measurement, not with a
  guess.
- [`LIKE` and non-ASCII case] -> stated in TASKS-SEARCH and ADR 0006.
  Full-text search waits for a requirement.
- [The owner's task list read by a default test] -> the suite's `TASKS_DB`
  points into a temporary directory, and the environment wins.

## Migration and rollback

There is no data before this change. Rollback is a revert. The owner's
`.data/tasks.sqlite3` is left behind, unread.

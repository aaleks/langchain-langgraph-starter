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
| `src/starter/domain/agents/budgets.py` | `TOOL_CALLS_PER_RUN = 20`; `TASK_READ_TIMEOUT_SECONDS = 5` | domain |
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

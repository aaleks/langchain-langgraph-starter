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

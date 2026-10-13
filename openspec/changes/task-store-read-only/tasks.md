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

- [ ] 0.1 The suite sealed from the owner's task list: `TASKS_DB` set to a
  temporary file in `tests/conftest.py`; `.data/` in `.gitignore`;
  `.env.example` documents `TASKS_DB`
- [ ] 0.2 The Open WebUI stand-in takes scripted replies, a tool call among
  them
- [ ] 0.3 The story test, red

## 1. SETTINGS-TASKS-DB and SETTINGS-ENVIRONMENT-WINS (modified)

- [ ] 1.1 /accept -- red
- [ ] 1.2 /tdd

## 2. TASKS-SCHEMA

- [ ] 2.1 /accept -- red
- [ ] 2.2 /tdd

## 3. TASKS-ADD

- [ ] 3.1 /accept -- red
- [ ] 3.2 /tdd -- `[project.scripts]`, `uv sync`

## 4. TASKS-LIST and TASKS-SEARCH

- [ ] 4.1 /accept -- red
- [ ] 4.2 /tdd

## 5. TOOLS-MANIFEST

- [ ] 5.1 /accept -- red
- [ ] 5.2 /tdd -- existing tests' `add` tool given a manifest

## 6. ASSISTANT-TOOL-CALL-BUDGET

- [ ] 6.1 /accept -- red
- [ ] 6.2 /tdd -- the step ceiling re-measured with the new middleware

## 7. ASSISTANT-REGISTERED (modified) -- the story test green

- [ ] 7.1 /tdd -- the registry wires the store and the tools
- [ ] 7.2 The live server tests' environment names a task list; `check.sh live`
- [ ] 7.3 Proved by mutation, each red in a full-suite run

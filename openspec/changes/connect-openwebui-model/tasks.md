# Sequence

- **Order:** settings first (nothing can be configured without them), then the
  choice (pure), then the client it builds, then the retry policy around every
  model call, then the registry wiring that joins them -- and last the live run
  that needs all of it and a running Open WebUI.
- **Wiring point:** `src/starter/infrastructure/agents/registry.py` -- a
  factory function reads the settings, chooses and builds the model, and
  compiles the assistant.
- **Story test:** `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`
  -- ASSISTANT-REGISTERED, modified: its new scenario "the model the settings
  choose" stays red until the registry reads the settings.

## 0. Foundation

- [x] 0.1 `langchain-openai` and `python-dotenv` pinned to the checked minor -- 1.7.0 (core
  stays 1.6.9) and 1.2.4
- [x] 0.2 The suite sealed from the owner's `.env`: the three Open WebUI
  settings set empty in `tests/conftest.py`, so the default suite always
  chooses the offline model; `clean_env` empties rather than removes
- [x] 0.3 `.env.example` documents `OPENWEBUI_URL`, `OPENWEBUI_API_KEY`,
  `OPENWEBUI_MODEL`

## 1. SETTINGS-ENVIRONMENT-WINS

- [x] 1.1 /accept -- red: `No module named 'starter.config.settings'`
- [x] 1.2 /tdd -- 5 passed; mutated (.env winning) -> `environment-wins` FAILED

## 2. MODEL-CHOICE

- [x] 2.1 /accept -- red: `No module named 'starter.domain.models'`
- [x] 2.2 /tdd -- 4 passed; mutated (partial falls back offline) -> the counter-example FAILED

## 3. MODEL-OPENWEBUI-CLIENT

- [x] 3.1 /accept -- red: `No module named 'starter.config.settings'`
- [x] 3.2 /tdd -- 2 passed; mutated (the client's own retries kept) -> FAILED

## 4. ASSISTANT-TRANSIENT-RETRY and ASSISTANT-ERRORS-PROPAGATE (modified)

- [x] 4.1 /accept -- red: `No module named 'starter.domain.agents.retries'`
- [x] 4.2 /tdd -- green, the modified one included; mutated (`on_failure="continue"`) -> the
  past-the-retries scenario FAILED

## 5. ASSISTANT-REGISTERED (modified) -- the wiring

- [x] 5.1 /accept the new scenarios -- red: `No module named 'starter.config.settings'`
- [x] 5.2 /tdd -- 8 passed, against an in-process stub of Open WebUI's `/api/chat/completions`;
  a scenario added so the registry's retry predicate is proved (a 503 retried). Mutated:
  the registry always offline, or retrying nothing, or a 503 not transient -> each FAILED
- [x] 5.3 The "only `infrastructure/models.py` builds a model" check extended to
  every module, proved on a fixture -- `models_built_outside_models`, 50 architecture passed

## 6. MODEL-OPENWEBUI-LIVE

- [x] 6.1 The live test written; skipped, saying so, when `.env` does not configure Open WebUI
- [x] 6.2 Run against the owner's Open WebUI once `.env` is filled -- or recorded as not yet run:
  **not yet run** -- `.env` does not configure Open WebUI yet: `1 skipped`, "does not
  configure Open WebUI -- see .env.example". The owner re-runs `bash scripts/check.sh live`

## 7. Wiring

- [x] 7.1 The story test is green through the registry -- TestAssistantIsRegistered, 8 passed
- [x] 7.2 `bash scripts/check.sh` and `bash scripts/check.sh live` pass -- "all checks passed":
  architecture 50, method 117 OK, suite 89, live 7 passed and 1 skipped (Open WebUI not configured)

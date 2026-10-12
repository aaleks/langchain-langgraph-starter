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

- [ ] 0.1 `langchain-openai` and `python-dotenv` pinned to the checked minor
- [ ] 0.2 The suite sealed from the owner's `.env`: the three Open WebUI
  settings set empty in `tests/conftest.py`, so the default suite always
  chooses the offline model
- [ ] 0.3 `.env.example` documents `OPENWEBUI_URL`, `OPENWEBUI_API_KEY`,
  `OPENWEBUI_MODEL`

## 1. SETTINGS-ENVIRONMENT-WINS

- [ ] 1.1 /accept -- red for the right reason
- [ ] 1.2 /tdd -- every scenario green

## 2. MODEL-CHOICE

- [ ] 2.1 /accept -- red for the right reason
- [ ] 2.2 /tdd -- every scenario green

## 3. MODEL-OPENWEBUI-CLIENT

- [ ] 3.1 /accept -- red for the right reason
- [ ] 3.2 /tdd -- every scenario green

## 4. ASSISTANT-TRANSIENT-RETRY and ASSISTANT-ERRORS-PROPAGATE (modified)

- [ ] 4.1 /accept -- red for the right reason
- [ ] 4.2 /tdd -- every scenario green, the modified one included

## 5. ASSISTANT-REGISTERED (modified) -- the wiring

- [ ] 5.1 /accept the new scenario -- red for the right reason
- [ ] 5.2 /tdd -- every scenario green
- [ ] 5.3 The "only `infrastructure/models.py` builds a model" check extended to
  every module, proved on a fixture

## 6. MODEL-OPENWEBUI-LIVE

- [ ] 6.1 The live test written; skipped, saying so, when `.env` does not configure Open WebUI
- [ ] 6.2 Run against the owner's Open WebUI once `.env` is filled -- or recorded as not yet run

## 7. Wiring

- [ ] 7.1 The story test is green through the registry
- [ ] 7.2 `bash scripts/check.sh` and `bash scripts/check.sh live` pass

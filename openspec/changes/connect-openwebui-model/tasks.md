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

## 8. Verify pass 1 -- the fixes (`verify.md`, reviewed at `4dc2516`)

- [x] 8.1 MODEL-TRANSIENT-FAILURES added at the unit tier, every status; each
  failure kind proved through the client's own exceptions -- a streamed chunk's
  builtin `TimeoutError` now transient, `stream_chunk_timeout` set (1, 6)
- [x] 8.2 The settings counter-example removes the name before reading; the
  registry refuses a partial configuration at start; `.env` read only for a
  missing name, a non-UTF-8 file refused naming it; a URL without
  `http(s)://host` refused (2, 3, 8, 9)
- [x] 8.3 ASSISTANT-MODEL-CALL-BUDGET modified to turns, a retried turn proved to
  spend one unit; LOCAL-SERVER-STAYS-LOCAL modified to except the owner's
  configured Open WebUI (4, 5)
- [x] 8.4 Timeout, not deadline, throughout; the suite sealed from proxies and
  `OPENAI_*`; the offline test re-imports the module; the models check catches
  aliases and `AzureChatOpenAI`, `config/` allowed only `dotenv`; retry timing
  in the domain; SETTINGS-KEY-NEVER-SHOWN added; stale text updated (7, 10-16);
  17 accepted in the design
- [x] 8.5 Proved by mutation, eight probes in a full-suite run, each red: a
  stream timeout not transient, 429 not transient, a failed connection not
  transient, `load_dotenv` in the reader, `build_model` falling back silently,
  the provider imported at module level, the chunk timer left to
  langchain-openai (red once its environment override is set in the test), `.env`
  opened regardless

## 9. Verify pass 2 -- the fixes (`verify.md`, reviewed at `bd4bc4e`)

- [x] 9.1 LOCAL-SERVER-STAYS-LOCAL: a second live server, its Open WebUI a
  stand-in on 127.0.0.1, run under the probe -- one request at
  `/api/chat/completions` with the key, nothing beyond this machine (18)
- [x] 9.2 Spaces read as empty from the environment and from a quoted `.env`
  value (19); the URL refusal names the variable, never the value, and refuses
  a missing host, a bad port and an unparseable URL (20, 21); 409, 501 and 505
  not transient (22)
- [x] 9.3 Frame and design: a timeout per wait, retries per turn; the retry
  timing recorded as passed, not asserted (23, 24); 25 and 26 accepted in the
  design; the models check follows `init_chat_model`'s aliases and leaves a
  partner package's non-model classes alone (27)
- [x] 9.4 Proved by mutation, each red: the configured server looking up a far
  host; `.strip()` dropped (both rows); the port not read; `urlsplit`'s error
  escaping; the refusal quoting the value; 501 made transient; and the models
  check's fixture against the old check (missed alias, flagged `Chroma`)

## 10. Verify pass 3 -- the fixes (`verify.md`, reviewed at `6033d3a`)

- [x] 10.1 MODEL-CHOICE refuses a key and a model without the URL (28); the
  registered export proved to read the process's settings, loaded through
  `langgraph.json` with them in the environment, a partial set refused at load
  (29)
- [x] 10.2 The URL is Open WebUI's address: a query or a fragment refused, a
  URL ending in `/api` taken as the API itself (31); `openai` impossible to import in the offline
  counter-example (32), declared and bounded to 3.29 (33)
- [x] 10.3 The models check by class name and SDK module, chat data excepted
  (30); `config`'s allowlist fixture-proved, `CLAUDE.md` and the overview
  updated (34); `local_server(settings=)` takes the settings' names only (35);
  the retry predicate required (36)
- [x] 10.4 SETTINGS-ENVIRONMENT-WINS: the counter-example reads `os.environ`
  itself (37); every setting trimmed, claimed (38); `.env` values not
  interpolated, claimed (39); MODEL-TRANSIENT-FAILURES over every status
  100-599 (40); the session servers assert the offline answer (41); stale text
  in the frame, design and `CLAUDE.md` (42 -- the living Purpose at archive)
- [x] 10.5 Proved by mutation, nine in a full-suite run, each red: the URL
  deciding offline, the export ignoring the process's settings, a query
  accepted, `/api` added twice or dropped, `openai` imported at module level, the reader writing into
  the environment, only the model trimmed, `.env` interpolated, 507 transient;
  the two architecture fixtures red against the old check and a widened
  allowlist
  -- and five for `/api` taken as the API: added twice, never added, the
  trailing slash kept, refused again, the builder bypassing `api_base`

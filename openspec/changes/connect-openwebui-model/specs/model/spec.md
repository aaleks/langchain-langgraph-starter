## Purpose

The model is what the assistant thinks with: chosen from the settings -- the owner's local Open WebUI when it is configured, the offline model when nothing is -- and built in one place, `infrastructure/models.py`.

## ADDED Requirements

### Requirement: MODEL-CHOICE
The model SHALL be Open WebUI's when `OPENWEBUI_URL`, `OPENWEBUI_API_KEY` and `OPENWEBUI_MODEL` are all set, and the offline model when none is. When only some are set the choice SHALL be refused, naming each one missing -- never a silent fall back to the offline model.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_model_choice.py::TestModelChoice`

#### Scenario: Which model
| `OPENWEBUI_URL` | `OPENWEBUI_API_KEY` | `OPENWEBUI_MODEL` | Choice |
|---|---|---|---|
| `http://localhost:3000` | `sk-local` | `llama3.1:8b` | `openwebui` |
| empty | empty | empty | `offline` |

#### Scenario: Counter-example -- partly configured is refused, not defaulted
| Set | Refused, naming |
|---|---|
| `OPENWEBUI_URL` only | `OPENWEBUI_API_KEY, OPENWEBUI_MODEL` |
| `OPENWEBUI_URL`, `OPENWEBUI_MODEL` | `OPENWEBUI_API_KEY` |

### Requirement: MODEL-OPENWEBUI-CLIENT
The Open WebUI model SHALL be an OpenAI-compatible chat client addressed to `<OPENWEBUI_URL>/api` -- a trailing slash on the URL ignored -- with the configured key and model, a deadline of `MODEL_CALL_DEADLINE_SECONDS` per call, and no retries of its own: retrying is the assistant's policy, not the client's.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_models.py::TestOpenWebUIClient`

#### Scenario: The client the settings describe
- **GIVEN** `OPENWEBUI_URL=http://localhost:3000/`, `OPENWEBUI_API_KEY=sk-local`, `OPENWEBUI_MODEL=llama3.1:8b`
- **WHEN** the model is built
- **THEN** its base URL is `http://localhost:3000/api`, its model `llama3.1:8b`, its timeout `MODEL_CALL_DEADLINE_SECONDS` (120), its retries 0, and building it made no connection

#### Scenario: Counter-example -- nothing configured builds the offline model
- **GIVEN** none of the three settings
- **WHEN** the model is built
- **THEN** it is the offline model, and `langchain_openai` was not needed to build it

### Requirement: MODEL-OPENWEBUI-LIVE
With Open WebUI configured in `.env`, a run of the registered assistant SHALL be answered by that Open WebUI model: one model call, a transcript of `human, ai`, and an answer that is not empty and is not the offline model's.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_openwebui_live.py::TestAnsweredByOpenWebUI`

#### Scenario: A real answer
- **GIVEN** `.env` configuring an Open WebUI that is running
- **WHEN** the registered assistant runs on the human message `Reply with one word.`
- **THEN** the transcript's message types are `human, ai`, the answer is not empty, and it is not the offline model's fixed answer

#### Scenario: Counter-example -- not configured, not run
- **GIVEN** a `.env` that does not configure Open WebUI
- **THEN** the test is skipped, saying so -- never passed

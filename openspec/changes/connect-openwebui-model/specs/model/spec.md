## Purpose

The model is what the assistant thinks with: chosen from the settings -- the owner's local Open WebUI when it is configured, the offline model when nothing is -- and built in one place, `infrastructure/models.py`.

## ADDED Requirements

### Requirement: MODEL-CHOICE
The model SHALL be Open WebUI's when `OPENWEBUI_URL`, `OPENWEBUI_API_KEY` and `OPENWEBUI_MODEL` are all set, and the offline model when none is. When only some are set the choice SHALL be refused, naming each one missing -- never a silent fall back to the offline model -- and so SHALL a URL that is not `http` or `https` with a host and, if it names one, a valid port, the refusal naming `OPENWEBUI_URL`.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_model_choice.py::TestModelChoice`

#### Scenario: Which model
| `OPENWEBUI_URL` | `OPENWEBUI_API_KEY` | `OPENWEBUI_MODEL` | Choice |
|---|---|---|---|
| `http://localhost:3000` | `sk-local` | `llama3.1:8b` | `openwebui` |
| `https://webui.lan` | `sk-local` | `llama3.1:8b` | `openwebui` |
| `http://[::1]:3000` | `sk-local` | `llama3.1:8b` | `openwebui` |
| empty | empty | empty | `offline` |

#### Scenario: Counter-example -- partly or wrongly configured is refused, not defaulted
| Set | Refused, naming |
|---|---|
| `OPENWEBUI_URL` only | `OPENWEBUI_API_KEY, OPENWEBUI_MODEL` |
| `OPENWEBUI_URL`, `OPENWEBUI_MODEL` | `OPENWEBUI_API_KEY` |
| all three, the URL `localhost:3000` (no scheme) | `OPENWEBUI_URL` |
| all three, the URL `http://:3000` (no host) | `OPENWEBUI_URL` |
| all three, the URL `http://localhost:99999` or `http://localhost:abc` (no valid port) | `OPENWEBUI_URL` |
| all three, the URL `http://[::1` (not a URL at all) | `OPENWEBUI_URL` |

### Requirement: MODEL-TRANSIENT-FAILURES
A failed model call SHALL be transient exactly when it timed out, its connection failed, or the server answered HTTP 408, 429, 500, 502, 503 or 504.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_retries.py::TestTransientFailures`

#### Scenario: Transient
| Failure | Transient |
|---|---|
| timed out | yes |
| connection failed | yes |
| HTTP 408, 429, 500, 502, 503, 504 | yes |

#### Scenario: Counter-example -- the same on every try
| Failure | Transient |
|---|---|
| HTTP 400, 401, 403, 404, 409, 422, 501, 505 | no |
| no status, no timeout, no connection failure | no |

### Requirement: MODEL-OPENWEBUI-CLIENT
The Open WebUI model SHALL be an OpenAI-compatible chat-completions client addressed to `<OPENWEBUI_URL>/api` -- a trailing slash on the URL ignored -- with the configured key and model, a timeout of `MODEL_CALL_TIMEOUT_SECONDS` on every wait for the model, a streamed chunk included, and no retries of its own: retrying is the assistant's policy, not the client's.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_models.py::TestOpenWebUIClient`

#### Scenario: The client the settings describe
- **GIVEN** `OPENWEBUI_URL=http://localhost:3000/`, `OPENWEBUI_API_KEY=sk-local`, `OPENWEBUI_MODEL=llama3.1:8b`
- **WHEN** the model is built
- **THEN** its base URL is `http://localhost:3000/api`, its model `llama3.1:8b`, its timeout and its streamed-chunk timeout `MODEL_CALL_TIMEOUT_SECONDS` (120), its retries 0, it never uses the Responses API, and building it made no connection

#### Scenario: Counter-example -- nothing configured builds the offline model
- **GIVEN** none of the three settings, and `langchain_openai` impossible to import
- **WHEN** the models module is imported afresh and the model built
- **THEN** it is the offline model

### Requirement: MODEL-OPENWEBUI-LIVE
With Open WebUI configured in `.env`, a run of the registered assistant SHALL be answered by that Open WebUI model: one model turn, a transcript of `human, ai`, and an answer that is not empty and is not the offline model's.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_openwebui_live.py::TestAnsweredByOpenWebUI`

#### Scenario: A real answer
- **GIVEN** `.env` configuring an Open WebUI that is running
- **WHEN** the registered assistant runs on the human message `Reply with one word.`
- **THEN** the transcript's message types are `human, ai`, the answer is not empty, and it is not the offline model's fixed answer

#### Scenario: Counter-example -- not configured, not run
- **GIVEN** a `.env` that does not configure Open WebUI
- **THEN** the test is skipped, saying so -- never passed

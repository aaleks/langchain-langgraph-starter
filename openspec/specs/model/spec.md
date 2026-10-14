# model Specification

## Purpose
The model is what the assistant thinks with: chosen from the settings -- the owner's local Open WebUI when it is configured, the offline model when nothing is -- and built in one place, `infrastructure/models.py`.

## Requirements

### Requirement: MODEL-CHOICE
The model SHALL be Open WebUI's when `OPENWEBUI_URL`, `OPENWEBUI_API_KEY` and `OPENWEBUI_MODEL` are all set, and the offline model when none is. When only some are set the choice SHALL be refused, naming each one missing -- never a silent fall back to the offline model -- and so SHALL a URL that is not Open WebUI's address -- `http` or `https`, a host, a port from 1 to 65535 if it names one, no user or password, no query or fragment, and no path beyond an `/api` segment -- the refusal naming `OPENWEBUI_URL`.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_model_choice.py::TestModelChoice`

#### Scenario: Which model
| `OPENWEBUI_URL` | `OPENWEBUI_API_KEY` | `OPENWEBUI_MODEL` | Choice |
|---|---|---|---|
| `http://localhost:3000` | `sk-local` | `llama3.1:8b` | `openwebui` |
| `https://webui.lan` | `sk-local` | `llama3.1:8b` | `openwebui` |
| `http://[::1]:3000` | `sk-local` | `llama3.1:8b` | `openwebui` |
| `https://webui.lan/openwebui` (behind a proxy, under a path) | `sk-local` | `llama3.1:8b` | `openwebui` |
| `http://localhost:3000/api` or `http://localhost:3000/api/` (the API's address) | `sk-local` | `llama3.1:8b` | `openwebui` |
| `https://webui.lan/tools/openwebui` (two segments) | `sk-local` | `llama3.1:8b` | `openwebui` |
| `http://api/openwebui` (a host named `api`) | `sk-local` | `llama3.1:8b` | `openwebui` |
| `http://localhost:1` or `http://localhost:65535` (the lowest and highest ports) | `sk-local` | `llama3.1:8b` | `openwebui` |
| empty | empty | empty | `offline` |

#### Scenario: Counter-example -- partly or wrongly configured is refused, not defaulted
| Set | Refused, naming |
|---|---|
| `OPENWEBUI_URL` only | `OPENWEBUI_API_KEY, OPENWEBUI_MODEL` |
| `OPENWEBUI_URL`, `OPENWEBUI_MODEL` | `OPENWEBUI_API_KEY` |
| `OPENWEBUI_API_KEY`, `OPENWEBUI_MODEL` | `OPENWEBUI_URL` |
| `OPENWEBUI_MODEL` only | `OPENWEBUI_URL, OPENWEBUI_API_KEY` |
| all three, the URL `localhost:3000` (no scheme) | `OPENWEBUI_URL` |
| all three, the URL `http://:3000` (no host) | `OPENWEBUI_URL` |
| all three, the URL `http://localhost:99999`, `http://localhost:abc`, `http://localhost:0` or `http://localhost:` (no valid port) | `OPENWEBUI_URL` |
| all three, the URL `http://[::1` (not a URL at all) | `OPENWEBUI_URL` |
| all three, the URL `http://localhost:3000/?x=1` or `http://localhost:3000/#top` | `OPENWEBUI_URL` |
| all three, the URL `http://localhost:3000/api/chat/completions` or `https://webui.lan/openwebui/api/chat/completions` (an endpoint, not the address) | `OPENWEBUI_URL` |
| all three, the URL `http://owner:secret@localhost:3000` or `http://owner@localhost:3000` (a user, with or without a password) | `OPENWEBUI_URL` |
| all three, the URL `https://webui.lan/api/openwebui` (a site under an `/api/` prefix) | `OPENWEBUI_URL` |

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

#### Scenario: Exactly those statuses
- **GIVEN** every HTTP status from 100 to 599, no timeout and no connection failure
- **THEN** the transient ones are exactly 408, 429, 500, 502, 503 and 504

### Requirement: MODEL-OPENWEBUI-CLIENT
The Open WebUI model SHALL be an OpenAI-compatible chat-completions client addressed to `<OPENWEBUI_URL>/api` -- a trailing slash on the URL ignored, and a URL whose path already ends in `/api` taken as the API itself -- with the configured key and model, a timeout of `MODEL_CALL_TIMEOUT_SECONDS` on every wait for the model -- the whole reply when the call carries tools, since it is then not streamed; each chunk otherwise -- an output cap of `MODEL_OUTPUT_TOKENS` tokens a reply, no streamed call while tools are bound -- a streamed call's arguments are re-parsed at every chunk, worse than linearly -- and no retries of its own: retrying is the assistant's policy, not the client's.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_models.py::TestOpenWebUIClient`

#### Scenario: The client the settings describe
- **GIVEN** `OPENWEBUI_URL=http://localhost:3000/`, `OPENWEBUI_API_KEY=sk-local`, `OPENWEBUI_MODEL=llama3.1:8b`
- **WHEN** the model is built
- **THEN** its base URL is `http://localhost:3000/api`, its key `sk-local`, its model `llama3.1:8b`, its timeout and its streamed-chunk timeout `MODEL_CALL_TIMEOUT_SECONDS` (300: a whole reply at the cap from the slower measured model, about 259 s), its output cap `MODEL_OUTPUT_TOKENS` (4,096), sent in the request as `max_completion_tokens`, its streaming off whenever tools are bound, its retries 0, it never uses the Responses API, and building it made no connection

#### Scenario: Counter-example -- nothing configured builds the offline model
- **GIVEN** none of the three settings, and `langchain_openai` and `openai` impossible to import
- **WHEN** the models module is imported afresh and the model built
- **THEN** it is the offline model

#### Scenario: The API's address, under Open WebUI's
| `OPENWEBUI_URL` | Base URL |
|---|---|
| `http://localhost:3000/` | `http://localhost:3000/api` |
| `http://localhost:3000/api` | `http://localhost:3000/api` |
| `http://localhost:3000/api/` | `http://localhost:3000/api` |
| `https://webui.lan/openwebui` | `https://webui.lan/openwebui/api` |
| `https://webui.lan/openapi` (a path ending in `api`, not `/api`) | `https://webui.lan/openapi/api` |
| `http://api` (a host named `api`) | `http://api/api` |

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

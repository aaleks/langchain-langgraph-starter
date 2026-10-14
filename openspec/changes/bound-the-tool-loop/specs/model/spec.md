## MODIFIED Requirements

### Requirement: MODEL-OPENWEBUI-CLIENT
The Open WebUI model SHALL be an OpenAI-compatible chat-completions client addressed to `<OPENWEBUI_URL>/api` -- a trailing slash on the URL ignored, and a URL whose path already ends in `/api` taken as the API itself -- with the configured key and model, a timeout of `MODEL_CALL_TIMEOUT_SECONDS` on every wait for the model, a streamed chunk included, an output cap of `MODEL_OUTPUT_TOKENS` tokens a reply, and no retries of its own: retrying is the assistant's policy, not the client's.

- **Kind:** deterministic
- **Proved by:** `tests/integration/infrastructure/test_models.py::TestOpenWebUIClient`

#### Scenario: The client the settings describe
- **GIVEN** `OPENWEBUI_URL=http://localhost:3000/`, `OPENWEBUI_API_KEY=sk-local`, `OPENWEBUI_MODEL=llama3.1:8b`
- **WHEN** the model is built
- **THEN** its base URL is `http://localhost:3000/api`, its key `sk-local`, its model `llama3.1:8b`, its timeout and its streamed-chunk timeout `MODEL_CALL_TIMEOUT_SECONDS` (120), its output cap `MODEL_OUTPUT_TOKENS` (4,096), its retries 0, it never uses the Responses API, and building it made no connection

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

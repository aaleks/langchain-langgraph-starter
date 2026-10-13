# Frame

## Outcome

The owner fills three lines of `.env`, starts the server with
`bash scripts/serve.sh`, and the `assistant` answers through their local Open
WebUI. A briefly failing model is retried a bounded number of times, and a
stalled one times out rather than hanging; a misconfigured `.env` fails loudly at start,
naming what is missing; and the default suite still never calls a model.

Observable signals:

- With `.env` configured, `bash scripts/check.sh live` runs the registered
  assistant through Open WebUI and passes; without it, that test is skipped,
  saying why.
- `uv run pytest` is green on a machine with or without the owner's `.env`.
- A `.env` with the URL but no key is refused with both missing names.

**Non-goals:** tools, `invalid_tool_calls`, re-measuring the model-call budget
(slice 3); approval and interrupts (slice 4); any provider but Open WebUI.

## Existing options considered

Checked on 2026-10-12 against PyPI, Open WebUI's documentation and its source
(latest release v0.12.0, 2026-10-10), and the unpacked wheels.

**The client:**

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| **`langchain-openai`'s `ChatOpenAI`, `base_url=<url>/api`** | yes -- 1.7.x, released 2026-10-08 and -12 | Open WebUI's documented OpenAI-compatible endpoint, `POST /api/chat/completions`; Bearer key; `tools` forwarded verbatim and tool calls returned unexecuted (Open WebUI docs, "server-side tool calling") | `max_retries=0` -- the openai SDK otherwise retries twice itself, under our policy; `use_responses_api=False` -- some model ids switch it to `/responses`, which Open WebUI lacks; an explicit `base_url` and `api_key` -- `langchain-core` 1.6.9+ otherwise lets `LANGSMITH_GATEWAY` route `ChatOpenAI` to `gateway.smith.langchain.com` |
| `langchain-ollama` against Open WebUI's `/ollama` passthrough | yes | Ollama models only | bypasses Open WebUI's routing and keys; reaches only what Ollama serves |
| `init_chat_model("openai:...")` | yes | the same client | a string-built model -- the architecture refuses it outside `models.py`, and it hides the settings |
| An HTTP client of our own | -- | -- | a chat-model contract to own: tool-call parsing, streaming |

**Settings:**

| Option | Covers | Delta |
|---|---|---|
| **`python-dotenv`'s `dotenv_values(path)`** -- 1.2.4, 2026-10-01; already locked (through `langgraph-cli`) | parses `.env` into a dict without touching `os.environ` | the environment-wins merge -- three lines in `config/` |
| `load_dotenv()` | the same, by writing `os.environ` | mutates the process: a `.env` could then reach every library that reads the environment -- LangSmith's among them |
| `pydantic-settings` | typed settings, `.env` included | a framework for three strings |

**Retries:** `langchain`'s `ModelRetryMiddleware(max_retries=, retry_on=,
on_failure="error")` -- already installed, the ladder's choice; its default
`on_failure="continue"` turns a failure into a message that reads like an
answer, the inherited lesson.

**Decision:** adopt `ChatOpenAI` with the three explicit settings above,
`dotenv_values`, and `ModelRetryMiddleware` on a domain predicate. Chosen by
the agent under the owner's standing delegation; the owner chose the provider.

## Orchestration rung

Unchanged: the tool loop (`create_agent`). The retry policy is middleware on it.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | the owner, and the three signals above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | seven requirements, each with one |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | the live run asserts structure -- one call, `human, ai`, a non-empty answer that is not the offline one -- never the text |
| Data -- provenance, freshness, what happens when a source is withdrawn | N-A | no data read beyond the owner's settings |
| Untrusted input -- anything ingested that this project did not write | Partial | the person's message now reaches a real model, but no tool can act on its answer: the data-never-instruction requirement and its adversarial case come with the first tool (slice 3), as the roadmap says |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | three settings, `OPENWEBUI_URL`, `OPENWEBUI_API_KEY`, `OPENWEBUI_MODEL`, documented in `.env.example`; the default -- nothing configured -- keeps the offline model |
| Failure -- what the user sees when a dependency is down | Clear | ASSISTANT-TRANSIENT-RETRY: retried twice, then the failure itself; a deadline on every call |
| Cost -- tokens, time, money and storage per run | Clear | a local model: no money; time bounded by `MODEL_CALL_TIMEOUT_SECONDS` x (1 + `MODEL_RETRIES`) per call |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the project owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Are a 120 s timeout per wait and 2 retries right for the owner's model? | OPEN -- needs real runs | Starting policy; measured in the live test's runs. Owner: the project owner. Review by: 2026-12-31 |
| 2 | Open WebUI's Ollama path appears to drop `max_completion_tokens`, `temperature` and `top_p` (source-read, not run) | OPEN -- needs a live instance | Nothing here sets them; checked when one is first needed. Owner: the project owner. Review by: 2026-12-31 |
| 3 | `scripts/serve.sh` and the local-only environment do not empty `LANGSMITH_GATEWAY` / `LANGSMITH_GATEWAY_API_KEY` | Reported to the owner | Closed for this project's model by the explicit `base_url` and `api_key`; the seal itself is the method's and the owner's settings to change -- upstream with the suite seal (roadmap, Method) |

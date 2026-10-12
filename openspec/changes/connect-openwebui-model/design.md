# Design

Why: `frame.md`; scope: `intake.md`.

## Context

The registry builds `assistant` at import with the offline model
(`build_offline_model()`), through `factory.build_assistant(model, tools)`. No
setting is read anywhere; `config/` is empty.

## Decisions

| File | Holds | Layer rule |
|---|---|---|
| `src/starter/config/settings.py` | `Settings` (url, key, model); `read_settings(environ, dotenv)` -- the environment wins, `.env` fills the rest via `dotenv_values`, nothing written; `settings_from_process()` -- `os.environ` and the repository's `.env` | config: the only reader of `os.environ` |
| `src/starter/domain/models.py` | `choose_model(url, key, model) -> "openwebui" \| "offline"`, refusing a partial configuration with the missing names | domain: pure |
| `src/starter/domain/agents/budgets.py` | `MODEL_CALL_DEADLINE_SECONDS = 120`, beside `MODEL_CALLS_PER_RUN` | domain |
| `src/starter/domain/agents/retries.py` | `MODEL_RETRIES = 2`; `is_transient(status, timed_out, connection_failed)` | domain: facts in, a decision out |
| `src/starter/infrastructure/models.py` | `build_model(settings)` -- the choice, then `build_openwebui_model(...)` (`langchain_openai` imported inside it) or the offline model; `is_transient_failure(exc)` -- an exception's facts, handed to the domain | infrastructure: the only place a model is built, and the only place that knows the provider's exceptions |
| `src/starter/infrastructure/agents/factory.py` | `build_assistant(model, tools, *, transient=never)` -- adds `ModelRetryMiddleware(max_retries=MODEL_RETRIES, retry_on=transient, on_failure="error")` | agents adapter: the predicate arrives as a dependency, so the adapter imports no provider |
| `src/starter/infrastructure/agents/registry.py` | `assistant = registered_assistant()` -- a factory function: settings, model, graph | registration |

- **The environment wins, and `.env` never enters it.** `dotenv_values` reads
  the file into a dict; `read_settings` takes a value from the environment when
  the name is there -- an empty one included -- and from the dict otherwise.
  `load_dotenv` would write `os.environ`, and with it give a `.env` reach into
  every library that reads the environment.
- **The suite is sealed from the owner's `.env`.** `tests/conftest.py` sets the
  three settings empty in the process environment, beside `LOCAL_ONLY`; the
  environment wins, so every default test -- and the live server tests of
  slice 1b, which inherit it -- chooses the offline model. The live Open WebUI
  test reads `.env` alone, on purpose.
- **Partial is refused.** A URL without a key is a mistake the owner should
  hear about at start -- `ValueError` naming what is missing -- not a silent
  offline assistant.
- **One retry layer.** The client gets `max_retries=0`; `ModelRetryMiddleware`
  retries on the domain's predicate, `on_failure="error"`. `initial_delay` and
  `backoff_factor` stay at the middleware's defaults (1 s, x2); the tests pass
  a zero delay through a factory parameter rather than sleep.
- **What is transient** is the domain's: a timeout, a failed connection, or HTTP
  408, 429, 500, 502, 503, 504. `models.is_transient_failure` reads those facts
  off `openai`'s exceptions (`APITimeoutError`, `APIConnectionError`,
  `APIStatusError.status_code`). Anything else -- a 400, a 401, a `RuntimeError`
  -- is not, and propagates unchanged (ASSISTANT-ERRORS-PROPAGATE, modified:
  its model scenario now raises a `RuntimeError`, a timeout being transient).
- **The client:** `ChatOpenAI(base_url=<url>/api, api_key=, model=,
  timeout=MODEL_CALL_DEADLINE_SECONDS, max_retries=0, use_responses_api=False)`.
  Explicit `base_url` and `api_key` also close `langchain-core`'s
  `LANGSMITH_GATEWAY` routing (frame.md).
- **The registry reads settings in a function, at import.** The server imports
  the registry once; `registered_assistant()` reads the settings then -- `.env`
  included, so nothing is read before it is loaded (the inherited lesson).

## Orchestration design

N-A for the node table -- the tool loop. What changes:

- **Budgets:** `MODEL_CALL_DEADLINE_SECONDS = 120` per call; `MODEL_RETRIES = 2`
  per call; `MODEL_CALLS_PER_RUN = 10` unchanged (re-measured with tools,
  slice 3).
- **Errors:** transient -> retried, then raised; everything else -> raised
  unchanged. Both pinned by tests.
- **Runtime:** with `.env` configured, the served graph calls Open WebUI. The
  live server tests of 1b keep the offline model -- they inherit the suite's
  empty settings.

## Risks

- [The owner's `.env` leaks into a default test] -> the three settings are set
  empty in the suite's environment, and the environment wins.
- [Open WebUI's API keys are off by default] -> the live test fails with the
  server's 401/403 and the frame says where to switch them on.
- [A model's "Stream Chat Response" setting overrides the request's `stream`]
  -> the live test invokes; a mismatch shows there first.
- [Hours-old `langchain-openai` / `langchain-core` patch releases] -> bounded
  to the minor; the live test is the check.

## Migration and rollback

Nothing persists. With `.env` untouched the assistant behaves as before.
Rollback: revert; the offline model returns.

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
| `src/starter/domain/models.py` | `choose_model(url, key, model) -> "openwebui" \| "offline"`, refusing a partial configuration with the missing names; `api_base(url)` -- the API's address under it | domain: pure |
| `src/starter/domain/agents/budgets.py` | `MODEL_CALL_TIMEOUT_SECONDS = 120`, beside `MODEL_CALLS_PER_RUN` | domain |
| `src/starter/domain/agents/retries.py` | `MODEL_RETRIES = 2`, `RETRY_INITIAL_DELAY_SECONDS = 1.0`, `RETRY_BACKOFF_FACTOR = 2.0`; `is_transient(status, timed_out, connection_failed)` | domain: facts in, a decision out |
| `src/starter/infrastructure/models.py` | `build_model(settings)` -- the choice, then `build_openwebui_model(...)` (`langchain_openai` imported inside it) or the offline model; `is_transient_failure(exc)` -- an exception's facts, handed to the domain | infrastructure: the only place a model is built, and the only place that knows the provider's exceptions |
| `src/starter/infrastructure/agents/factory.py` | `build_assistant(model, tools, *, transient)` -- the predicate required, no default -- adds `ModelRetryMiddleware(max_retries=MODEL_RETRIES, retry_on=transient, on_failure="error")` | agents adapter: the predicate arrives as a dependency, so the adapter imports no provider |
| `src/starter/infrastructure/agents/registry.py` | `assistant = registered_assistant()` -- a factory function: settings, model, graph | registration |

- **The environment wins, and `.env` never enters it.** `dotenv_values` reads
  the file into a dict; `read_settings` takes a value from the environment when
  the name is there -- an empty one included -- and from the dict otherwise.
  `load_dotenv` would write `os.environ`, and with it give a `.env` reach into
  every library that reads the environment.
- **The suite is sealed from the owner's `.env`.** `tests/conftest.py` sets the
  three settings empty in the process environment, beside `LOCAL_ONLY`; the
  environment wins, so every default test -- and the live server tests of
  slice 1b, which inherit it -- chooses the offline model, unless a test sets
  its own settings over them: a stand-in on 127.0.0.1, never the owner's. The
  live Open WebUI test reads `.env` alone, on purpose.
- **Partial is refused.** A URL without a key is a mistake the owner should
  hear about at start -- `ValueError` naming what is missing -- not a silent
  offline assistant.
- **One retry layer.** The client gets `max_retries=0`; `ModelRetryMiddleware`
  retries on the domain's predicate, `on_failure="error"`, after
  `RETRY_INITIAL_DELAY_SECONDS` and then x `RETRY_BACKOFF_FACTOR` (1 s, 2 s),
  with the middleware's jitter. The timing is passed, not asserted: the jitter
  is random, and nothing observable depends on the delays yet. The tests pass
  a zero delay through a factory parameter rather than sleep.
- **What is transient** is the domain's: a timeout, a failed connection, or HTTP
  408, 429, 500, 502, 503, 504. `models.is_transient_failure` reads those facts
  off `openai`'s exceptions (`APITimeoutError`, `APIConnectionError`,
  `APIStatusError.status_code`). Anything else -- a 400, a 401, a `RuntimeError`
  -- is not, and propagates unchanged (ASSISTANT-ERRORS-PROPAGATE, modified:
  its model scenario now raises a `RuntimeError`, a timeout being transient).
- **The client:** `ChatOpenAI(base_url=<url>/api, api_key=, model=,
  timeout=MODEL_CALL_TIMEOUT_SECONDS, max_retries=0, use_responses_api=False)`.
  Explicit `base_url` and `api_key` also close `langchain-core`'s
  `LANGSMITH_GATEWAY` routing (frame.md).
- **The registry reads settings in a function, at import.** The server imports
  the registry once; `registered_assistant()` reads the settings then -- `.env`
  included, so nothing is read before it is loaded (the inherited lesson).

- **Verify pass 1's corrections** (`verify.md`):
  - *A timeout, not a deadline.* `MODEL_CALL_TIMEOUT_SECONDS` bounds every wait
    -- to connect, for the next part of an answer, for the next streamed chunk
    (`stream_chunk_timeout`, else langchain-openai's own 120 s, or its
    environment override, applies) -- not a whole call: a model that keeps
    answering is not cut off. A builtin `TimeoutError`, which is how
    langchain-openai reports a chunk that never came, is a timeout.
  - *Turns, not attempts.* `ModelCallLimitMiddleware` counts turns; the
    retries happen inside one. A run is at most `MODEL_CALLS_PER_RUN` turns of
    at most `1 + MODEL_RETRIES` attempts -- 30 requests, each waited on at most
    120 s at a time (ASSISTANT-MODEL-CALL-BUDGET, modified).
  - *The owner's Open WebUI is the one exception to "local only".*
    LOCAL-SERVER-STAYS-LOCAL is modified: the conversation goes to the Open
    WebUI `.env` names, wherever it runs -- the owner's choice. ADR 0004 is
    about LangSmith, and holds.
  - *Refused at start:* a partial configuration, and a URL that is not
    `http(s)://host`; an unreadable `.env`, naming the file. The file is not
    opened when the environment holds every setting.
  - *The suite* removes the owner's proxy and `OPENAI_*` variables and sets
    `NO_PROXY` for 127.0.0.1. The server's client still reads them from the
    owner's shell -- the owner's choice; recorded in `models.py`.
  - *Accepted, recorded:* the domain names the three variables as config does;
    the `.env` path is right for the editable install `uv sync` makes; the
    registry composes the model (the factory would, once a second graph
    exists); retrying a timeout on a single-slot local model may queue behind
    the abandoned generation.
- **Verify pass 2's corrections** (`verify.md`):
  - *The URL refusal names the variable, never the value* -- two lines
    swapped would otherwise print the key -- and refuses a bad port or an
    unparseable URL at start rather than at the first run.
  - *Accepted, recorded:* a permanent connection failure (a certificate
    refused) is retried like a transient one -- about 10 s lost, the cause in
    the traceback's chain; telling them apart needs the cause chain, and
    narrows MODEL-TRANSIENT-FAILURES -- revisited when a remote Open WebUI is
    configured. A streamed attempt cut off and retried leaves its partial text
    in the `messages` stream under its own id; the thread's state holds only
    the retried answer -- revisited when a client renders the stream (slice 6).
  - *Settings' text* shows the URL and the model as given: a key put in the
    URL's line would show there. The refusal at start, which names no value,
    comes first.
- **Verify pass 3's corrections** (`verify.md`):
  - *The URL is Open WebUI's address*: a query or a fragment is refused at
    start; a path under a reverse proxy is not. A URL already ending in
    `/api` -- every endpoint's prefix, an address an owner may well copy -- is
    taken as the API itself (`domain.models.api_base`) rather than refused:
    both name the same server.
  - *The export reads the process's settings*, proved at the default tier by
    loading `langgraph.json`'s file with the settings in the environment.
  - *`.env` values are read as written*: `interpolate=False`, since expanding
    `${NAME}` reads `os.environ` behind `read_settings`' argument.
  - *The retry predicate has no default*: a graph composed without one would
    quietly retry nothing. Tests that are not about retrying say so.
  - *`openai` is declared*, bounded to 3.29: its exception classes decide what
    is retried, and langchain-openai alone allows two majors.
  - *The models check names a model by its class and its SDK*: chat and
    completion models and embeddings by name, langchain_core's chat data
    excepted; a provider SDK's clients, imported from it or called through
    it.
- **Verify pass 4's corrections** (`verify.md`):
  - *The served export's retry policy* is proved through the export, loaded
    as the server loads it; the test waits the domain's first delay, about a
    second.
  - *The URL:* `api_base` decides on the path's last segment, not the text --
    a host named `api` keeps its `/api`; a path beyond an `/api` segment (Open
    WebUI's full endpoint, pasted) is refused at start, as are port 0 and an
    empty port.
  - *Accepted, recorded:* the models check sees the names a model goes by,
    not every way of reaching one -- `partial`, a class bound to another name
    by assignment, a model named like none (`langchain_community`'s `Ollama`);
    the overview says so. It guards against the natural slip, not an author
    set on evading it; revisited when a second model builder is wanted.
    `api_base`'s table is proved through the client builder, at the
    integration tier MODEL-OPENWEBUI-CLIENT needs anyway: a unit table of the
    same rows would prove the same claim twice.

## Orchestration design

N-A for the node table -- the tool loop. What changes:

- **Budgets:** `MODEL_CALL_TIMEOUT_SECONDS = 120` per wait for the model;
  `MODEL_RETRIES = 2` per turn; `MODEL_CALLS_PER_RUN = 10` turns, unchanged
  (re-measured with tools, slice 3).
- **Errors:** transient -> retried, then raised; everything else -> raised
  unchanged. Both pinned by tests.
- **Runtime:** with `.env` configured, the served graph calls Open WebUI. The
  live server tests of 1b keep the offline model -- they inherit the suite's
  empty settings, and assert its answer; one more server, its Open WebUI a
  stand-in on 127.0.0.1, proves the configured path stays on the machine.

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

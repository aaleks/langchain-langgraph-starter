# Verify

- **Verdict:** SHIP at `11c3f50` -- pass 5 (no BLOCKER, no MAJOR; nine
  MINOR, fixed after it and read in pass 6). Pass 4: DO NOT SHIP (two
  MAJOR). Pass 3: DO NOT SHIP (two MAJOR). Pass 2: DO NOT SHIP (two MAJOR).
  Pass 1: DO NOT SHIP (six MAJOR).
- **Reviewed at:** pass 5: `11c3f50`, the fix diff `9118344..11c3f50`,
  committed before the lenses read it. Pass 4: `7491b94`, the whole change with the fix diff
  `5dc4b99..7491b94` in focus, committed before the lenses read it. Pass 3:
  `6033d3a`, the fix diff `dade9c1..6033d3a` in focus. Pass 2: `bd4bc4e`, the
  fix diff `6dd2700..bd4bc4e`. Pass 1: `4dc2516`. Passes 1-3: the staged tree
  the lenses read, committed unchanged after they reported.
- **Evidence (pass 1):** `bash scripts/check.sh live` on the reviewed tree: all checks
  passed -- architecture 50, method 117 OK, suite 89, live 7 passed and 1
  skipped (Open WebUI not configured in `.env` yet). Seven mutations red
  (tasks.md). Three fresh-context lenses over `git diff --cached main`: proof
  (`spec-compliance`), defects (`code-reviewer`), placement
  (`architecture-guardian`); their mutations ran on scratch copies, no `.env`
  read.

## Findings

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | proof, placement, defects | The transient classification is mostly unproved: only a timeout and a 503 are exercised; removing 429 or `connection_failed` keeps every test green. No unit test of the domain predicate | `domain/agents/retries.py` | A unit-tier requirement with every status; the chain proved for each failure kind |
| 2 | MAJOR | proof, defects | SETTINGS-ENVIRONMENT-WINS's counter-example cannot catch `load_dotenv()`: the suite already sets `OPENWEBUI_URL=""`, which `load_dotenv` leaves alone | `test_settings.py:50-62` | Remove the name from the environment in that test; assert it stays absent |
| 3 | MAJOR | proof | MODEL-CHOICE's refusal is proved only on the pure function; a `build_model` with its own check could fall back silently | `infrastructure/models.py:29-36` | Prove it where the server starts: the registry refuses a partial configuration |
| 4 | MAJOR | proof, placement | Retries make ASSISTANT-MODEL-CALL-BUDGET's "at most 10 model calls" false: the budget counts turns, the retries happen inside one -- measured, 30 requests and 10 tool calls before the budget fired | `factory.py`; living spec | MODIFY the budget to turns, each of at most `1 + MODEL_RETRIES` attempts, with a scenario |
| 5 | MAJOR | proof | LOCAL-SERVER-STAYS-LOCAL is now conditional: an `OPENWEBUI_URL` on another host takes the conversation off the machine, and no requirement says so | living spec `local-server` | MODIFY it: beyond this machine, except the Open WebUI the owner configured |
| 6 | MAJOR | defects | A streamed call (the server's `messages` mode) times out with langchain-openai's `StreamChunkTimeoutError` -- a builtin `TimeoutError`, not an openai one: not retried, and its timer is not ours (reproduced) | `models.py` | Classify a builtin `TimeoutError` as timed out; set `stream_chunk_timeout` from the domain |
| 7 | MINOR | defects, proof | The "deadline" is a per-wait timeout (connect, each read, each chunk), not a total; the budget's comment says "measured" though nothing was | `budgets.py`; `models.py` | Name it a timeout; correct the comment and the frame |
| 8 | MINOR | defects | A URL without a scheme (`localhost:3000`) becomes a connection error, retried three times, naming nothing | `models.py` | Refuse a URL that is not `http(s)://host` at start |
| 9 | MINOR | defects | `.env` is parsed even when the environment holds every name; a UTF-16 `.env` then breaks every registry import, default suite included | `settings.py:42` | Read the file only for a missing name; a decode error names the file |
| 10 | MINOR | defects, placement | The suite is not sealed from proxies, nor from the `OPENAI_*` variables the client reads itself (`OPENAI_PROXY`, organisation, project, custom headers) | `tests/conftest.py` | Seal them in the suite; record that the owner's shell still reaches the client |
| 11 | MINOR | defects | "`langchain_openai` was not needed" cannot fail: the module was imported before the patch | `test_models.py:40-46` | Re-import the module under the patch |
| 12 | MINOR | defects, placement | The models check misses aliases and `AzureChatOpenAI`; `config/` has no external-import allowlist | `contract.py` | Flag names imported from provider packages; allow `config` only `dotenv` |
| 13 | MINOR | placement | The retry delay is a literal in the adapter; backoff left at library defaults | `factory.py` | `RETRY_INITIAL_DELAY_SECONDS`, `RETRY_BACKOFF_FACTOR` in the domain |
| 14 | MINOR | proof | Unclaimed: whitespace stripping, the settings' redacted text, `use_responses_api=False`; how the server finds `.env` is unproved | `settings.py`; `models.py` | Claim each in a requirement's scenario |
| 15 | MINOR | proof | ASSISTANT-REGISTERED says the retry policy's middleware is among the nodes -- it has none; the live test's "one model call" is a turn | spec; live test | Reword |
| 16 | MINOR | proof, defects | Stale text: the test docstrings quote the old requirements; `.env.example` says `clean_env` removes | tests; `.env.example` | Update |
| 17 | MINOR | placement | The domain repeats config's variable names; the `.env` path is right for an editable checkout only; the composition sits in the registry | `domain/models.py`; `settings.py`; `registry.py` | Recorded: accepted for now, written in the design |

## Not checked

- A live run through Open WebUI: `.env` does not configure it yet.
- The graph-architecture and durability lenses: no graph topology, registration
  or state changed.

## Pass 2 -- the fix diff `6dd2700..bd4bc4e`

- **Evidence:** `bash scripts/check.sh live` at `bd4bc4e`: `all checks
  passed`, exit 0 -- architecture 51, OpenSpec 3 passed, `sdd check` OK (11
  requirements in flight, 8 test files, 8 claimed), method 117 OK, manifest
  matches, suite 121 passed, live 7 passed and 1 skipped (Open WebUI not
  configured in `.env`). Eight mutations red (tasks.md 8.5).
- **Lenses:** proof (`spec-compliance`) and defects (`code-reviewer`), fresh
  context, over `git diff --cached main` with the pass-1 fix in focus. The
  defects lens stopped twice on a session limit before reporting and was
  re-run in full. Its probes and mutations ran on scratch copies; no `.env`
  read; nothing left running.
- **Pass 1 resolved:** 1, 2, 3, 4, 6, 9, 10, 11 and 13 rechecked by the
  defects lens and holding; 5 holds as written but is unproved (18); 7 is
  half done (23); 8 holds but is incomplete (21); 12 is incomplete (27).

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 18 | MAJOR | proof | LOCAL-SERVER-STAYS-LOCAL's one exception -- a configured Open WebUI -- never runs under the probe: every live server test inherits the suite's empty settings, so a configured server reaching anything else (a tokenizer download, a gateway) would pass | `test_local_server.py`; spec `local-server` | A live run of `serve.sh` with Open WebUI configured -- a stand-in on 127.0.0.1 -- under the probe |
| 19 | MAJOR | proof, defects | "A value of only spaces reads as empty" cannot fail: python-dotenv strips an unquoted value before `read_settings` sees it; with `.strip()` removed the suite stays green (mutation) | `settings.py:57`; `test_settings.py:42` | An environment value of spaces, and a quoted `.env` value `"   "`, which dotenv keeps (probed) |
| 20 | MINOR | defects, proof | The URL refusal quotes the value: an owner who swapped two lines (`OPENWEBUI_URL=sk-...`) sees the key in the start-up traceback; no scenario has a key beside a refused URL | `domain/models.py:31` | Name the variable and the expected form, never the value; a scenario |
| 21 | MINOR | defects, proof | The URL check is untested for a missing host (`http://:3000`), passes a bad port (`http://localhost:99999`, `:abc` -- failing only at run time), and lets `urlsplit`'s own error (`http://[::1`) escape without naming `OPENWEBUI_URL` | `domain/models.py:28-29` | Read the port inside the check; any `ValueError` becomes the refusal; rows for each |
| 22 | MINOR | proof | The transient counter-example has no 5xx outside the set: adding 501 or 505 (or 409) to `TRANSIENT_STATUSES` stays green | `test_retries.py` | 409, 501, 505 in the counter-example |
| 23 | MINOR | proof, defects | Finding 7 half done: the frame's Failure and Cost rows still say "a deadline on every call" and "x (1 + `MODEL_RETRIES`) per call"; design's Budgets say "per call" -- a model that sends a chunk every 119 s is never cut off | `frame.md:67-68`; `design.md:85-86` | Reword: per wait, per turn |
| 24 | MINOR | proof | The retry timing is unclaimed -- the factory could pass any delay or backoff and stay green -- and design still says the middleware's defaults apply | `factory.py`; `design.md:37-39` | Record it in the design: passed from the domain, not asserted (the middleware's jitter is random) |
| 25 | MINOR | defects | A permanent connection failure -- a self-signed certificate -- is retried like a transient one: three handshakes, ~10 s, then "Connection error." naming no URL. The code matches MODEL-TRANSIENT-FAILURES; the requirement is broad | `models.py:93` | Recorded: accepted for now (below) |
| 26 | MINOR | defects | A streamed attempt cut off mid-answer and retried leaves its partial text in the `messages` stream under its own id; the final state holds only the retried answer (reproduced) | `models.py:88` | Recorded: accepted for now (below) |
| 27 | MINOR | defects | The models check misses `init_chat_model` imported under another name, and flags any `langchain_*` class as a model -- `Chroma()` in a store would fail the build | `contract.py:55, 436, 453` | Track aliases of the inline builders; provider classes only by the chat-model name pattern |

Also noted, not counted: on Windows a child started with `env=None` sees an
empty variable as absent, and would fall back to the owner's `.env` -- every
subprocess the tests start passes `env`, and empty values were probed through
Python, Git bash and `uv run`; the server's log renders tracebacks without
frame locals, so the key in `choose_model`'s locals is not printed.

**Pass 2 verdict:** DO NOT SHIP -- 18 and 19 are MAJOR. Fixed in a separate
commit with the MINORs, and that diff is read in pass 3.

## Not checked -- pass 2

- The placement lens (`architecture-guardian`): not re-run on the fix diff;
  pass 3 runs all three lenses over the whole change.
- A live run through Open WebUI: `.env` does not configure it yet.

## Pass 3 -- the whole change, the fix diff `dade9c1..6033d3a` in focus

- **Evidence:** `bash scripts/check.sh live` on the reviewed tree: `all checks
  passed`, exit 0 -- architecture 51, OpenSpec 3 passed, `sdd check` OK,
  method 117 OK, manifest matches, suite 131 passed, live 8 passed and 1
  skipped (Open WebUI not configured in `.env`). Seven pass-2 mutations red
  (tasks.md 9.4).
- **Lenses:** proof (`spec-compliance`), defects (`code-reviewer`) and
  placement (`architecture-guardian`), fresh context, over `git diff --cached
  main`. The proof lens ran 24 mutations on a scratch copy, live ones included
  -- 18 red, 6 survived (below); it checked every test class's docstring
  against its requirement, word for word. No `.env` read; nothing left running.
- **Pass 2 resolved:** 18-24 and 27 rechecked, each red under its mutation;
  27's narrowing went too far (30).

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 28 | MAJOR | proof | MODEL-CHOICE: no row leaves the URL unset -- `if not url: return "offline"` passes every test, so a key and a model under a mistyped URL variable would run offline, unrefused | `domain/models.py:22`; `test_model_choice.py` | Rows: key and model set; model only |
| 29 | MAJOR | proof | ASSISTANT-REGISTERED: the export is never proved to read the process's settings at the default tier -- `assistant = registered_assistant(Settings("", "", ""))` keeps `check.sh` green; only a live test of another requirement turns red | `registry.py:24,28`; `test_registered_assistant.py` | Load the registry with the settings in the environment, against the stand-in; a partial environment refused at load |
| 30 | MINOR | placement, defects | The models check misses `import openai; openai.OpenAI()`, no longer catches completion models (`OllamaLLM`, `langchain_openai.OpenAI`) or embeddings HEAD caught, and flags `ChatPromptTemplate`, `ChatMessage` -- prompts in `application/` would fail the build | `contract.py:418-456` | Track module aliases of provider packages; name model classes by their package, not a pattern alone; counter-example rows for prompts and messages |
| 31 | MINOR | placement, defects | The URL check accepts a path and a query: `http://localhost:3000/api` -- Open WebUI's own documented base URL -- becomes `/api/api`, a 404 at the first run naming nothing | `domain/models.py:37-43`; `infrastructure/models.py:58` | Refuse a path ending in `/api`, a query or a fragment, naming `OPENWEBUI_URL` |
| 32 | MINOR | placement | Only `langchain_openai` is guarded against a module-level import: `import openai` at the top of `models.py` stays green | `test_models.py:50` | Make `openai` impossible to import too |
| 33 | MINOR | placement | `openai` is imported directly but not declared: its range is langchain-openai's, two majors wide, while the transient classification depends on its exception classes | `pyproject.toml` | Declare it, bounded to the checked minor |
| 34 | MINOR | placement | `config`'s allowlist (`dotenv`) has no fixture proving it can fail; `CLAUDE.md` and `docs/architecture/overview.md` still describe the old one | `contract.py:37`; `test_imports.py` | A fixture; the documents updated |
| 35 | MINOR | placement | `local_server(settings=)` accepts any name, so a proxy variable could come back after the hostile environment removed it | `tests/localserver.py` | Accept only the settings' names |
| 36 | MINOR | placement | The factory's default predicate `never` is a retry policy in the adapter: a second graph composed without one would retry nothing, every test green | `factory.py:21-30` | A required keyword |
| 37 | MINOR | proof | SETTINGS-ENVIRONMENT-WINS's counter-example reads a copy of `os.environ`: a reader writing into the mapping it is given passes | `test_settings.py:107` | Read `os.environ` itself |
| 38 | MINOR | proof | Spaces are proved on `OPENWEBUI_MODEL` only; trimming a non-empty value is claimed by no requirement | `test_settings.py`; `settings.py:57` | Rows for the URL and the key; claim trimming |
| 39 | MINOR | proof | `.env` values interpolate `${VAR}` from the real `os.environ`, bypassing `read_settings`' argument -- unclaimed | `settings.py:65` | `interpolate=False`, with a row |
| 40 | MINOR | proof | MODEL-TRANSIENT-FAILURES says "exactly" but samples: 507 made transient passes | `test_retries.py` | Every status from 100 to 599 |
| 41 | MINOR | proof | The session server's "no Open WebUI configured" is assumed: were the empty settings lost on the way, the owner's `.env` would answer and every session test pass | `test_local_server.py` | Assert the offline answer in both session runs |
| 42 | MINOR | proof | Stale text: the living `local-server` Purpose ("never reaching anything beyond 127.0.0.1"); `design.md` says the live server tests keep the offline model; `frame.md:63` "one call"; `CLAUDE.md` "No model provider is installed yet" | as listed | Reword; the Purpose with the archive |

Also noted, not counted: an empty port (`http://localhost:`), port 0 and a
hostname with a space pass the URL check -- httpx refuses the last at the first
run; the POSIX-only clauses of the live tests are unrun on this machine.

**Pass 3 verdict:** DO NOT SHIP -- 28 and 29 are MAJOR. Fixed in a separate
commit with the MINORs; that diff is read in pass 4.

## Not checked -- pass 3

- MODEL-OPENWEBUI-LIVE: it reads the owner's `.env` and calls a real model;
  `.env` does not configure Open WebUI yet.
- The SIGINT path and the `127.0.0.1:9` clause: POSIX only (CI's `live` job).

## Pass 4 -- the whole change, the fix diff `5dc4b99..7491b94` in focus

- **Evidence:** `bash scripts/check.sh live` on the reviewed tree: every
  default check passed -- architecture 52, OpenSpec 3 passed, `sdd check` OK,
  method OK, manifest matches, suite 150 passed; live 8 passed and 1 failed:
  MODEL-OPENWEBUI-LIVE, Open WebUI answering `400 {'detail': 'Model not
  found'}` -- the owner's URL accepted, the key accepted (no 401), the model id
  in `.env` not one this Open WebUI lists. That setting is the owner's to
  correct; no key-shaped line in the output. Nine pass-3 mutations red and
  five for `/api` (tasks.md 10.5).
- **Lenses:** proof (`spec-compliance`), defects (`code-reviewer`) and
  placement (`architecture-guardian`), fresh context, over
  `4e48cc0..7491b94`. Mutations on scratch copies only (proof: 3, 1 red and
  2 survived; placement: 2 on the models check, both survived). No `.env`
  read; no live test run by a lens.
- **Pass 3 resolved:** 28-42 rechecked by all three lenses and held; 29 is
  now red under `registered_assistant(Settings("", "", ""))`.
- **A decision, reversing 31's suggested fix:** a URL already ending in `/api`
  is taken as the API itself (`domain.models.api_base`), not refused. Both
  name the same server; refusing the API's own address would only send the
  owner back to edit `.env`. Found by the live run: the owner's URL was
  refused at start.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 43 | MAJOR | the live run | The owner's key was printed in the live test's traceback: pytest shows a failing frame's arguments, and `choose_model(url, key, model)` was one. Fixed before this pass and re-checked by the defects lens (`--tb=long`, `-l`, `--tb=native`): a failure is reported by its message alone | `test_openwebui_live.py` | Done: `reported_by_message_only`; the local log holding it deleted |
| 44 | MAJOR | proof | ASSISTANT-REGISTERED's "Its retry policy is the domain's" calls `registered_assistant(settings)`, never the export: `assistant = build_assistant(..., transient=lambda f: False)` keeps every test green, and the served graph would end a run on the first 503 | `test_registered_assistant.py:110-121`; `registry.py:28` | Load the export with the settings on a stand-in failing once with 503; assert two requests and `human, ai` |
| 45 | MAJOR | placement | The models check's provider-SDK branches cannot fail on their fixture: both SDK rows build `OpenAI`, which the name pattern already matches -- `from_sdk` and `through_sdk` each removed, the fixture stays green | `contract.py:450,467-471`; `test_graphs.py:370-371` | Rows the pattern does not match: `from ollama import Client as C; C()`, `import anthropic; anthropic.Anthropic()` |
| 46 | MINOR | defects, proof | `api_base` reads the URL's text, not its path: `http://api` keeps no `/api` (the host is `api`), and `endswith("api")` without the slash passes the suite -- `https://webui.lan/openapi` would lose its `/api` | `domain/models.py:44-46` | Decide on the parsed path's last segment; rows `http://api` and `.../openapi` |
| 47 | MINOR | defects | Open WebUI's full endpoint, `http://localhost:3000/api/chat/completions`, is accepted and becomes `.../chat/completions/api`: a 404 at the first run, naming nothing | `domain/models.py:50-60` | Refuse a path with segments after `/api`, naming `OPENWEBUI_URL` |
| 48 | MINOR | placement | The name pattern misses `Ollama`, `HuggingFaceEndpoint`, `ChatOpenAI.model_validate({})`, an alias assigned (`f = ChatAnthropic`) and `partial(...)` | `contract.py:422-426` | Flag any reference to a name from a model package outside `models.py`, non-model partners excepted |
| 49 | MINOR | placement | `api_base` is a pure decision proved only through `ChatOpenAI` | `test_models.py:46-56` | Its table at the unit tier; one integration row as the seam |
| 50 | MINOR | placement | The overview's enforcement table lacks "models are built only in `infrastructure/models.py`"; the design overstates its reach | `docs/architecture/overview.md:60-64`; `design.md` | Add the row; qualify the sentence |
| 51 | MINOR | proof | The URL refusal names a query but not a fragment, which it also refuses | `domain/models.py:33-36` | "no query or fragment" |
| 52 | MINOR | proof | `http://localhost:0` and `http://localhost:` pass: neither is a valid port (pass 3, noted not counted) | `domain/models.py:49-58` | Refuse both, with rows |

**Pass 4 verdict:** DO NOT SHIP -- 44 and 45 are MAJOR (43 fixed). Fixed in a
separate commit with the MINORs; that diff is read in pass 5.

## Not checked -- pass 4

- MODEL-OPENWEBUI-LIVE green: it ran, and failed on the owner's model id
  (above). Its code path ran up to Open WebUI's answer.
- The SIGINT path and the `127.0.0.1:9` clause: POSIX only (CI's `live` job).

## Pass 5 -- the fix diff `9118344..11c3f50`

- **Evidence:** `bash scripts/check.sh live` at `11c3f50`: every default check
  passed -- architecture 52, OpenSpec 3 passed, `sdd check` OK, method OK,
  manifest matches, suite 155 passed; live 8 passed and 1 failed, as in pass
  4: Open WebUI's `400 Model not found` for the owner's model id. No key-shaped
  line in the output. Eight pass-4 mutations red (tasks.md 11.4).
- **Lenses:** proof (`spec-compliance`), defects (`code-reviewer`) and
  placement (`architecture-guardian`), fresh context, over the fix diff, the
  commit read as it stands. Mutations on scratch worktrees only (proof: 13, 8
  red and 5 survived -- below); no `.env` read; no live test run by a lens.
- **Pass 4 resolved:** 44-47, 51 and 52 red under their mutations, rechecked
  by all three lenses; 48-50 accepted on the record, the reasons judged sound
  by the placement lens.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 53 | MINOR | defects | A URL with a user and password (`http://owner:secret@localhost:3000`) is accepted: httpx sends them as Basic auth over the bearer key -- measured on the stand-in, `sk-local` never sent; a 401 pointing at the wrong setting -- and `Settings`' text shows the password | `domain/models.py:53-69`; `config/settings.py:33-39` | Refuse a user or password in the URL, naming `OPENWEBUI_URL`; a row |
| 54 | MINOR | defects, placement | A site under an `/api/` prefix (`https://host/api/openwebui`) is refused: the spec says so, the design gives the reason only for a pasted endpoint | `domain/models.py:68`; `design.md` | Keep the rule; the design says it is chosen |
| 55 | MINOR | proof | ASSISTANT-REGISTERED's retry policy is proved for a retried failure only: an export retrying everything (`transient=lambda f: True`) stays green | `test_registered_assistant.py:114-126` | A 401 from the stand-in, raised after one request |
| 56 | MINOR | proof | The beyond-`/api` refusal has one row, starting with `/api`: only a leading `/api` refused, or the text checked (refusing the host `http://api/openwebui`), both stay green | `test_model_choice.py:64` | Refused `.../openwebui/api/chat/completions`; accepted `http://api/openwebui`, `.../api/` |
| 57 | MINOR | proof | No accepted row has two path segments: every such path refused stays green | `test_model_choice.py:19-26` | Accepted `https://webui.lan/tools/openwebui` |
| 58 | MINOR | proof | "A port from 1 to 65535" has no low or high accepted row: ports below 1024 refused stays green | `test_model_choice.py:19-26` | Accepted `:1` and `:65535` |
| 59 | MINOR | placement | Parts of the models check can be deleted, the fixture green: the `Error` lookahead, the chat-data exclusions past `Prompt`/`Message`, the SDK call's capital-letter guard, a builder called as an attribute | `contract.py:423-424,471,476`; `test_graphs.py:376-384` | Rows: `cm.init_chat_model(...)`; counter-examples `ChatResult`, `ChatGenerationChunk`, `SomeChatError()`, `openai.base_url_for(...)` |
| 60 | MINOR | placement | An SDK's exception is reported as a model built: `raise openai.APITimeoutError(...)` outside `models.py` would fail the build | `contract.py:449-456,468-472` | The `Error` exclusion for SDK names too; a counter-example |
| 61 | MINOR | placement | The accepted blind spots leave out a classmethod constructor (`ChatOpenAI.model_validate({})`), named in 48 | `design.md`; `overview.md:65` | Name it in both |

**Pass 5 verdict:** SHIP at `11c3f50` -- no BLOCKER, no MAJOR. The MINORs are
cheap and 53 sends the wrong credential, so they are fixed before the land,
in a separate commit read in pass 6.

## Not checked -- pass 5

- MODEL-OPENWEBUI-LIVE green: the owner's model id (pass 4).
- The SIGINT path and the `127.0.0.1:9` clause: POSIX only (CI's `live` job).
- The eight requirements the fix diff did not touch: re-proved in pass 4.

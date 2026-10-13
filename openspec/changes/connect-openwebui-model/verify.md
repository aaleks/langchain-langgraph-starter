# Verify

- **Verdict:** DO NOT SHIP -- pass 2 (two MAJOR). First fix: run the server
  with Open WebUI configured under the probe (finding 18). Pass 1: DO NOT SHIP
  (six MAJOR).
- **Reviewed at:** pass 2: `bd4bc4e`, the fix diff `6dd2700..bd4bc4e` -- the
  staged tree the lenses read, committed unchanged after they reported. Pass 1:
  `4dc2516`, likewise.
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

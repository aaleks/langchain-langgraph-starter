# Verify

- **Verdict:** DO NOT SHIP -- pass 1. First fix: prove the transient
  classification at the domain's tier, and classify a streamed call's timeout
  as transient (findings 1, 6).
- **Reviewed at:** `4dc2516` -- the staged tree the lenses read, committed
  unchanged after they reported.
- **Evidence:** `bash scripts/check.sh live` on the reviewed tree: all checks
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

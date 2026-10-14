# Verify

- **Verdict:** DO NOT SHIP -- pass 2 (one MAJOR). First fix: never stream a
  call with tools bound (finding 14). Pass 1: DO NOT SHIP (four MAJOR).
- **Reviewed at:** pass 2: `26d897b`, the fix diff `d604dee..26d897b`. Pass
  1: `d941831`, the whole change (`git diff
  main..d941831`), committed before the lenses read it.
- **Evidence (pass 1):**
  - `bash scripts/check.sh live` at `d941831`: every check passed; suite 266,
    and live 9 passed, the Open WebUI test among them. No key-shaped line,
    and no `.data/`.
  - Eleven mutations red, none hanging (tasks.md 5.3, 5.4).
  - The measurement: N = 20 on `gpt-5.4-mini` (frame.md, tasks.md 5.2).
  - Four fresh-context lenses over the diff:
    - proof (`spec-compliance`): 10 mutations, 6 red and 4 survived;
    - defects (`code-reviewer`);
    - graph (`graph-architecture-guardian`);
    - capabilities (`agent-capability-auditor`).

    Scratch copies only. No `.env` read, no live test run, and no paid
    model call by a lens.
- **After the lenses, a check by the agent:** one call of the owner's model
  capped at 20 tokens returned `finish_reason: length` and 20 tokens. Open
  WebUI honours an output cap.

## Findings

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | capabilities, defects, graph, proof | `call_chars` counts `tool_calls`' arguments, not `invalid_tool_calls`' raw ones. `langchain-openai` sends those, and the error message repeated them: 70,011 characters of bad arguments counted 70,700, while the request held 140,990. A call far over the budget passes | `middleware.py:call_chars` | Count invalid calls' raw arguments; stop repeating them (5); a row near the bound |
| 2 | MAJOR | capabilities | Nothing caps what the model writes: injected text could make it write a huge, paid-for reply before any check sees it | `infrastructure/models.py` | The owner chose: a cap of 4,096 tokens a reply, and a reply cut off at it ends the run with a named error |
| 3 | MAJOR | proof | Only one malformed call per reply is tested: answering only the first stays green. A real endpoint refuses the next request when a call has no answer | `test_assistant.py` | A row with two malformed calls, one error tool message per id |
| 4 | MAJOR | proof | "Every message's text" is unproved for AI messages: the fixtures' AI content is empty, so not counting it stays green | `test_assistant.py:TestContextBudget` | AI text in the rows |
| 5 | MINOR | defects, capabilities, graph, proof | The error message repeats the model's whole malformed output and a LangChain docs link. A streamed reply records no error, so the fallback text is sent instead. And "names the parse error" is asserted by a substring a constant passes | `middleware.py:34` | One short fixed message naming the tool, the same streamed or not, asserted exactly |
| 6 | MINOR | defects | An invalid call with no id crashes the run with a pydantic error: `ToolMessage(tool_call_id=None)` | `middleware.py:AnswerInvalidCalls` | Skip a call without an id, as LangChain's own patching does |
| 7 | MINOR | graph | The budget decision `count > budget` sits in the adapter | `middleware.py` | A domain function, unit-tested |
| 8 | MINOR | graph | That the context error is never retried is unproved: every test passes `no_retries` | `test_assistant.py` | The 150,001 row with the registry's retry predicate, the model called once |
| 9 | MINOR | proof | The prompt's "cannot change a task yet" is not asserted; `ASSISTANT_PROMPT_VERSION` is read by nothing, so nothing makes it move with the text | `prompts.py` | The clause asserted; the text pinned to its version by a digest |
| 10 | MINOR | capabilities | The budget is per call. Each turn re-sends the conversation, so the per-run worst case (10 turns x 3 attempts x 150,000) is unstated | `budgets.py`; frame | State it |
| 11 | MINOR | defects, proof | The script counts model attempts, not turns, and tools run, not calls proposed (refused ones spend the tool budget too). `--repeat 0` crashes. It copies the registry's composition | `scripts/measure_tool_loop.py` | Count turns and proposed calls from the transcript; refuse `--repeat < 1`; compose through one shared function |
| 12 | MINOR | capabilities | Tools, filters or web search configured on the model inside Open WebUI run outside the graph's allow-lists and the "no effect" test | -- | Recorded: the configured model must have none |
| 13 | MINOR | proof | ASSISTANT-MODEL-CALL-BUDGET's scenario title still says 41 | spec | OpenSpec keeps a scenario's title; the body says 61 and why. Accepted |

**Pass 1 verdict:** DO NOT SHIP -- four MAJOR. They are fixed in a separate
commit with the MINORs, and that diff is read in pass 2.

## Not checked -- pass 1

- An evaluated score for resisting prompt injection: a non-goal (frame.md).
- The live measurement with a lens: it calls a paid model, and only the
  agent runs it.

## Pass 2 -- the fix diff `d604dee..26d897b`

- **Evidence:** `bash scripts/check.sh live` at `26d897b`:
  - Every check passed; suite 277, live 9.
  - Ten pass-1 mutations red (tasks.md 6.7).
  - The measurement re-run through `task_tools`: N = 20, unchanged maxima.
- **Lenses:** fresh context, over the fix diff:
  - proof (`spec-compliance`): 18 mutations, 15 red and 3 survived;
  - defects (`code-reviewer`);
  - capabilities (`agent-capability-auditor`), which drove the real
    `ChatOpenAI` against a fake OpenAI server, invoked and streamed.

  The proof lens's scratch venv broke on Windows' path length. While it was
  replacing it, one chained command ran `uv sync -q` and a read-only pytest
  in the repository. The repository was left clean.
- **After the lenses, checks by the agent:**
  - On the owner's server, `qwen3:1.7b` -- an Ollama model -- ignored the
    cap. Sent as `max_completion_tokens` or as `max_tokens`, it wrote 1,272
    and 1,694 tokens and reported `stop`. Only `options.num_predict` capped it
    (20 tokens), and it still reported `stop`.
  - The cloud route refuses `options` (400) and honours the cap, streamed
    too: `length`, with 20 output tokens reported.
  - Merging streamed chunks of arguments that never repair took 0.14 s for
    500 characters, 0.58 s for 1,000 and 3.19 s for 2,000. That confirms
    finding 14.
- **Pass 1 resolved:**
  - 1-4, 6, 9 and 13 fixed and proved.
  - 5, 7 and 8 fixed in code but only partly proved (below).
  - 10-12 recorded.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 14 | MAJOR | capabilities | A streamed reply's tool-call arguments are re-parsed at every chunk merge, worse than linearly. Arguments that never repair stall the event loop: 2,000 characters took 3.2-8.1 s, and a capped reply can be about 16,000. No budget covers time | `models.py`; langchain-core | Never stream a call that has tools bound (`disable_streaming="tool_calling"`), proved on the client |
| 15 | MINOR | defects | The output cap holds only where the backend honours it. An Ollama model behind Open WebUI ignores it, and reports `stop` even when capped by its own `num_predict` | `middleware.py`; `models.py` | A reply whose output tokens reach the cap counts as cut off too. A local model needs `num_predict` set in Open WebUI (`.env.example`). The requirement says so |
| 16 | MINOR | defects | The 4,096 cap is unmeasured, and on a reasoning model it counts hidden reasoning tokens | `budgets.py` | Record output tokens in the measurement, and re-run it |
| 17 | MINOR | proof | The retry-predicate row cannot fail: the budget refuses before the model either way | `test_assistant.py` | Assert the predicate itself: neither budget error is transient |
| 18 | MINOR | proof | "Streamed or not" is unproved: every fixture carries an error | `test_assistant.py` | A row with no error recorded, the same sentence |
| 19 | MINOR | proof | "Naming the cap" is a substring check: 40960 contains 4096 | `test_assistant.py` | `ended.value.cap == 4096` |
| 20 | MINOR | proof | "Every call asks for at most 4,096" is proved only by MODEL-OPENWEBUI-CLIENT's test | spec | The cap is the client's requirement; the output budget names it |
| 21 | MINOR | capabilities | The cap test checks the client's attribute, not the request it sends | `test_models.py` | Assert the request's `max_completion_tokens` |
| 22 | MINOR | defects | A malformed call without an id beside one with an id: the answered one jumps back, and the request then holds an unanswered call, which the endpoint refuses | `middleware.py` | Answer none unless every malformed call has an id; a row |
| 23 | MINOR | capabilities, defects, proof | The script's maxima leave out runs that ended in a budget error, under an N for every run. The worst case per run is stated in characters, not the tokens adversarial text could reach, and the output's is not stated. `.env.example` misses Open WebUI's global filters | script; `budgets.py`; `.env.example` | N per statistic; both worst cases stated; filters named |
| 24 | MINOR | proof | `check_context_chars` has no unit test of its own, and the fallback name "the tool" is untested | `budgets.py`; `middleware.py` | Accepted: the domain function is proved through ASSISTANT-CONTEXT-BUDGET's tests, and a call always carries a name from Open WebUI |

**Pass 2 verdict:** DO NOT SHIP -- 14 is MAJOR. It is fixed in a separate
commit with the MINORs, and that diff is read in pass 3.

## Not checked -- pass 2

- The live measurement by a lens: it calls a paid model.

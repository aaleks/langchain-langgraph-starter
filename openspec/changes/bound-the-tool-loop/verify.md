# Verify

- **Verdict:** DO NOT SHIP -- pass 1 (four MAJOR). First fix: count every
  argument a call sends, malformed calls' included (finding 1).
- **Reviewed at:** pass 1: `d941831`, the whole change (`git diff
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

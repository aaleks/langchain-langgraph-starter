# Design

Why: `frame.md`, with the measurement. Scope: `intake.md`.

## Context

The factory composes `create_agent` with three middlewares: the model-call
budget, the tool-call budget and the retry policy. It has no system prompt. A
reply carrying only `invalid_tool_calls` ends the run as an empty answer
(measured). Nothing bounds what one call sends the model, beyond what one read
returns.

## Decisions

| File | Holds | Layer rule |
|---|---|---|
| `src/starter/application/prompts.py` | `ASSISTANT_PROMPT`: what the assistant is for, its two tools, that it cannot change a task yet, and that tool output is data, never instructions | application: prompts |
| `src/starter/domain/agents/budgets.py` | `CONTEXT_CHARS_PER_CALL = 150_000`, with its evidence; `ContextBudgetExceededError(count, budget)`; the two call budgets' comments cite the measurement | domain |
| `src/starter/infrastructure/agents/middleware.py` | `AnswerInvalidCalls`: `after_model`, one error tool message per invalid call, then back to the model when no well-formed call is left. `ContextBudget`: `wrap_model_call`, counting with `call_chars(system, messages)` and raising before the handler. `call_chars` counts each message's text and each tool call's arguments | agents adapter: middleware |
| `src/starter/infrastructure/agents/factory.py` | `system_prompt=ASSISTANT_PROMPT`; the two middlewares beside the budgets | composition |
| `tests/openwebui_stub.py` | A reply may be a list of tool calls, for one turn proposing many | tests |
| `scripts/measure_tool_loop.py` | Counts with `call_chars`, so the measurement and the budget agree | tooling |

- **The malformed call's answer** names the parse error that langchain-core
  records. That error carries the model's own arguments, never anything else.
  `langchain-openai` sends an invalid call as a `tool_call`, so the error
  tool message that answers it keeps the request well formed (checked:
  `_convert_message_to_dict`).
- **The budget counts characters, not tokens.** Characters are
  deterministic, provable with `==`, and need no tokenizer for a model the
  owner can change in `.env`. A token is about four characters in English,
  so 150,000 characters is about 37,500 tokens: inside the measured model's
  window, and the local `qwen3:1.7b`'s 32k-token window would sit near it.
- **The retry policy does not see the context error:**
  `is_transient_failure` classifies `ContextBudgetExceededError` as not
  transient, so it propagates.
- **The prompt is sent, not stored.** `create_agent` puts it in each request;
  the thread's state holds no system message.
- **The step ceiling** moves again with the new `after_model` node. Measured:
  60 supersteps end at the ceiling, 61 in the budget's error
  (ASSISTANT-MODEL-CALL-BUDGET, modified).
- **The budgets' values stay, with evidence.** Measured with N = 20 on
  `gpt-5.4-mini`: at most 2 model calls and 2 tool calls per run, at most
  16,148 characters sent to one call (`frame.md`).

## Orchestration design

N-A for the node table: the tool loop. What changes:

| Route | Outcome |
|---|---|
| a malformed call, alone | an error tool message per call; the model called again |
| a malformed call beside well-formed ones | the well-formed ones run; each malformed one answered |
| the conversation over `CONTEXT_CHARS_PER_CALL` | `ContextBudgetExceededError`, the model not called |
| task text giving orders | data in a tool message; whatever the model proposes stays within the tools and the budgets |

## Risks

- [The prompt changes the measured numbers] -> it adds about 500 characters
  per call. After the change, the measurement is re-run and its results
  recorded in `verify.md`.
- [A long conversation on a large-window model ends sooner than it must] ->
  the budget is per call, and the conversation is re-sent each turn. Raising
  it is a one-line change, re-measured.

## Migration and rollback

Nothing persists. Rollback is a revert.

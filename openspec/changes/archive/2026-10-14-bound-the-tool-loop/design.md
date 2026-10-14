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
- **Both paths, sync and async.** The local server runs graphs with `astream`. A middleware with only `wrap_model_call` raises `NotImplementedError` there, so `ContextBudget` implements `awrap_model_call` too. `after_model` runs on both paths as it is (measured), and the default suite exercises the async path.
- **The middleware's order matters.** `after_model` hooks run last-first. `AnswerInvalidCalls` is listed first, so its jump back to the model comes after the model-call budget has counted the turn. Listed last, an endless malformed reply looped past the budget (measured: 13 calls in 40 steps).
- **The step ceiling** moves again with the two new `after_model` nodes.
  Measured: 70 supersteps end at the ceiling, 71 in the budget's error
  (ASSISTANT-MODEL-CALL-BUDGET, modified).
- **The budgets' values stay, with evidence.** Measured with N = 20 on
  `gpt-5.4-mini`: at most 2 model calls and 2 tool calls per run, at most
  16,148 characters sent to one call (`frame.md`).

- **Verify pass 1's corrections** (`verify.md`):
  - *Every argument counted.* A malformed call's raw arguments are sent by
    `langchain-openai`, so `call_chars` counts them. The answer to a malformed
    call is a fixed sentence naming the tool. It never repeats the model's
    output, which would double it, and it is the same whether the reply
    streamed (no parse error recorded) or not.
  - *A call without an id is left*, as LangChain's own patching leaves it:
    nothing could answer it.
  - *What the model writes is capped:* `max_tokens=MODEL_OUTPUT_TOKENS`
    (4,096). Open WebUI honours it (checked: `finish_reason: length`).
    `OutputBudget` ends the run on a reply cut off at the cap, before
    `AnswerInvalidCalls` could hand a cut-off call back. The owner chose
    this.
  - *The budget decision is the domain's:* `check_context_chars`.
  - *The prompt's text is pinned to its version* by a digest in the test.
  - *The script measures what the budgets count:* turns and proposed calls,
    from the transcript. It composes with the registry's own `task_tools`.
  - *Recorded:*
    - The per-run worst case, in `budgets.py`.
    - The model in Open WebUI must have no tools, filters or web search
      attached: they run outside the graph (`.env.example`).
    - The scenario title's 41 stays, as OpenSpec requires; its body says 71.

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

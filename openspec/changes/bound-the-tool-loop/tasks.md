# Sequence

- **Order:**
  1. The prompt, since every other test sees it in the model's inputs.
  2. The malformed call.
  3. The context budget.
  4. The step ceiling, re-measured with both.
  5. The adversarial case, through the registered graph.
  6. The measurement, re-run.
- **Wiring point:** `src/starter/infrastructure/agents/factory.py`.
- **Story test:**
  `tests/acceptance/agents/test_registered_assistant.py::TestUntrustedTaskText`
  -- through the real entry point, a stand-in Open WebUI and a real task list.

## 0. Foundation

- [x] 0.1 The stand-in Open WebUI: a reply may be several tool calls
- [x] 0.2 The story test -- green when written: the tools are read-only, an
  unknown tool is refused, the tool-call budget holds. The requirement records
  what already held, and mutations prove its tests can fail (5.3)

## 1. ASSISTANT-PROMPT

- [x] 1.1 /accept -- red: `No module named 'starter.application.prompts'`
- [x] 1.2 /tdd -- `ASSISTANT_PROMPT` (version 1), sent by the factory

## 2. ASSISTANT-TOOL-ERROR and ASSISTANT-TOOL-LOOP (modified)

- [x] 2.1 /accept -- red: a malformed call alone ended the run, and an endless
  one never reached the budget. A malformed call beside a valid one was
  already answered by the tool node
- [x] 2.2 /tdd -- `AnswerInvalidCalls`. Found on the way: `after_model` hooks
  run last-first, so placed after the budget it jumped back before the turn
  was counted, and an endless malformed reply looped past it (13 calls in 40
  steps). It is placed first; the test runs under a ceiling of 100, so a wrong
  order fails at once rather than hanging

## 3. ASSISTANT-CONTEXT-BUDGET

- [x] 3.1 /accept -- written after `ContextBudget`, which was wired with group
  2: not a red first. Its proof is the mutations in 5.3: no budget, `>=`, the
  prompt not counted, the arguments not counted -- each red
- [x] 3.2 /tdd -- `ContextBudget`, `call_chars`, `CONTEXT_CHARS_PER_CALL`,
  `ContextBudgetExceededError`

## 4. ASSISTANT-MODEL-CALL-BUDGET (modified)

- [x] 4.1 The step ceiling, re-measured with the real factory: 60 ends at the
  ceiling, 61 in the budget's error

## 5. ASSISTANT-UNTRUSTED-TASK-TEXT -- the story test green

- [x] 5.1 The story test green through the stand-in and a real task list
- [x] 5.2 The measurement re-run with the prompt, through `call_chars`: N = 20
  on `gpt-5.4-mini`, every run completed, at most 2 model calls, 2 tool calls,
  16,582 characters to one call. `check.sh live`: below
- [x] 5.3 Proved by mutation, ten in a full-suite run, each red, none hanging:
  no context budget; `>=`; the prompt not counted; the arguments not counted;
  invalid calls not answered; answered after the budget counts; no jump back;
  the parse error not named; no prompt; no tool-call budget
- [x] 5.4 Found by the live server tests: `ContextBudget` had only the
  synchronous hook, and the server runs graphs with `astream`. Every served
  run ended in `NotImplementedError`, and no default test ran the graph
  asynchronously. Added `awrap_model_call`, with default tests on the
  asynchronous path: the context budget at 150,000 and 150,001, and a
  malformed call. Removing the async hook turns them red.
  `bash scripts/check.sh live`: every check passed -- suite 266, live 9
  passed, the Open WebUI test among them. No key-shaped line, and no `.data/`

## 6. Verify pass 1 -- the fixes (`verify.md`, reviewed at `d941831`)

- [x] 6.1 `call_chars` counts malformed calls' raw arguments; the answer to
  one is a fixed sentence, asserted exactly; rows for AI text and raw
  arguments near the bound (1, 4, 5)
- [x] 6.2 Two malformed calls in one reply, each answered; one without an
  id left, the run not crashing (3, 6)
- [x] 6.3 ASSISTANT-OUTPUT-BUDGET: `max_tokens` 4,096 on the client
  (MODEL-OPENWEBUI-CLIENT, modified), `OutputBudget` ending a cut-off reply.
  Open WebUI honours the cap, checked on the owner's server (2). The step
  ceiling re-measured: 70 and 71
- [x] 6.4 `check_context_chars` in the domain (7); the context error not
  retried under the registry's predicate (8); the prompt's clause asserted,
  its text pinned to version 1 by a digest (9); the per-run worst case stated
  (10)
- [x] 6.5 The script: turns and proposed calls from the transcript,
  `--repeat` of at least 1, `task_tools` shared with the registry (11).
  Re-run: N = 20 on `gpt-5.4-mini`, at most 2 turns, 2 calls proposed, 16,582
  characters, all completed. An earlier run used the old script by mistake --
  20 paid calls, the same results
- [x] 6.6 Open WebUI-side tools recorded in `.env.example` (12)
- [x] 6.7 Proved by mutation, ten in a full-suite run. Nine were red at once.
  The survivor -- `OutputBudget` placed after `AnswerInvalidCalls` -- turned
  red with a row added: a call cut off mid-arguments is not handed back

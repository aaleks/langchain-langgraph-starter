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

- [ ] 0.1 The stand-in Open WebUI: a reply may be several tool calls
- [ ] 0.2 The story test, red

## 1. ASSISTANT-PROMPT

- [ ] 1.1 /accept -- red
- [ ] 1.2 /tdd

## 2. ASSISTANT-TOOL-ERROR and ASSISTANT-TOOL-LOOP (modified)

- [ ] 2.1 /accept -- red
- [ ] 2.2 /tdd

## 3. ASSISTANT-CONTEXT-BUDGET

- [ ] 3.1 /accept -- red
- [ ] 3.2 /tdd

## 4. ASSISTANT-MODEL-CALL-BUDGET (modified)

- [ ] 4.1 The step ceiling's rows at 60 and 61

## 5. ASSISTANT-UNTRUSTED-TASK-TEXT -- the story test green

- [ ] 5.1 /tdd
- [ ] 5.2 The measurement re-run with the prompt; `check.sh live`
- [ ] 5.3 Proved by mutation, each red in a full-suite run

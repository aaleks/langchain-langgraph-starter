# Sequence

- **Order** -- the ladder's build order (graphs.md):
  1. The routing policy and the budget checks, in `domain/`.
  2. The state contract.
  3. The nodes and their transitions -- the topology.
  4. The living requirements, re-proved through the factory.
  5. The budgets per run, on a thread.
  6. Registration, and the server.
- **Wiring point:** `src/starter/infrastructure/agents/factory.py`.
- **Story test:**
  `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`
  -- its scenario "Compiled by the factory" is red until the registered graph
  is the new one.

## 1. ASSISTANT-ROUTING

- [ ] 1.1 /accept -- `tests/unit/domain/test_routing.py`
- [ ] 1.2 /tdd -- `domain/agents/routing.py`; the budget checks and errors in
  `domain/agents/budgets.py`

## 2. ASSISTANT-STATE-CONTRACT

- [ ] 2.1 /accept -- `TestStateContract`
- [ ] 2.2 /tdd -- `graphs/assistant/state.py`

## 3. ASSISTANT-GRAPH-TOPOLOGY

- [ ] 3.1 /accept -- `TestTopology`, and the story test's modified scenario
- [ ] 3.2 /tdd -- `graph.py`, `nodes.py`, `routes.py`; the factory compiles
  it; `middleware.py` deleted

## 4. The living requirements, modified and carried

- [ ] 4.1 ASSISTANT-MODEL-CALL-BUDGET, ASSISTANT-TOOL-CALL-BUDGET,
  ASSISTANT-TOOL-ERROR, ASSISTANT-UNTRUSTED-TASK-TEXT: the error classes and
  the measured step count, in their tests
- [ ] 4.2 Every other assistant test green, unchanged

## 5. ASSISTANT-BUDGETS-PER-RUN

- [ ] 5.1 /accept -- `TestBudgetsPerRun`
- [ ] 5.2 /tdd -- `start_run`

## 6. Registration and the server

- [ ] 6.1 ASSISTANT-REGISTERED green; `langgraph.json` unchanged
- [ ] 6.2 Mutations of the new code, each red
- [ ] 6.3 `bash scripts/check.sh live` -- the local server and the owner's
  Open WebUI
- [ ] 6.4 Documents: CLAUDE.md, ADR 0005's status, the roadmap, the
  measurement script's import

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

- [x] 1.1 /accept -- `tests/unit/domain/test_routing.py`; red: no module
  `starter.domain.agents.routing`
- [x] 1.2 /tdd -- `domain/agents/routing.py`, 9 passed. The budget checks and
  errors in `domain/agents/budgets.py`, and the cut-off check moved there from
  the adapter: a threshold is a domain decision

## 2. ASSISTANT-STATE-CONTRACT

- [x] 2.1 /accept -- `TestStateContract`; red: no module
  `starter.infrastructure.agents.graphs`, and a caller's count unrefused
- [x] 2.2 /tdd -- `graphs/assistant/state.py`

## 3. ASSISTANT-GRAPH-TOPOLOGY

- [x] 3.1 /accept -- `TestTopology` red: the nodes were `create_agent`'s and its
  middleware's; the story test's scenario red with them
- [x] 3.2 /tdd -- `graph.py`, `nodes.py`, `routes.py`; the factory compiles
  it; `middleware.py` deleted. A test of mine read `retry_policy` as a list --
  LangGraph stores one policy -- fixed in the test

## 4. The living requirements, modified and carried

- [x] 4.1 ASSISTANT-MODEL-CALL-BUDGET, ASSISTANT-TOOL-CALL-BUDGET,
  ASSISTANT-TOOL-ERROR, ASSISTANT-UNTRUSTED-TASK-TEXT: the error classes and
  the measured step count, in their tests
- [x] 4.2 Every other assistant test green, unchanged: `check.sh`, suite 303

## 5. ASSISTANT-BUDGETS-PER-RUN

- [x] 5.1 /accept -- `TestBudgetsPerRun`; red: `KeyError: 'model_calls'` -- the
  old graph kept no count in the state
- [x] 5.2 /tdd -- `start_run`

## 6. Registration and the server

- [x] 6.1 ASSISTANT-REGISTERED green; `langgraph.json` unchanged
- [x] 6.2 Mutations of the new code, 17 in all, each red but two, found and
  closed:
  - counting malformed calls survived: the test's run ended after that turn.
    Its row is now 19 calls and 1 malformed, then 1 more -- red under the
    mutation;
  - the route's guard for a reply that is not an AI message survived: dead
    code, since only `call_model` reaches the route. Removed.

  Red: counts kept across runs; `>` for the model budget; `>=` for the tool
  budget; tool calls not counted; malformed calls always kept; a malformed
  call beside a valid one unanswered; a malformed call alone ending the run;
  an empty id kept; no retry policy; no context budget; no output budget; no
  prompt; no input schema; no step ceiling; async tools run sync
- [x] 6.3 `bash scripts/check.sh live` -- all checks passed: suite 303, live 9,
  the local server and the owner's Open WebUI included
- [x] 6.4 Documents: CLAUDE.md, ADR 0005's status, the roadmap, the
  measurement script's import

## 7. Verify pass 1 -- the fixes

- [x] 7.1 The retry waits: `RETRY_JITTER = False`, `RETRY_MAX_DELAY_SECONDS =
  60` in the domain, pinned in `TestTopology`. The default suite went from
  about 30 s to 18 s: the random waits are gone
- [x] 7.2 ASSISTANT-NO-CALL-LEFT-UNANSWERED: `start_run` answers what an
  earlier run left, in order (`unanswered_calls` in the domain)
- [x] 7.3 A reply under a repeated id is appended under a new one
- [x] 7.4 The tool budget's rule in the domain: `check_tool_calls(spent, *,
  well_formed, malformed)`; a refused call counts, a row says so
- [x] 7.5 The output budget: not stored, never retried; every budget error
  asserted not transient
- [x] 7.6 The proof gaps: every retry field compared; the budget row's AND; the
  required keys and channels pinned; no interrupt asserted
- [x] 7.7 The malformed-call and not-run sentences in `application/prompts.py`
- [x] 7.8 Documents: the route table, the decisions, the risks accepted or
  deferred, frame and design reconciled, stale text reworded
- [x] 7.9 Mutations of the fixes, each red after one survivor was closed: a
  malformed call left by a failed turn went unproved -- the budget row now
  carries one. Red: jitter on; no max interval; left calls not answered;
  answers appended at the end; a repeated id kept; refused calls free
- [x] 7.10 `check.sh live` run: suite 310 and 8 live passed. The Open WebUI test
  could not connect -- the owner's Open WebUI was not running
  (`localhost:8080` refused); in verify.md's Not checked until it is re-run

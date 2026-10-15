# Verify

- **Verdict:** pass 1: DO NOT SHIP -- three MAJOR. The most important fix: the
  retry waits (1).
- **Reviewed at:** pass 1: `a9cbde3`, the whole change (`git diff
  7243c03..a9cbde3`), committed before the lenses read it.
- **Evidence (pass 1):**
  - `bash scripts/check.sh live` at the code of `a9cbde3`: every check passed --
    suite 303, live 9, the owner's Open WebUI among them. No key-shaped line,
    and no `.data/`.
  - 17 mutations of the new code, each red once two survivors were closed
    (tasks.md 6.2).
  - Six fresh-context lenses over the diff:
    - proof (`spec-compliance`);
    - defects (`code-reviewer`);
    - placement (`architecture-guardian`): `lint-imports` 1 contract kept,
      `tests/architecture` 54 passed;
    - graph (`graph-architecture-guardian`): no violation;
    - durability (`durability-auditor`);
    - routes (`graph-eval-auditor`).

    Four of them stopped on a usage limit and were run again from the start.
    They used scratch scripts only: no `.env` read, no live test, no paid
    model call.

## Findings

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | defects, routes, proof | `RetryPolicy` keeps LangGraph's default jitter, which adds up to 1 s of random wait to every retry, `initial_delay=0` included. The old middleware added ±25% of the delay, so a delay of 0 waited 0. The waits went from about 1 s and 2 s to 1–2 s and 2–3 s, and random sleeps reached the default suite (3.3 s, then 6.4 s, in one test). The frame's "no change to the retry policy" is false, and the topology test cannot see it | `graph.py:37` | Set `jitter` and `max_interval` explicitly, as the domain's; pin them in `TestTopology` |
| 2 | MAJOR | durability, defects | A run that ends inside `run_tools` -- a tool's own exception, or `ToolCallBudgetExceededError` -- leaves the reply's calls unanswered on the thread. The next run sends them, and a real endpoint refuses every later turn. Older than this change; 4b's approval makes it likelier, since new input on a paused thread drops the pending tools too | `nodes.py:run_tools`, `start_run` | A requirement that a run starts on a thread with no call unanswered: `start_run` answers what an earlier run left |
| 3 | MAJOR | durability | `messages` grows without bound across runs. Once it passes the context budget, every run on the thread fails before calling the model, and each superstep checkpoints the whole transcript again (1 MB in 17 checkpoints after 100k-character reads). Older than this change | `state.py`, `budgets.py` | A size or retention policy for a thread -- a decision for the owner, and slice 5's "retention" |
| 4 | MINOR | proof, placement | Which calls spend the tool budget is decided in the adapter, and refused well-formed calls count though `state.py` says "executed". No scenario names it | `nodes.py:80`, `state.py:28` | State it: a well-formed call counts, run or refused; a malformed one does not. A row with refused calls |
| 5 | MINOR | proof | A budget error now runs inside `call_model`'s retry scope; only the predicate keeps it from being retried, and that is asserted for two of the three | `nodes.py:45` | Assert all three, and run the output budget under the registry's predicate |
| 6 | MINOR | proof | A cut-off reply is no longer stored in the thread -- an improvement no scenario claims | `nodes.py:51` | An AND on the cut-off scenario, with a checkpointer |
| 7 | MINOR | proof | ROUTING says "any call, well-formed or malformed", but routes on the reply as stored. It also claims the storing, proved only by TestToolError | `spec.md` ROUTING | "As stored"; the storing left to ASSISTANT-TOOL-ERROR |
| 8 | MINOR | defects, graph | The route and `run_tools` read the reply as the last message. A reply whose id repeats one in the transcript replaces it where it stands, and the run fails with `AttributeError` | `routes.py:15`, `nodes.py:79` | Store a reply with a repeated id under a new one; a scenario |
| 9 | MINOR | proof | "Compiled by the factory": of the retry policy, only `max_attempts` and `retry_on` are compared | `test_registered_assistant.py:212` | Compare every field |
| 10 | MINOR | proof | UNTRUSTED-TASK-TEXT's AND is asserted for row 1 only | `test_registered_assistant.py:322` | Assert it for the budget row |
| 11 | MINOR | proof | The scenario title "below 41" is false on this graph | `spec.md` MODEL-CALL-BUDGET | Retitle it, if the validator allows |
| 12 | MINOR | proof | "A caller cannot set a count" passes with the input schema removed: `start_run` resets the counts either way. The jsonschema assertion is the proof | `test_assistant_graph.py:128` | Say so beside it |
| 13 | MINOR | placement | The malformed-call sentence the model reads is text in an adapter, not a named constant beside the prompt | `nodes.py:125` | Move it to `application/prompts.py` |
| 14 | MINOR | placement | design.md's test plan promises unit tests of the budget checks that do not exist | `design.md`, `budgets.py` | Amend the plan: the graph tests prove them |
| 15 | MINOR | routes | No route table walks the ladder's checklist: refusal, authorisation-based denial and retrieval failure are named nowhere | `design.md` | The table, each row a requirement or an N-A with its reason |
| 16 | MINOR | routes, durability | frame.md says no thread outlives the server; design.md says one can. An old thread stopped mid-run does nothing on a continue (`next` names a node that no longer exists) | `frame.md`, `design.md` | Reconcile them; the policy for old threads: delete `.langgraph_api/` |
| 17 | MINOR | durability | The state version is written into no checkpoint, and the pin misses required keys and the compiled channels | `state.py`, `test_assistant_graph.py` | Pin `__required_keys__` and the channels now; stamp the version on checkpoints in slice 5 |
| 18 | MINOR | durability | A caller of the local server's state-update endpoint can set the counts and bypass the per-run budget (120 model calls measured) | `state.py` | Accepted, to be stated: the local server's caller is the owner, who can start any number of runs |
| 19 | MINOR | graph | `start_run` is labelled "decide"; the node names are mechanical, and become an interface with slice 5. The topology test does not assert there is no interrupt | `design.md`, `test_assistant_graph.py` | Relabel; record the names as deliberate; assert no interrupt |
| 20 | MINOR | graph, defects, proof | Stale text names the deleted middleware or `create_agent` | `capabilities.py:11`, `models.py:48`, `agents/__init__.py:4`, `docs/architecture/overview.md:43`, `test_assistant.py:667`, `tests/fakes.py:76` | Reword |

One more, a note: budget errors are raised, not audited (graph). Accepted in
design decision 5; auditing arrives with 4b and slice 6.

## Not checked

- `agent-capability-auditor`: no tool, manifest or permission changed. The
  manifest check moved with the factory, and `test_tool_manifests.py` runs
  unchanged except for the name it patches.
- `observability-auditor`, `determinism-auditor`: no logging, tracing or
  entry point changed. No test calls a real model by default (`check.sh`).

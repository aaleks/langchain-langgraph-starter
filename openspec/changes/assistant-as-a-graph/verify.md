# Verify

- **Verdict:** SHIP at `0eb6dc5` -- pass 2: no BLOCKER, no MAJOR. Its MINORs
  were fixed after it, at `601bdd4` (below). Pass 1: DO NOT SHIP -- three
  MAJOR: two fixed, one deferred by the owner in writing.
- **Reviewed at:** pass 2: `0eb6dc5`, the fix diff `a9cbde3..0eb6dc5`. Pass 1:
  `a9cbde3`, the whole change (`git diff 7243c03..a9cbde3`), committed before
  the lenses read it.
- **Evidence (pass 2):**
  - `bash scripts/check.sh live` at `7804da6` (the fixes' code): suite 310,
    and 8 of 9 live passed. The Open WebUI test could not connect: the
    owner's Open WebUI was not running (Not checked).
  - Mutations of the fixes, each red once one survivor was closed (tasks.md
    7.9). After `601bdd4`: answers matched by id anywhere, red. A dedupe of
    ids within one reply survived; it was behaviour no requirement claims,
    and was removed.
  - `bash scripts/check.sh` at `601bdd4`: all checks passed, suite 313.
  - Three fresh-context lenses over the fix diff: proof, defects and
    durability. No `.env` read, no live test, no paid model call.
- **Evidence (pass 1):**
  - `bash scripts/check.sh live` at the code of `a9cbde3`: every check passed --
    suite 303, live 9, the owner's Open WebUI among them. No key-shaped line,
    and no `.data/`.
  - 17 mutations of the new code, each red once two survivors were closed
    (tasks.md 6.2).
  - Six fresh-context lenses over the diff: proof (`spec-compliance`);
    defects (`code-reviewer`); placement (`architecture-guardian`:
    `lint-imports` 1 contract kept, `tests/architecture` 54 passed); graph
    (`graph-architecture-guardian`: no violation); durability
    (`durability-auditor`); routes (`graph-eval-auditor`). Four stopped on a
    usage limit and were run again from the start.

## Findings -- pass 1

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

### Pass 1 -- what became of each

| # | Outcome |
|---|---|
| 1 | Fixed (tasks.md 7.1): no jitter, a max delay, from the domain; 1 s then 2 s pinned after pass 2 |
| 2 | Fixed (7.2): ASSISTANT-NO-CALL-LEFT-UNANSWERED; answered by position after pass 2 |
| 3 | Deferred to slice 5 by the owner, 2026-10-14: "Defer to slice 5 (Recommended)" -- design.md Risks, roadmap slice 5 |
| 4 | Fixed (7.4): the rule in `check_tool_calls`; rows for an unknown tool and refused arguments; `state.py`'s comment |
| 5, 6 | Fixed (7.5) |
| 7, 8 | Fixed (7.3; the ROUTING statement) |
| 9, 10, 12 | Fixed (7.6) |
| 11 | Kept, with its reason in the scenario: OpenSpec refuses a modified requirement's renamed scenario (measured) |
| 13 | Fixed (7.7) |
| 14, 15, 16, 19, 20 | Fixed (7.8) |
| 17 | Pinned now (7.6); the version stamped on checkpoints deferred to slice 5 (roadmap) |
| 18 | Accepted and stated: the state-update endpoint's caller is the owner |

## Findings -- pass 2

| # | Severity | Lens | Finding | Where | Outcome |
|---|---|---|---|---|---|
| 21 | MINOR | proof, defects, durability | A call counted as answered by a tool message anywhere in the transcript: a backend reusing a call id across turns leaves it unanswered | `nodes.py:_answer_left_calls` | Fixed: answered only by the tool messages right after its reply; a row with `call_0` used twice |
| 22 | MINOR | proof | The budget row's 22 answers not checked for their text | `test_assistant_graph.py` | Fixed |
| 23 | MINOR | proof | "1 s then 2 s" claimed, not asserted | `test_assistant_graph.py` | Fixed |
| 24 | MINOR | proof | "Arguments its schema refuses" count had no row | `test_assistant.py` | Fixed: parametrised |
| 25 | MINOR | proof | A transcript sent without a checkpointer is answered too, unclaimed; a call without an id is left, unstated | `nodes.py` | Fixed: a scenario, and the statement |
| 26 | MINOR | proof | `state.py` still said "executed" | `state.py:28` | Fixed |
| 27 | MINOR | proof | tasks.md 7.10 pointed at a Not checked line verify.md lacked | `verify.md` | Fixed: below |
| 28 | MINOR | defects | A rewriting run streams the whole transcript after a `remove` marker | `nodes.py:start_run` | Stated: design.md decision 10 |
| 29 | MINOR | durability | A state edit then a continue without input goes past `start_run` | `nodes.py:start_run` | Stated: the requirement covers runs that start from input; design.md decision 10 |

Notes: a continue resumes `run_tools`, whose tools run again -- safe while
every tool reads, and a constraint on 4b's write node (design.md decision
10). `check_tool_calls` takes `malformed` to state its rule, and spends
nothing for it.

One more, a note (pass 1): budget errors are raised, not audited (graph). Accepted in
design decision 5; auditing arrives with 4b and slice 6.

## Not checked

- **The real Open WebUI test, after the fixes.** The owner's Open WebUI was
  not running on 2026-10-15 (`localhost:8080` refused, probed twice). It
  passed at the code of `a9cbde3`; the fixes since change `start_run`, the
  retry waits and the budgets' bookkeeping, each proved with fakes and the
  stand-in. To re-run: `bash scripts/check.sh live`.
- `agent-capability-auditor`: no tool, manifest or permission changed. The
  manifest check moved with the factory, and `test_tool_manifests.py` runs
  unchanged except for the name it patches.
- `observability-auditor`, `determinism-auditor`: no logging, tracing or
  entry point changed. No test calls a real model by default (`check.sh`).

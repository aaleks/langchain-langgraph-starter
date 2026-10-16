# Verify

- **Verdict:** SHIP -- after five passes; the last two found no BLOCKER and
  no MAJOR, and every earlier one is fixed or, for finding 21, accepted.
- **Pass 5:** SHIP -- no BLOCKER, no MAJOR; its MINORs fixed or accepted
  (58-61). Reviewed at `adb660a`, the pass-4 fixes, by the proof and
  defects lenses; its fixes committed after it, each row red first.
- **Pass 1:** DO NOT SHIP -- two BLOCKER, three MAJOR. The most
  important fix: a write the owner rejected was applied when two calls of a
  reply shared an id (1).
- **Pass 2:** DO NOT SHIP -- one BLOCKER, three MAJOR. The most
  important fix: a page's blind `text/plain` POST could propose and approve
  a write, since CORS limits what a page reads, never what it sends (18).
- **Pass 3:** DO NOT SHIP -- one BLOCKER, three MAJOR. The most
  important fix: the guard let every WebSocket through, and the server's
  event stream starts and approves runs over one (31).
- **Pass 4:** SHIP -- no BLOCKER, no MAJOR; its MINORs fixed
  or recorded (51-57). Every MAJOR of passes 1-3 fixed; finding 21 accepted
  under the approved design's identity line, its reach stated exactly.
- **Reviewed at:** pass 4: `6512b07`, the pass-3 fixes (`git diff
  a5a5624..6512b07`); its fixes committed after it.
- **Evidence (pass 4 fixes, run 2026-10-16):** every step of
  `scripts/check.sh` -- format, lint, architecture 54, OpenSpec 7 of 7,
  `sdd check` 0 errors (19 of 19 test files claimed), the method's selftest,
  the manifest, the suite 490 passed -- run step by step with `python -m
  pytest`, since this machine's Application Control began refusing the
  `pytest.exe` launcher that `uv run pytest` spawns; `pytest -m live`: 14 of
  14, the owner's Open WebUI answering, a page's WebSocket refused through
  `serve.sh`. Mutations: 8 of the pass-4 fixes, each red.
- **Reviewed at:** pass 1: `04dc4a2`, the whole change (`git diff
  0123b5d..04dc4a2`), committed before the lenses read it.
- **Evidence (pass 1):**
  - `bash scripts/check.sh live` at `04dc4a2`:
    - suite 391;
    - 10 of 11 live tests, the story test `TestApprovalThroughTheServer`
      among them, through `scripts/serve.sh`;
    - the Open WebUI test could not connect: the owner's Open WebUI was not
      running (Not checked).
  - 19 mutations, each red once three survivors were closed (tasks.md 10.1).
  - Four fresh-context lenses:
    - proof (`spec-compliance`);
    - defects (`code-reviewer`);
    - capabilities (`agent-capability-auditor`);
    - durability (`durability-auditor`): v1 checkpoints written by the old
      code resumed on v2.

    Scratch files, fakes and in-memory checkpointers only. No `.env` read,
    no live test, no paid model call.

## Findings -- pass 1

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | BLOCKER | capabilities, defects, durability | Two calls of one reply sharing an id -- or a write without an id -- collapse into one decision and one key: the owner rejects one and approves the other, and the rejected write is applied and recorded as approved. Then the second raises, and the thread is stuck. A read and a write sharing an id drop the write silently | `nodes.py:review_writes`, `apply_writes` | Every well-formed call of a stored reply gets an id of its own, unique in the reply |
| 2 | BLOCKER | capabilities | The local server allows cross-origin requests from any web page (LangGraph's default, `CORS_ALLOW_ORIGINS="*"`): a page in the owner's browser can read a paused run and approve it | `scripts/serve.sh` | The owner chose, 2026-10-15: "Only Agent Chat UI's localhost:3000" |
| 3 | MAJOR | proof, defects, durability | `apply_writes` commits writes one by one but stores their answers together: a failure part-way, then new input, answers an applied write "not run" -- the model is told the opposite of the list, and a re-proposal duplicates it | `nodes.py:apply_writes` | One write per step: each answer is stored with its write |
| 4 | MAJOR | durability, defects | A replay or fork with a different decision: the answer and the route follow the new decision, the store the recorded one -- "rejected, nothing changed" for an applied write; a rejection that does not end the run | `nodes.py:apply_writes`, `routes.py:after_writes` | Answer and route from the outcome the writer returns |
| 5 | MAJOR | capabilities | The owner approves `Close task 3` with nothing trusted to say which task 3 is: task text could steer the model to name the wrong one | `approvals.py:describe_write` | The task's title and status, read from the list, in the description |
| 6 | MINOR | capabilities | A title or assignee holding `"` or a line break makes the description read like other actions | `approvals.py` | Quote as JSON |
| 7 | MINOR | capabilities, defects | The schema coerces `true` and `"1"` to a task id before the domain sees them | `nodes.py:checked_write` | Strict validation |
| 8 | MINOR | capabilities | `thread:reply:call` is ambiguous when a part holds `:` | `approvals.py:write_key` | A JSON array |
| 9 | MINOR | durability | A key too long is found only after the owner approved | `nodes.py:apply_writes` | Checked with the proposal |
| 10 | MINOR | durability | A rule changed while a write waits makes the resume crash on a refusal string | `nodes.py` | A write refused on resume is answered as not proposed |
| 11 | MINOR | proof | A write manifest without a builder passes the factory and fails with `KeyError` when proposed | `capabilities.py` | Refused at compose |
| 12 | MINOR | proof | A write proposed with no checkpointer returns an interrupt nothing can resume | `nodes.py` | Refused as not proposed: no thread to pause on |
| 13 | MINOR | proof | Test gaps: NO-CALL row 4's record and status; the write tools' defaults and every direct call; the registered graph's write reaching `TASKS_DB` in the default suite; the replay re-running; the read beside a write succeeding | tests | Asserted |
| 14 | MINOR | durability | Stale text: "the key holds the step" (design.md Risks), "thread, step and call" (`domain/tasks.py`) | docs | Reworded |
| 15 | MINOR | durability | A fork that keeps a reply's id and changes its call meets the key's record and is stuck | `stores/tasks.py:replayed` | Accepted: only a state edit through the owner's own server reaches it |
| 16 | MINOR | capabilities | The record cannot tell an owner's rejection from a malformed answer, nor shows the description seen | `stores/tasks.py` | Accepted for now: the decision is `reject` either way, the effect none |
| 17 | MINOR | durability | The pause lives in the server's in-memory checkpointer: no durable approval yet | -- | Slice 5, as design.md and ADR 0009 say |

### Pass 1 -- what became of each

| # | Outcome |
|---|---|
| 1 | Fixed (tasks.md 11.1) |
| 2 | Fixed (11.4): the owner chose "Only Agent Chat UI's localhost:3000" |
| 3, 4 | Fixed (11.2) |
| 5, 6, 7, 8, 9, 11, 12 | Fixed (11.3) |
| 10 | Fixed (11.2): a scenario and a test |
| 13 | Fixed (11.5) |
| 14 | Fixed: design.md Risks, `domain/tasks.py` |
| 15, 16 | Accepted, as written |
| 17 | Slice 5 |

## Findings -- pass 2

Reviewed at `195ab87`, the fixes (`git diff 04dc4a2..195ab87`), by the four
lenses of pass 1, fresh context each; scratch files, fakes and in-memory
checkpointers only. `uv run pytest`: 411 passed.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 18 | BLOCKER | capabilities, defects, proof | Pass 1's finding 2 was half closed: CORS limits what a page may read, never what it may send. A page's `text/plain` POST is sent without a preflight, and the server parses its body as JSON whatever its type: a page can create a thread, propose a write and approve it -- or set `write_decisions` and go to `apply_writes` -- reading nothing. DNS rebinding makes it same-origin: no `Host` check | `scripts/serve.sh`, the server | The owner chose, 2026-10-15: "Request guard middleware" |
| 19 | MAJOR | proof, defects, durability | On resume `review_writes` rebuilt its list under the current rules: a write refused by then dropped out, and the owner's decisions were counted and mapped against a list they never saw -- an approval recorded as a rejection, or, with one decision for two, an approval landing on the other write | `nodes.py:review_writes` | Every waiting write asked about, one refused by then shown `Not valid: <why>` |
| 20 | MAJOR | durability | The store's commit and the step's checkpoint are two transactions: a run cancelled or killed between them keeps the write and loses its answer, and the next run answered it "not run" -- a re-proposal applied it twice. The requirement said this could not happen | `nodes.py:start_run` | `start_run` answers it with the outcome recorded under its key |
| 21 | MAJOR | capabilities | The owner's decision is tied to a position, not to the action shown: a client that edits the paused thread's state can swap the call under its id, and the owner's approval applies to a task they never saw | `nodes.py:review_writes` | The same reach as setting `write_decisions` directly: any client that can edit state can approve. The guard (18) keeps every page but Agent Chat UI's out |
| 22 | MINOR | defects, capabilities, proof | `CORS_CONFIG` from the shell, or `http.cors` in `langgraph.json`, replaces the script's origin | `scripts/serve.sh` | Unset; a `"cors"` key refused |
| 23 | MINOR | defects, proof | A thread id with no checkpointer passes "a thread to pause on", and returns an interrupt nothing can resume | `nodes.py:_proposal` | The checkpointer read from the run's config |
| 24 | MINOR | defects | A thread id that is not a string makes `write_key` raise `TypeError`, failing the turn | `approvals.py:write_key` | `str()` |
| 25 | MINOR | proof | A status from the list is shown unquoted; a file written elsewhere need not hold the schema's check | `approvals.py:describe_write` | A fixed word, `closed` |
| 26 | MINOR | capabilities | JSON quoting leaves bidi overrides, U+2028/U+2029 and C1 controls raw in a description, which a UI may draw as another line or reversed | `approvals.py:_quoted` | Escaped: categories Cc, Cf, Zl, Zp |
| 27 | MINOR | durability | The state contract called `write_decisions` the owner's decision; after the fixes it is the store's outcome class | `state.py`, ASSISTANT-STATE-CONTRACT | Reworded |
| 28 | MINOR | durability | "No v1 thread can be paused where it is read" was backed by a scratch probe only | tests | A v1 state run on, in a test |
| 29 | MINOR | proof | Parts of scenarios unasserted: the proposal rows' AND clauses; the read and write under one id still waiting; the replay rejecting then approving | tests | Asserted |
| 30 | MINOR | proof | "Nothing written" by a direct call held for any code: the list was empty | `test_tool_manifests.py` | A seeded list, unchanged |

Not findings, for the record: `review_writes` reads the list again on resume
to rebuild descriptions nobody sees then (durability); `localhost:3000` has
credentials, the owner's accepted choice (capabilities).

### Pass 2 -- what became of each

| # | Outcome |
|---|---|
| 18 | Fixed (tasks.md 12.1): `request_refusal`, `LocalRequestGuard`; live, a page's blind POST and a rebound `Host` refused with no thread created |
| 19 | Fixed (12.3) |
| 20 | Fixed (12.4) |
| 21 | Accepted under the approved design's identity line -- "no owner check yet: one owner on 127.0.0.1. Slice 5 adds ownership." Binding a decision to what was shown would not close it: a client that can edit state can set the decision itself. The guard narrows it to a process on this machine, which can write the task file directly. Recorded in design.md Risks and ADR 0009 |
| 22 | Fixed (12.2) |
| 23, 24, 25, 26 | Fixed (12.5) |
| 27 | Fixed: `state.py`, ASSISTANT-STATE-CONTRACT |
| 28, 29, 30 | Fixed (12.6) |

## Findings -- pass 3

Reviewed at `a5a5624`: the pass-2 fixes (`git diff 195ab87..a5a5624`) against
the whole change, by seven lenses, fresh context each -- proof, defects,
capabilities and durability again, and placement, graph architecture and
graph evaluation for the first time. Scratch files, fakes, temporary lists and
the server's app in-process only; no server started, no `.env` read.
`uv run pytest`: 432 passed; `tests/architecture`: 54 passed.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 31 | BLOCKER | placement, capabilities, defects | The guard passed every scope but HTTP through unchecked. `langgraph-api` 0.16 serves `/threads/{id}/stream/events` as a WebSocket by default (`FF_V2_EVENT_STREAMING`), which starts a run (`if_not_exists: create`) and resumes an interrupt; CORS never applies to a WebSocket. Measured in-process: a page at `https://evil.example` opened it, read the approval request, approved it, and the task was written | `guard.py`; `access.py` (a handshake is a GET, so "safe") | A WebSocket is never safe: refused for its `Host` and any other page's `Origin`, closed unaccepted; fail closed for any other kind |
| 32 | MAJOR | proof, defects | The media-type rule refused a POST with no body: the SDK's `runs.cancel` and `threads.copy` got 403, though the spec said the SDK is unaffected | `access.py` | The rule applies to a body sent; a page's empty POST still carries its `Origin` |
| 33 | MAJOR | proof, placement | The guard adapter ran in no default test: its header reading, its 403, its scope branch were proved only live -- which is how 31 went unseen | tests | `TestGuardInFrontOfEveryRoute`: every policy row through the adapter |
| 34 | MAJOR | graph evaluation | The async half of `run_tools`, the path the server runs, met no write in any test: dropping its refusal answers left all 432 green | `nodes.py:run_tools` | The proposal, decision and read-beside-write tests on `invoke` and `ainvoke` |
| 35 | MINOR | durability | `apply_writes` read the rules before the key's record: a continue after a lost answer and a rule change answered an applied write "not proposed" | `nodes.py:apply_writes` | The record first |
| 36 | MINOR | durability | A run cancelled while its write waits for the list's lock: the write's thread commits after the next run answered it "not run" | `nodes.py:start_run` | Narrowed in the spec ("cancelled after the list committed it"); the window recorded in design.md Risks, for slice 5 |
| 37 | MINOR | durability | `start_run` answers with the key's record without matching it to the call; a fork that edits the reply's arguments under the same ids gets another write's outcome | `nodes.py:start_run` | Accepted: only the owner's client edits state (21's reach); recorded in Risks |
| 38 | MINOR | graph evaluation | A malformed call and a write under one id: the rename that keeps the write waiting was untested | tests | A row and a test |
| 39 | MINOR | proof | `str()` on the thread id: no test | tests | `UUID(int=7)`, a row and a test |
| 40 | MINOR | proof, graph evaluation | A `Not valid` action shows the model's arguments, not "checked arguments" | spec | Stated -- "its arguments as proposed" -- and asserted |
| 41 | MINOR | proof, defects | The check that `serve.sh` refuses a `"cors"` key could not fail: a comment holds the word | `test_local_server.py` | The refusal's own line |
| 42 | MINOR | proof, graph evaluation | The live test's docstring missed the amended sentence; a malformed call's answer would fail it; the measurement names no model | `test_openwebui_live.py` | Docstring and malformed calls fixed; the measurement: prompt v2, N = 3, the owner's configured model -- its id is in `.env`, which no agent reads |
| 43 | MINOR | placement | The one browser origin was held in the script and the domain, each pinned alone | tests | Held equal by one test |
| 44 | MINOR | durability | Two stale lines in `state.py` | `state.py` | Reworded |
| 45 | MINOR | placement, graph architecture | Small decisions sit in nodes: which tools need approval, a proposal's eligibility, the approval vocabulary, a second "unanswered" rule in `waiting_writes` | `graph.py`, `nodes.py` | Accepted as recorded: a refactor with no behaviour change, a bounded change of its own |
| 46 | MINOR | placement, graph architecture | `start_run` and `review_writes` hold the writer, though they only read | `nodes.py` | Slice 5, recorded in Risks |
| 47 | MINOR | placement, graph architecture | `langgraph.json` names `http.app`, beside the rule "only registry exports"; no architecture check reads non-graph keys; `starlette` is not a declared dependency | `langgraph.json`, rules | ADR 0009 records the exception; a test pins the `http` block whole; `starlette` is the dev-only server's (design.md). The rule's wording: upstream, in `docs/learnings.md` |
| 48 | MINOR | capabilities | Server surfaces no requirement asks for are on: MCP, A2A, the store, crons | `langgraph.json` | Slice 6, operations: each measured against what Agent Chat UI and the SDK use, then turned off |
| 49 | MINOR | graph evaluation, graph architecture | Unnamed: a resume with nothing paused; the store failing in `start_run` or `review_writes`; the unit-tier test plan not followed; `CONFIG_KEY_CHECKPOINTER` | design.md | Named in design.md |
| 50 | MINOR | graph evaluation | No live run takes the owner's model through an approval; no row pins that extra keys in a write's arguments are ignored (probed: they are) | tests | Not done here: a live approval with a real model is slice 5's story test |

Not findings, for the record: the guard runs before CORS and every route on
the installed server (two lenses read `server.py`, one printed the order);
pass-2 findings 19, 20, 27 and 28 are closed (durability); each write is
still applied at most once under pause, resume, replay, fork, race and cancel
(durability). The capabilities lens's in-process probe left a thread titled
"Planted by evil.example" in the gitignored `.langgraph_api/`; no tracked
file changed.

### Pass 3 -- what became of each

| # | Outcome |
|---|---|
| 31 | Fixed (tasks.md 13.1); the in-process tests red first, the live socket rows through `serve.sh` |
| 32 | Fixed (13.2); live, red on the old guard |
| 33 | Fixed (13.3) |
| 34 | Fixed (13.4); the lens's mutant now red |
| 35 | Fixed (13.5), red first |
| 36 | Narrowed and recorded; slice 5 |
| 37 | Accepted, recorded |
| 38, 39, 40, 41, 42, 43, 44 | Fixed (13.6) |
| 45 | Accepted as recorded |
| 46 | Slice 5 |
| 47 | Recorded: ADR 0009, design.md; upstream |
| 48 | Slice 6 |
| 49 | Named in design.md |
| 50 | Slice 5 |

## Findings -- pass 4

Reviewed at `6512b07`, the pass-3 fixes, by the proof, defects and
capabilities lenses, fresh context each; the server's app in-process, its
WebSocket handshakes on a real uvicorn around the guard; no server of the
project's started, no `.env` read. `uv run pytest`: 478 passed.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 51 | MINOR | proof, defects, capabilities | Fix 35 read the key's record before the writer, so a fork that edits a decided call under the same ids was answered "applied" -- the store's "the key already records another write" never reached; design.md said the opposite | `nodes.py:apply_writes` | The writer decides again, refusing it (TASKS-WRITE-ONCE); the record is read directly only when the rules now refuse the call |
| 52 | MINOR | capabilities | The development server mounts `POST /deploy`, which runs a LangSmith deployment from the repository, and `POST /internal/truncate`, which wipes every thread -- reachable by Agent Chat UI's origin and any local client, unseen by a deny rule on a command's text | `langgraph_runtime_inmem/routes.py` | Refused by the guard: `/deploy`, `/deploy/...`, `/internal/...` |
| 53 | MINOR | capabilities | Finding 21's acceptance named "a process that can write the task file"; the reach is any client that is not a browser and can reach the port | ADR 0009, design.md | Reworded; slice 5 in the roadmap |
| 54 | MINOR | proof, defects | The guard's test gave a WebSocket scope a `method`; a real one has none, so `scope["method"]` would have answered every handshake 500 unseen | `test_request_guard.py` | Built as the server builds it |
| 55 | MINOR | proof | No `PUT` or `PATCH` row; the tool-call budget unproved on `ainvoke`; an approval with more than its type had a test and no scenario row; the `Not valid` scenario's values were not its test's | tests, spec | Rows added; the budget on both paths |
| 56 | MINOR | proof | The deferrals of 36, 46, 47, 48 and 50 lived only in this change's files, which archive puts away | `docs/roadmap.md`, `docs/learnings.md` | In the roadmap's slices 5 and 6; the upstream note |
| 57 | MINOR | defects | `Content-Length: 00` counts as a body, refusing a non-JSON POST no client sends | `guard.py` | Accepted: it refuses, never lets through |

Not findings, for the record: the WebSocket fix holds on the installed server
-- a page's handshake 403, Agent Chat UI's and the SDK's 101, on a real
uvicorn as in-process (capabilities, defects); no page can write or read a
paused run but from `http://localhost:3000` (capabilities); 31-44 closed as
stated, every docstring matches its statement (proof).

### Pass 4 -- what became of each

| # | Outcome |
|---|---|
| 51 | Fixed (tasks.md 14.1), the fork test red first |
| 52 | Fixed (14.2), rows red first |
| 53, 56 | Fixed (14.4) |
| 54, 55 | Fixed (14.3) -- 55's `PUT` row only in pass 5 (60) |
| 57 | Accepted |

## Findings -- pass 5

Reviewed at `adb660a`: the pass-4 fixes (`git diff 6512b07..adb660a`), by the
proof and defects lenses; the server's app in-process with its routes stubbed,
no deployment run, no `.env` read. `python -m pytest`: 490 passed; their 8
mutations of the pass-4 fixes each red.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 58 | MINOR | defects | Under a mount prefix (`MOUNT_PREFIX`, or `mount_prefix` in `langgraph.json`), the guard saw `/api/deploy` while the router matched `/deploy`: the refusal was bypassed. Latent: nothing sets a prefix | `guard.py` | The route's path: the prefix stripped as Starlette strips it |
| 59 | MINOR | defects | A fork that edits a decided call to arguments the rules refuse is answered with the key's recorded outcome | `nodes.py:apply_writes` | Accepted: design.md Risks says that branch matches no record to the call; only a client that can edit state reaches it (21, 37) |
| 60 | MINOR | proof | `PUT` is in the statement with no row; row 55 said it was added | tests | A `PUT` row |
| 61 | MINOR | proof | Two sentences kept pass 3's order of `apply_writes`; the statement said `/deploy` where the code refuses `/deploy/...` too; two docstrings left the route rule out | spec, design.md, docstrings | Reworded |

### Pass 5 -- what became of each

| # | Outcome |
|---|---|
| 58 | Fixed (tasks.md 15.1), red first |
| 59 | Accepted |
| 60, 61 | Fixed (15.2) |

## Not checked

- **Placement, graph architecture and routes** were held in passes 1 and 2,
  while the fixes reshaped `apply_writes` and the topology; they ran in pass 3.
- **The real Open WebUI test** could not run in pass 1 -- the owner's Open
  WebUI was down on 2026-10-15 -- and ran from pass 2 on, once it was up.
- **A browser.** No browser was driven: the guard's rows are sent as a
  browser sends them, by the in-process and the live tests.

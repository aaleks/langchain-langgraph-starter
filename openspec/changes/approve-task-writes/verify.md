# Verify

- **Verdict:** pass 1: DO NOT SHIP -- two BLOCKER, three MAJOR. The most
  important fix: a write the owner rejected was applied when two calls of a
  reply shared an id (1).
- **Verdict:** pass 2: DO NOT SHIP -- one BLOCKER, three MAJOR. The most
  important fix: a page's blind `text/plain` POST could propose and approve
  a write, since CORS limits what a page reads, never what it sends (18).
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

## Not checked

- **Placement, graph architecture and routes** (`architecture-guardian`,
  `graph-architecture-guardian`, `graph-eval-auditor`): held for pass 2, since
  pass 1's fixes reshape `apply_writes` and the topology.
- **The real Open WebUI test:** the owner's Open WebUI was not running on
  2026-10-15.

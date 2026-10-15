# Verify

- **Verdict:** pass 1: DO NOT SHIP -- two BLOCKER, three MAJOR. The most
  important fix: a write the owner rejected was applied when two calls of a
  reply shared an id (1).
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

## Not checked

- **Placement, graph architecture and routes** (`architecture-guardian`,
  `graph-architecture-guardian`, `graph-eval-auditor`): held for pass 2, since
  pass 1's fixes reshape `apply_writes` and the topology.
- **The real Open WebUI test:** the owner's Open WebUI was not running on
  2026-10-15.

# Verify

- **Verdict:** DO NOT SHIP -- pass 2 found no BLOCKER and no MAJOR; its fixes,
  one wording of code among them, go to pass 3.
- **Pass 2:** no BLOCKER, no MAJOR; MINORs 21-34 fixed or recorded. Reviewed at
  `a365256`, the pass-1 fixes (`git diff 5a49478..a365256`), by the proof,
  defects and durability lenses: strict reads re-checked over 94 rows of real
  state with nothing blocked, a full pause, approve and copy cycle behind the
  server's own wrapper; 18 mutants, 7 surviving -- each now red.
- **Evidence (pass 2's fixes, run now):** `bash scripts/check.sh`; the live
  local-server tests through `serve.sh`, 3 of 3 for durability; the real-model
  test refused on the owner's expired key ("Your API key has expired"), not
  this change.
- **Pass 1:** DO NOT SHIP -- no BLOCKER, seven MAJOR. The most important fix: a
  checkpoint file could name any importable callable, called on load (2).
- **Reviewed at:** pass 1: `5a49478`, the whole change (`git diff
  4dfb9de..5a49478`), by five lenses, fresh context each -- proof, defects,
  placement, durability, graph architecture; fakes, temporary files, the
  server's checkpointer wrapper in-process; no server started, no `.env` read.
- **Evidence (pass 1):** `uv run python -m pytest`: 512 passed; architecture
  54; the live local-server tests, the story test among them: 16 passed.

## Findings -- pass 1

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | placement, graph architecture, proof, durability | The hook the server loads, `durable_checkpointer`, ran in no default test: renamed, broken, or opening the default file instead of `CHECKPOINTS_DB`, the suite stayed green | `checkpointers.py`; tests | Handed settings, loaded by the path `langgraph.json` names, in a default test |
| 2 | MAJOR | durability | Deserialization was not strict: a msgpack value in the file naming `os.mkdir` was called on load (measured) | `checkpointers.py` | `JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)`, in code |
| 3 | MAJOR | defects, durability | A copy re-stamped every checkpoint with this code's version through `aput`: a newer thread, copied, resumed under older code | `checkpointers.py`; the server's copy fallback | `acopy_thread`: refuses a thread holding a refused checkpoint, copies each stamp as it is |
| 4 | MAJOR | proof, graph architecture, durability | "None or an older one SHALL be loaded" was proved on the pure function only | tests | A v1 and an unstamped pause resumed on the saver |
| 5 | MAJOR | proof | A refusal inside the first node would pass the test, leaving checkpoints stamped 2 over a v3 thread | tests | The file's rows asserted unchanged |
| 6 | MAJOR | proof, defects, durability | "Killed, not re-registered: not found" asserted a race: the server's records flush on a 10-second clock | spec, live test | Found or not; the list unchanged |
| 7 | MAJOR | durability, graph architecture | Encryption at rest and redaction neither decided nor deferred | design.md, ADR 0010 | The owner chose, 2026-10-16: "Record: no encryption yet (Recommended)" |
| 8 | MINOR | proof | The graceful stop was not asserted graceful; the file `CHECKPOINTS_DB` names never checked | live test | Both asserted |
| 9 | MINOR | durability | `CHECKPOINTS_DB` could name the task list: the saver adds tables and switches it to WAL | `config/settings.py` | Refused, naming both settings |
| 10 | MINOR | defects | SQLite's `-wal` and `-shm` beside a checkpoint file outside `.data/` were not ignored | `.gitignore` | Ignored |
| 11 | MINOR | proof | The suite did not isolate `CHECKPOINTS_DB` as it does `TASKS_DB` | `tests/conftest.py` | Isolated |
| 12 | MINOR | proof, durability | The refusal also blocks reading a thread's state; history is not refused: unstated | spec | Stated |
| 13 | MINOR | graph architecture | Nothing pinned that the registered graph carries no checkpointer | tests | Asserted |
| 14 | MINOR | defects, durability | The SQLite saver lacks `adelete_for_runs` and `aprune`: deleting a run answers 500, a rollback leaves checkpoints, history is not pruned | the server's wrapper | Recorded; 5c |
| 15 | MINOR | durability | A thread copied while a write waits is applied twice if approved on both: the key holds the thread | `approvals.py:write_key` | Recorded; 5b decides who may copy |
| 16 | MINOR | durability | After a kill between a write's commit and its checkpoint, the owner is asked again about a write already applied | `nodes.py:review_writes` | Recorded; 5c. Applied once either way |
| 17 | MINOR | defects, durability | A thread paused before this change, approved, runs from its start on an empty transcript | migration | Recorded in design.md and ADR 0010; refusing it is 5c's |
| 18 | MINOR | placement, graph architecture | One server-wide saver stamps every thread with the assistant's version | `checkpointers.py` | Recorded: a second graph needs its own |
| 19 | MINOR | placement | The method's rules still call `langgraph.json` registry-only and the local server in-memory; `docs/architecture/overview.md` too | rules, docs | `overview.md` fixed; the rules upstream, in `docs/learnings.md` |
| 20 | MINOR | proof | The refusal's unit rows match on a substring | tests | Accepted: the requirement asks that both versions be named |

### Pass 1 -- what became of each

| # | Outcome |
|---|---|
| 1 | Fixed (tasks.md 7.3), red first |
| 2 | Fixed (7.1), red first |
| 3 | Fixed (7.2), red first |
| 4, 5 | Fixed (7.4) |
| 6 | Fixed (7.6): the spec restated |
| 7 | Decided by the owner, recorded (7.7) |
| 8 | Fixed (7.6) |
| 9 | Fixed (7.5), red first |
| 10, 11 | Fixed (7.7) |
| 12, 13 | Fixed: stated, asserted |
| 14, 15, 16, 17 | Recorded in design.md Risks and the roadmap's 5b and 5c |
| 18 | Recorded |
| 19 | Fixed for `overview.md`; the method's rules upstream |
| 20 | Accepted |

Mutations of the fixes: 7, each red.

## Findings -- pass 2

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 21 | MINOR | proof | A copy's refusal proved on an all-newer thread only: checking the latest checkpoint, or each as copied, survived | tests | A thread `3`, then none: refused, nothing under `t2` |
| 22 | MINOR | proof | The copy's fidelity -- pending writes, parents, the copy's thread id -- unclaimed and unchecked: without its writes, a copied pause lost its interrupt | spec, tests | Stated; a paused thread copied asks the owner |
| 23 | MINOR | proof, durability | The hook's no-argument path, the server's, ran in no default test | tests | Called with no argument, `CHECKPOINTS_DB` in the environment |
| 24 | MINOR | proof | "Its history is listed as stored" had no assertion | tests | Listed by the checkpointer itself |
| 25 | MINOR | proof | The kill counter-example could not fail | spec, live test | An approval before re-registering: not found, or applied once |
| 26 | MINOR | proof | A shell exporting `LANGGRAPH_STRICT_MSGPACK` would make the strict test unable to fail | `tests/conftest.py` | Removed from the suite's environment |
| 27 | MINOR | proof | An empty `CHECKPOINTS_DB` refused with a message saying it "names" the task list | `config/settings.py` | Worded as it is; a row, red first |
| 28 | MINOR | proof | `serve.sh` still called the server in-memory | `scripts/serve.sh` | Reworded |
| 29 | MINOR | proof | The method's rules deferred with no date | `docs/learnings.md` | Due by 2026-10-31 |
| 30 | MINOR | defects, durability | A copy refused by the stamp leaves the server's new thread record, idle and empty | the server | Stated; recorded; 5c |
| 31 | MINOR | durability | Request headers -- every `x-*`, `user-agent` -- are copied into each checkpoint's metadata | the server | Recorded: 5b's token must not travel in one |
| 32 | MINOR | durability | Deferral 15 placed in 5b, which cannot close it for the owner | roadmap | Accepted for the owner; who else may copy is 5b's |
| 33 | MINOR | defects | A Windows alias of the task list (`tasks.sqlite3.`) passes the refusal until the file exists | `config/settings.py` | Accepted: it needs a typo |
| 34 | MINOR | proof | verify.md recorded no evidence after the pass-1 fixes | verify.md | Recorded above |

## Not checked

- **Capabilities and graph evaluation:** no tool, prompt or route changed.
- **A browser:** none driven.

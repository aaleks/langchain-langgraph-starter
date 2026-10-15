# Verify

- **Verdict:** pass 1: DO NOT SHIP -- one MAJOR. The most important fix: prove
  a rejection under a key already recorded (1).
- **Reviewed at:** pass 1: `c56bb1e`, the whole change (`git diff
  bf8fd62..c56bb1e`), committed before the lenses read it.
- **Evidence (pass 1):**
  - `bash scripts/check.sh live` at `c56bb1e`: suite 346, and 8 of 9 live
    passed, the local server among them, opening the list at version 2. The
    Open WebUI test could not connect: the owner's Open WebUI was not running
    (Not checked).
  - 16 mutations of the new code, each red once one survivor was closed
    (tasks.md 6.1).
  - Three fresh-context lenses over the diff:
    - proof (`spec-compliance`): `sdd check` OK; 47 passed in the changed
      files;
    - defects (`code-reviewer`): 16 concurrent writers on one key, 8 racing
      migrations, a disk filling mid-write -- each atomic;
    - placement (`architecture-guardian`): `tests/architecture` 54 passed,
      `lint-imports` 1 contract kept.

    Scratch files only; no `.env` read, no live test.

## Findings -- pass 1

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | proof | TASKS-WRITE-ONCE says applying "or rejecting" under a recorded key returns the recorded outcome, but no test rejects under a key already recorded. A lookup run only for approvals stays green, and a second rejection would then raise `IntegrityError` -- the path 4b2's approval takes | `test_task_writes.py:TestWriteOnce` | Rows: applied then rejected; rejected twice; another write rejected under a recorded key -- `ValueError` |
| 2 | MINOR | placement | Which tasks a write may change -- open ones -- and the applied/refused choice are decided by SQL text and a row count in the adapter | `stores/tasks.py:_apply` | A domain function on the task's status; the `AND status = 'open'` guard kept as a safety net |
| 3 | MINOR | placement | The replay precedence -- a recorded outcome wins over the decision presented, a different write under the key is refused -- is adapter logic | `stores/tasks.py:_recorded`, `_decide` | A domain function on the recorded write |
| 4 | MINOR | placement | Tool builders receive the whole `TaskStore`, which now hands out a writer. Nothing enforces "a tool never holds a writer" | `tools/*.py` | Deferred to 4b2, which rewires the tools: they will be given a reader, not the store |
| 5 | MINOR | defects | A task id above SQLite's integer range passes the domain and fails in the store with `OverflowError` | `domain/tasks.py:_checked_id` | An upper bound, `TASK_ID_MAX`; a row |
| 6 | MINOR | defects | An unconditional `ROLLBACK` after SQLite has rolled back itself (disk full) replaces the real error with "no transaction is active" | `stores/tasks.py:_decide`, `_create` | Roll back only when a transaction is active |
| 7 | MINOR | proof | TASKS-WRITE-VALUES: the id rule has no row for `task_reassignment`, nor for a value that is not an integer | `test_task_writes.py` (unit) | Rows: `task_reassignment(0, "ana")`, `task_closing("7")` |
| 8 | MINOR | proof | TASKS-AUDIT's counter-example does not show the failure came after the insert | `test_task_writes.py:TestAudit` | Assert the task is there when the record fails |
| 9 | MINOR | proof | The migration's "same 2 tasks" compares three columns of tasks with default values | `test_task_store.py` | Tasks with an assignee and notes; every column compared |
| 10 | MINOR | proof | The audit table's arguments column spells JSON text; the test compares objects -- the spec's wording is the wrong side | `spec.md` TASKS-AUDIT | "a JSON object equal to" |
| 11 | MINOR | proof | A writer on a missing or unmigrated file creates it, then fails with "no such table" -- unclaimed | `stores/tasks.py:TaskWriter` | Connect with `mode=rw`; a sentence and a row |
| 12 | MINOR | proof | The owner's `starter tasks add` is not audited: decided in ADR 0008, held by no requirement | `spec.md` TASKS-AUDIT | A sentence and a row |
| 13 | MINOR | placement | `Field` widened to `task_id` lets `readable(x, "task_id")` type-check and raise `KeyError`; the decision values `approve`/`reject` are bare strings in the adapter | `domain/tasks.py` | A narrower field type for the limits; a `Decision` literal |

### Pass 1 -- what became of each

| # | Outcome |
|---|---|
| 1 | Fixed: rows for applied then rejected, rejected twice, and another write rejected under a recorded key; the tests parametrised over apply and reject |
| 2, 3 | Fixed: `write_refusal` decides from the status, `replayed` from the record -- both in the domain |
| 4 | Deferred to 4b2, recorded in design.md decision 7 |
| 5 | Fixed: `TASK_ID_MAX`, a row |
| 6 | Fixed: rolled back only when open; a scenario and a test with a full disk -- the disk's own error propagates |
| 7, 8, 9, 10, 11, 12 | Fixed |
| 13 | Fixed: `TextField` for the limits, `Decision` for the decisions |

Notes, no finding: the key's bound and the refusal texts are proved through
the store, not at unit level (placement) -- the store is what the
requirements describe.

## Not checked

- **The real Open WebUI test.** The owner's Open WebUI was not running on
  2026-10-15. This change does not touch the model path; the local server's
  live tests ran.

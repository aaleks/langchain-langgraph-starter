# Design

Why: frame.md. What: the delta specs. This is how.

## Context

The store (`infrastructure/stores/tasks.py`, ADR 0006):
- opens the list and adds the owner's tasks;
- hands tools a reader that refuses a write.

Schema version 1 already has a `status` column, so closing a task needs no
migration. Auditing does: a table at version 2.

## Decisions

1. **The writes are domain values.**
   - `CreateTask`, `CloseTask` and `ReassignTask` are frozen dataclasses in
     `domain/tasks.py`, built only by `task_creation`, `task_closing` and
     `task_reassignment`, which check every value (TASKS-WRITE-VALUES).
   - A creation reuses `new_task`. An assignee is checked by the same rule as
     the owner's, factored out of `new_task`.
   - Each write's action name and JSON arguments, for the audit, are domain
     functions: `write_action` and `write_arguments`.
2. **The store's `writer()` returns a `TaskWriter`**, with `apply(write,
   key)` and `reject(write, key)`. Each opens its own connection and runs
   one `BEGIN IMMEDIATE` transaction:
   1. Look the key up in `task_writes`.
      - Recorded, for the same action and arguments: return that outcome,
        and write nothing.
      - Recorded for a different write: `ValueError`.
   2. Apply the effect (`apply` only):
      - an `INSERT` for a creation;
      - an `UPDATE ... WHERE id = ? AND status = 'open'` for a closing or
        a reassignment;
      - when no row is updated, read the task's status to name the
        refusal -- `no task 7` or `task 7 is closed`, decided by the
        domain's `write_refusal`.
   3. Insert the audit row.
   4. Commit. Any failure rolls the whole transaction back.
3. **The key is the caller's.** It is checked for 1 to `WRITE_KEY_MAX` (300)
   characters by the domain's `check_write_key`, and held there by the
   schema. 4b2 builds it from the thread, the step and the call. The store
   only promises that one key is one write, applied once.
4. **The audit table** -- `task_writes`, schema version 2:

   ```sql
   CREATE TABLE task_writes (
     id          INTEGER PRIMARY KEY AUTOINCREMENT,
     write_key   TEXT NOT NULL UNIQUE CHECK (length(write_key) BETWEEN 1 AND 300),
     action      TEXT NOT NULL CHECK (action IN ('create', 'close', 'reassign')),
     arguments   TEXT NOT NULL,
     decision    TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
     outcome     TEXT NOT NULL CHECK (outcome IN ('applied', 'refused', 'rejected')),
     task_id     INTEGER,
     reason      TEXT NOT NULL DEFAULT '',
     recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
   )
   ```

   - `arguments` is `json.dumps(..., ensure_ascii=False, sort_keys=False)`
     of the write's own fields. A repeat is compared on the action and those
     fields, never on the JSON text.
   - The time is SQLite's, at insert, so no clock passes through the domain.
5. **Migration, forward only, in one transaction.** `open()`:
   - a version-2 list is used as it is, the file untouched;
   - a version-1 list (version 1, with `tasks`) gets `task_writes` and
     version 2;
   - a blank file gets both tables and version 2;
   - anything else is refused, as before.

   It is the same `BEGIN IMMEDIATE` transaction as creation, which looks at
   the file again inside it. A version-2 list opened by the previous version
   of this project is refused there, as ADR 0006 already says of a newer
   version.
6. **The reader is unchanged.** It reads `tasks` only, and its authorizer
   still refuses every write. The tools never hold a writer; 4b2's approval
   node will.

## Orchestration design

N-A: no graph changes.

## Risks

- **[A key reused across threads]** -> 4b2's key starts with the thread id,
  which LangGraph's server makes a UUID. A reused key with different content
  is refused, never applied.
- **[The migration meets a list another process has open]** -> `BEGIN
  IMMEDIATE` waits `TASK_STORE_TIMEOUT_SECONDS`, then fails with the store's
  error. Nothing is half-migrated.
- **[The audit grows]** -> one row per decision on a proposed write, a few
  hundred bytes each. A person cannot approve fast enough to make that
  matter. Retention is slice 5's, with the threads.

## Migration and rollback

**Every owner's list moves to version 2** when this version first opens it.
The tasks are unchanged, and an empty `task_writes` table is added.

**Rollback:** revert the merge. A version-2 list is then refused by the old
code, naming its version. To use it with the old code:
`DROP TABLE task_writes; PRAGMA user_version = 1;` in any SQLite tool.
Nothing in `tasks` changes.

# Sequence

- **Order:**
  1. The write values, in `domain/`.
  2. Schema version 2 and its migration.
  3. The writes.
  4. Once per key.
  5. The audit.
- **Wiring point:** `src/starter/infrastructure/stores/tasks.py` (`TaskStore.writer`).
- **Story test:** none. Nothing a user reaches changes until 4b2, whose
  story test drives an approved write through the local server. Each
  requirement's own test is the store's interface.

## 1. TASKS-WRITE-VALUES

- [x] 1.1 /accept -- `tests/unit/domain/test_task_writes.py`; red: the names did
  not exist
- [x] 1.2 /tdd -- `CreateTask`, `CloseTask`, `ReassignTask` and their builders
  in `domain/tasks.py`

## 2. TASKS-SCHEMA (modified), TASKS-ADD and ASSISTANT-REGISTERED (a row each)

- [x] 2.1 /accept -- the schema tests at version 2; the migration; version 3
  refused. Red: 8 failed -- the store created and kept version 1
- [x] 2.2 /tdd -- `open()` migrates

## 3. TASKS-WRITES

- [x] 3.1 /accept -- `tests/integration/infrastructure/test_task_writes.py::TestTaskWrites`
- [x] 3.2 /tdd -- `TaskWriter.apply`. Groups 3 to 5 share one test file,
  written whole before the writer existed; red: its imports failed

## 4. TASKS-WRITE-ONCE

- [x] 4.1 /accept -- `TestWriteOnce`
- [x] 4.2 /tdd -- the key's lookup, `reject`

## 5. TASKS-AUDIT

- [x] 5.1 /accept -- `TestAudit`
- [x] 5.2 /tdd -- the record, in the effect's transaction

## 6. Close

- [x] 6.1 Mutations of the new code, 16, each red once one survivor was
  closed: a version-2 file without `task_writes` taken for a list -- the
  schema's counter-example now has that row
- [x] 6.2 `bash scripts/check.sh live`: suite 346, 8 of 9 live passed -- the local
  server among them, opening the list at version 2. The Open WebUI test could
  not connect: the owner's Open WebUI was not running (`localhost:8080`
  refused); in verify.md's Not checked
- [x] 6.3 Documents: ADR 0006's status, the roadmap

## 7. Verify pass 1 -- the fixes

- [x] 7.1 A rejection under a recorded key: three rows, the tests over apply
  and reject
- [x] 7.2 The domain decides which task may change (`write_refusal`) and what
  a recorded key answers (`replayed`)
- [x] 7.3 `TASK_ID_MAX`; a writer that never creates a file; rolled back only
  when open, proved with a full disk; the owner's add not recorded; the
  migration compared on every column
- [x] 7.4 Mutations: 20, each red, the six new ones among them -- the lookup
  on approvals only, an unconditional rollback, a writer creating files, no
  upper bound, the reassignment's id unchecked, the open status not decided

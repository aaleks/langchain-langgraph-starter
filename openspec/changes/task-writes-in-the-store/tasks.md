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

- [ ] 1.1 /accept -- `tests/unit/domain/test_task_writes.py`
- [ ] 1.2 /tdd -- `CreateTask`, `CloseTask`, `ReassignTask` and their builders
  in `domain/tasks.py`

## 2. TASKS-SCHEMA (modified), TASKS-ADD and ASSISTANT-REGISTERED (a row each)

- [ ] 2.1 /accept -- the schema tests at version 2; the migration; version 3
  refused
- [ ] 2.2 /tdd -- `open()` migrates

## 3. TASKS-WRITES

- [ ] 3.1 /accept -- `tests/integration/infrastructure/test_task_writes.py::TestTaskWrites`
- [ ] 3.2 /tdd -- `TaskWriter.apply`

## 4. TASKS-WRITE-ONCE

- [ ] 4.1 /accept -- `TestWriteOnce`
- [ ] 4.2 /tdd -- the key's lookup, `reject`

## 5. TASKS-AUDIT

- [ ] 5.1 /accept -- `TestAudit`
- [ ] 5.2 /tdd -- the record, in the effect's transaction

## 6. Close

- [ ] 6.1 Mutations of the new code, each red
- [ ] 6.2 `bash scripts/check.sh live`
- [ ] 6.3 Documents: ADR 0006's status, the roadmap

# 8. A write to the task list is applied once under its key, and audited in the same file

Date: 2026-10-15
Status: Accepted. Extends ADR 0006 (the task list) to schema version 2.

## Context

The assistant will propose creating, closing and reassigning tasks, each run
only after the owner approves (`docs/roadmap.md`, slice 4b). The project's
rules ask two things of a write (`.claude/rules/langgraph/graphs.md`,
"write"):
- **It must not repeat its effect** when a run is replayed after a crash, or
  an approval arrives twice. That takes "an idempotency key from thread and
  step, or a guard".
- **It must be audited.**

Two things settled here are expensive to reverse:
- the schema every owner's list migrates to;
- the store's write interface.

## Decision

- **Schema version 2** adds one table, `task_writes`. Each row records one
  decision on one proposed write:
  - its key, `UNIQUE`;
  - the action and its arguments;
  - `approve` or `reject`;
  - the outcome: `applied`, `refused` or `rejected`;
  - the task's id, a reason, and when it was recorded.

  A version-1 list is migrated forward in one transaction when opened.
- **One transaction holds the effect and its record.** Neither can exist
  without the other.
- **A key is one write.**
  - A key already recorded returns the recorded outcome and changes nothing.
  - A key recorded for a different write is refused.
  - The caller makes the key: in slice 4b2, thread, reply and call (ADR
    0009) -- the reply naming the step's proposal, stable on replay.
- **Only the assistant's proposed writes are audited.** The owner's own
  `starter tasks add` is not: the audit is a record of what the owner
  decided about the assistant's proposals.
- **The writes are domain values**, checked by the rules that already check
  the owner's input.

## Consequences

**Good:**
- A replayed or doubled approval cannot change the list twice.
- Every proposal the owner decided on can be read back, with its outcome,
  using any SQLite tool.
- No dependency was added.

**Costly:**
- The file grows by one row per decision.
- The migration is hand-written SQL.
- A version-2 list cannot be opened by an older version of this project
  without the two-line downgrade in the change's design.md.

**Reversal:** drop `task_writes` and set version 1. The tasks are untouched.

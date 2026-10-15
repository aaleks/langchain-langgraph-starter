# Frame

## Outcome

**Who benefits:** the owner. The assistant's writes will each be approved
before they run (4b2). This change makes each one safe to run:
- **once** -- a replay after a crash, or an approval sent twice, changes
  the list once;
- **traceably** -- every decision on a proposed write, applied, refused or
  rejected, is a row in the same file, written with the effect or not at
  all.

**The observable signal:**
- a list opened by this version is at schema version 2, with its tasks
  unchanged;
- each write's outcome is one of `applied`, `refused` (with its reason) or
  `rejected`;
- a key used twice changes the list once;
- the audit table holds one row per key.

**Non-goals:**
- **Nothing the assistant or the owner can call yet.** No tool, no approval,
  no CLI command: 4b2.
- **The owner's `starter tasks add` is not audited.** The audit records
  decisions on what the assistant proposes; the owner's own command is
  theirs.
- **No deletion.** The product writes create, close and reassign
  (`docs/roadmap.md`).

## Existing options considered

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| the store as it is: stdlib `sqlite3` (ADR 0006) | the standard library | a transaction that writes the effect and its audit row together; a `UNIQUE` key that makes a repeat a no-op | about a hundred lines: three writes, the key check, the migration |
| an idempotency or audit library (`django-idempotency-key`, SQLAlchemy-Continuum) | not checked in depth: each assumes a framework this project does not have (Django, SQLAlchemy) | keys, or row history | adopting a framework for one table; the owner chose plain `sqlite3` for the store on 2026-10-13 |
| LangGraph's own task cache or durable execution | in the installed `langgraph` 1.2.14 | skips a node that already finished | not across a crash inside the node, nor in a store outside the graph -- the rules ask for a key the write itself checks (`.claude/rules/langgraph/graphs.md`, "write") |

**Decision:** build on the store already chosen. One transaction holds the
effect and its audit row, and a `UNIQUE` key turns a repeat into the
recorded outcome. Decided by the agent under the owner's standing
delegation, since it follows the owner's 2026-10-13 choice of plain
`sqlite3`.

## Orchestration rung

N-A: no graph changes here. 4b2 calls these writes from a node after the
owner's approval.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | each write's outcomes as rows; a repeat, a reused key with other content, a rejection then an approval |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | all deterministic |
| Data -- provenance, freshness, what happens when a source is withdrawn | Partial | an owner's v1 list is migrated forward, in one transaction, its tasks unchanged; a newer version is refused. No backward migration: a v2 list opened by the previous version is refused there, as ADR 0006 says |
| Untrusted input -- anything ingested that this project did not write | Partial | a write's values will come from the model (4b2): checked by the same rules as the owner's add, and stored by bound parameters. The key comes from the graph |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Partial | schema version 2 and its table `task_writes`; the store's `writer()`. No setting, flag or graph change |
| Failure -- what the user sees when a dependency is down | Clear | a locked list: the store's error after `TASK_STORE_TIMEOUT_SECONDS`, as for every other operation |
| Cost -- tokens, time, money and storage per run | Clear | one audit row per decision, at most a few hundred bytes; no model call |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Where the audit lives | decided by the agent | a table in the task list's own file. One transaction then holds the effect and its record, so neither can exist without the other. A log file could not be written atomically with the database |
| 2 | A key used again for a different write | decided by the agent | refused with `ValueError`, nothing written. A key names one write, so a reuse is a caller's bug, never a write to apply |
| 3 | Reassigning to an empty assignee | decided by the agent | allowed: it unassigns, as `starter tasks add` without `--assignee` adds an unassigned task |

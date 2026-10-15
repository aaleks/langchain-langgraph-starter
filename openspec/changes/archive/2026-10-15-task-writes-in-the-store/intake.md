# Intake

- **Class:** structural
- **Intent:** For the owner, before the assistant may propose a write: the
  task list can create, close and reassign a task, each write applied at
  most once under its key and recorded in an audit table in the same file.
  This adds schema version 2, to which an existing list is migrated forward
  when opened. Slice 4b2 puts these writes behind the owner's approval.
- **Because:** it changes the task list's schema -- every owner's existing
  file is migrated -- and adds the store's write interface, which the
  approval route will call. Both are expensive to reverse (ADR 0006).
- **Approved:** the owner chose slice 4's rung and its 4a/4b split, and
  answered 4b's questions, on 2026-10-14:
  - approval through the server API in LangChain's format;
  - a rejection ends the run;
  - approve or reject only.

  Splitting 4b into this store change (4b1) and the approval route (4b2)
  was decided by the agent under the owner's standing delegation: about 15
  requirements in one change is past the method's limit.

## Scope, against the roadmap's slice 4b

Here, 4b1:
- the writes themselves -- create, close, reassign -- in the store;
- idempotency per key;
- the audit;
- schema version 2 and its migration.

Later, 4b2:
- the three write tools;
- the approval pause, in LangChain's format;
- a rejection ending the run;
- the key built from the thread and the step;
- the prompt;
- the local server's approval, end to end.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

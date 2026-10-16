# Intake

- **Class:** structural
- **Intent:** For the owner: a write waiting for approval survives the local
  server's restart. The assistant pauses, the server stops and starts again,
  and the owner's approval -- or rejection -- resumes the same thread and
  applies the write once. Each checkpoint carries the state's version, so a
  checkpoint written by an older version is migrated or refused, never misread.
- **Because:** it adds a store -- the threads' checkpoints, in a SQLite file
  through `langgraph-checkpoint-sqlite` -- a `langgraph.json` key the server
  reads, a setting, and a stamp on every checkpoint: a data model and an
  interface, expensive to reverse.
- **Approved:** the owner, 2026-10-16:
  - the split: "5a, 5b, 5c (Recommended)" -- this is 5a; 5b thread
    ownership, 5c retention and a thread's size;
  - the store: "SQLite checkpointer (Recommended)";
  - for 5b, recorded here so it is not asked again: "A local token
    (Recommended)".

## Scope, against the roadmap's slice 5

In:
- the durable checkpointer, chosen by the owner, composed for the local
  server;
- a run paused, the server restarted on the same file, and resumed;
- the state's version stamped on each checkpoint, and what an older or newer
  one does.

Out, to 5b and 5c:
- thread ownership (5b: a local token);
- retention, deletion, a thread's size, the context budget (5c);
- the items verify of approve-task-writes left in slice 5 (roadmap), unless one
  turns out to be this change's.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

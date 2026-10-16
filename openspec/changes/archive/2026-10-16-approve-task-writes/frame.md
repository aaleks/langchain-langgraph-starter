# Frame

## Outcome

**Who benefits:** the owner. They can ask the assistant to add, close or
reassign a task, see exactly what it proposes, and decide. A model reading
a task that gives it orders can, at most, propose; nothing changes without
the owner.

**The observable signal:**
- a run whose model proposes a write pauses with an approval request naming
  the write;
- the task list is unchanged until a decision;
- an approval applies the write once and the run goes on;
- a rejection writes nothing and ends the run;
- every decision is in `task_writes`;
- the same works through `scripts/serve.sh`'s API, on one thread.

**Non-goals:**
- **No edit decision** (the owner chose approve or reject).
- **No UI of this project's own:** the payload is LangChain's, so Agent Chat
  UI and `useStream` render it.
- **No durable checkpointer:** a pause lasts as long as the local server's
  in-memory thread does. Slice 5 makes it durable.
- **No check that a task exists before the owner is asked.** The writer
  checks when the write is applied, and a missing or closed task is
  answered as refused.

## Existing options considered

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| LangChain's human-in-the-loop types (`HITLRequest`, `ActionRequest`, `ReviewConfig`, decisions), langchain 1.4.4 installed | yes: shipped in the installed minor; LangChain's docs show Agent Chat UI and `useStream` rendering them (docs.langchain.com, human-in-the-loop and frontend pages, read 2026-10-14) | the payload a client renders, and the resume shape | used as data in this graph's own node; the middleware is `create_agent`'s and is not used (ADR 0007) |
| `langgraph.types.interrupt` / `Command(resume=...)`, langgraph 1.2.14 | yes: the installed runtime | the pause and its resume on one thread | none |
| a payload of this project's own, `{approved: bool}` | -- | -- | the owner declined it (2026-10-14): no client understands it |

**Decision:** LangGraph's `interrupt()` in a node of this graph, carrying
LangChain's approval request as data. The owner chose this on 2026-10-14.

## Orchestration rung

**A hand-written graph** (ADR 0007), now with the two nodes it was climbed
for:
- `review_writes` -- the interrupt;
- `apply_writes` -- the write, after it.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | each decision, a malformed resume, a refused proposal, a replay |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | all deterministic: routes, payloads, the list's rows |
| Data -- provenance, freshness, what happens when a source is withdrawn | Clear | a write's values come from the model: checked by TASKS-WRITE-VALUES before the owner sees them, again by the writer |
| Untrusted input -- anything ingested that this project did not write | Partial | task text ordering a write: it can only be proposed, and the run pauses (ASSISTANT-UNTRUSTED-TASK-TEXT, a row). A resume is the owner's: anything but an exact approval rejects |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Partial | the approval request and its resume; state version 2; prompt version 2; three tool names and schemas. The graph id stays `assistant` |
| Failure -- what the user sees when a dependency is down | Clear | a locked list at apply: the store's error, the run failed, nothing written, and the thread paused at `apply_writes` until continued |
| Cost -- tokens, time, money and storage per run | Clear | three tool schemas sent to the model each call: a few hundred characters; one audit row per decision |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | A resume that is not a clean list of decisions | decided by the agent | every write without an exact `{"type": "approve"}` is rejected, and a count that does not match rejects all: the safe outcome is no effect |
| 2 | Two writes in one reply, one approved and one rejected | decided by the agent | each decided on its own; the run ends, since one was rejected (the owner's rule) |
| 3 | Reads and writes in one reply | decided by the agent | the reads run first and are answered; then the pause |

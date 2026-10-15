# 9. Every write waits for the owner's approval, in LangChain's approval format

Date: 2026-10-15
Status: Accepted.

## Context

The product's rule: the assistant reads freely, and every write waits for
the owner's approval (`docs/roadmap.md`). ADR 0007 made the assistant a
hand-written graph for this. ADR 0008 made each write applied once per key,
and audited.

On 2026-10-14 the owner chose:
- **the format:** the server API, in LangChain's approval format;
- **after a rejection:** the run ends, with no further model call;
- **the decisions:** approve or reject only.

What is settled here is the interface a client depends on:
- the payload of the pause;
- the shape of the resume;
- what each decision does.

## Decision

- **The run pauses in `review_writes`** with `interrupt()`, carrying
  LangChain's `HITLRequest` shape:
  - `action_requests`: the tool's name, its checked arguments, a
    description;
  - `review_configs`: `approve` and `reject` only.

  A client resumes the same thread with
  `Command(resume={"decisions": [...]})`, one decision per action, in
  order. Agent Chat UI and `useStream` render this shape.
- **Anything but an exact approval rejects.** A malformed resume rejects
  every action.
- **`apply_writes` decides each write through the store's writer**, under
  the key `<thread>:<reply>:<call>` -- the reply that proposed it, whose id
  is the same on every replay; the superstep is not (measured). Approved:
  applied once, answered with
  its outcome. Rejected: recorded, answered, and the run ends.
- **A write proposal is checked before the owner sees it** -- the tool's
  schema and the task list's rules -- and is checked again when it is
  applied.
- **Write tools are proposals only:** they cannot be run directly.

## Consequences

**Good:**
- No UI to own.
- Nothing changes without the owner.
- A replay, a doubled resume or a continue after a failure cannot write
  twice.
- Every decision can be read back.

**Costly:**
- A rejection gives no conversational reply.
- An approved write of a task closed meanwhile is refused only when
  applied.
- A pause lasts as long as the server's thread, until slice 5 makes it
  durable.

**Reversal:** another payload is a change of `review_writes` and of every
client. Letting the model continue after a rejection is one route
(`route_after_writes`).

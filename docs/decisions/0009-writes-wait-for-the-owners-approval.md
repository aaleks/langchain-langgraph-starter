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
  the key `[thread, reply, call]`, a JSON array -- the reply that proposed it, whose id
  is the same on every replay; the superstep is not (measured). Approved:
  applied once, answered with
  its outcome. Rejected: recorded, answered, and the run ends.
- **A write proposal is checked before the owner sees it** -- the tool's
  schema and the task list's rules -- and is checked again when it is
  applied.
- **Write tools are proposals only:** they cannot be run directly.
- **The owner is shown the task by its title and status as the list holds
  them**, never by the model's word for it.
- **Writes are decided one a step**, each answered with the outcome the
  store recorded for its key.
- **Each call of a reply has an id of its own**, so a decision is never
  another call's.
- **Browsers:** only `http://localhost:3000` may use the local server --
  the owner's choice, 2026-10-15. Any other page in the owner's browser
  gets no CORS permission, so cannot read a paused run.
- **A request guard in front of every route** -- the owner's choice,
  2026-10-15, since CORS never stops a page *sending* a `text/plain`
  POST. It refuses a `Host` that is not this machine, a write from
  another page's `Origin`, and a write body that is not
  `application/json`. A WebSocket -- the server's event stream starts and
  resumes runs over one, and CORS never applies to it -- is refused for its
  `Host` and for any other page's `Origin`. Anything but HTTP, WebSockets
  and the server's lifespan reaches nothing. Its policy is the domain's
  `request_refusal`; `langgraph.json` names the middleware as `http.app`
  -- the one entry there beside the graphs that names code, an exception
  to "langgraph.json names only registry exports" that this decision makes.
- **A write's answer lost is read back from the store.** A run that ends
  after the store commits and before the step's checkpoint loses the
  answer, never the write; the next run answers the call with the
  outcome recorded under its key.

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
- A process on this machine can still edit a paused thread's state, and
  so approve a write itself -- as it could write the task file. Slice 5's
  thread ownership revisits it.

**Reversal:** another payload is a change of `review_writes` and of every
client. Letting the model continue after a rejection is one route
(`route_after_writes`).

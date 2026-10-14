# Intake

- **Class:** structural
- **Intent:** For the owner, before any write reaches their task list: the
  assistant becomes a hand-written LangGraph `StateGraph` that behaves as the
  `create_agent` tool loop did -- every route, budget and error the living
  spec names -- with a versioned state contract, its routing decided in
  `domain/`, and its topology held equal to the design's table by a test.
  Approval-gated writes then land on a graph whose every node and route is
  this project's own (slice 4b).
- **Because:** it changes the state schema, the node names and the step count
  of the registered graph `assistant` -- an interface of the local server's
  threads -- and the error classes a run ends with. Each is expensive to
  reverse once threads and clients depend on them.
- **Approved:** the owner, on 2026-10-14:
  - "go ahead with slice 4 I think it's better to use hand-written LangGraph
    graph" -- the rung;
  - "Split 4a / 4b (Recommended)" -- this change is 4a;
  - for 4b: "Server API, LangChain format (Recommended)", "Run ends, no more
    model calls (Recommended)", "Approve or reject (Recommended)".

  Class and scope were decided by the agent under the owner's standing
  delegation.

## Scope, against the roadmap's slice 4

Here, 4a:
- the rung: a hand-written `StateGraph`, compiled by the factory, registered
  under the same id;
- the old Correctness slice's parts the roadmap names: a versioned state
  contract, routing policy in `domain/`, topology tests.

Later, 4b: create, close and reassign; `interrupt()` and
`Command(resume=...)`; idempotent, audited writes.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

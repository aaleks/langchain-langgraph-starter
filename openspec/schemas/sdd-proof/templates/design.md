# Design

<!-- Structural changes only, or when the frame's coverage screen raised a
     design question. Point at frame.md for why; do not restate the specs. -->

## Context

## Decisions

<!-- Each: the choice, the alternatives considered, why this one. A decision
     expensive to reverse -- data model, store, provider, embedding, public
     interface, graph id, state schema -- also gets an ADR in docs/decisions/. -->

## Orchestration design

<!-- Only when the frame's rung is a hand-written graph, otherwise N-A. The
     table is the contract; a diagram is review evidence, not the source of truth. -->

| Node (a business outcome) | Kind (read, decide, write) | Reads | Writes or side effect | Routes to | Decided by (domain policy or model) |
|---|---|---|---|---|---|

- **State:** <!-- fields, owner, serialisable, version -->
- **Identity:** <!-- who creates a thread id, which user and tenant own it, and
  the ownership check before a resume, a read or a fork -->
- **Budgets:** <!-- steps, retries, replans, tool calls -- each with its terminal outcome -->
- **Errors:** <!-- each failure the graph can meet, by class -- transient,
  correctable, contract, policy, needs a human, defect -- and its handling and
  terminal outcome -->
- **Interrupts:** <!-- where a human approves, and how the same thread resumes -->
- **Tools:** <!-- capability, authorisation, idempotency, retry class -->
- **Streaming:** <!-- what streams to whom (updates, messages, custom events),
  and what never does -->
- **Persistence:** <!-- checkpointer per environment; encryption at rest;
  retention and deletion; what is never stored -->
- **Observability:** <!-- run and thread ids in every record; what is logged,
  locally; what never is (secrets, raw user content) -->
- **Runtime:** <!-- how it runs locally -- the entry points, the tests, the
  development server -- and the durable store it needs, if any. If it will ever
  run beyond this machine, how: an ADR decides that -->
- **Test plan:** <!-- the tier for each claim: policies (unit), routes and
  topology with fakes (integration), durability with a real saver, the local
  server smoke (live), generated text (/eval) -- and security (adversarial
  cases: no unauthorised effect), operations, and migration (an old checkpoint
  resumes) -->
- **Graph id:** <!-- the registered id, and what changing it does to existing threads -->

## Risks

<!-- [Risk] -> mitigation -->

## Migration and rollback

<!-- What happens to existing data, threads, flags or users, and how to undo it.
     N-A with a reason if nothing persists. -->

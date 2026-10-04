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

| Node (a business outcome) | Reads | Writes or side effect | Routes to | Decided by (domain policy or model) |
|---|---|---|---|---|

- **State:** <!-- fields, owner, retention, serialisable, version -->
- **Budgets:** <!-- steps, retries, replans, tool calls -- each with its terminal outcome -->
- **Interrupts:** <!-- where a human approves, and how the same thread resumes -->
- **Tools:** <!-- capability, authorisation, idempotency, retry class -->
- **Persistence:** <!-- checkpointer per environment; what is never stored -->
- **Graph id:** <!-- the registered id, and what changing it does to existing threads -->

## Risks

<!-- [Risk] -> mitigation -->

## Migration and rollback

<!-- What happens to existing data, threads, flags or users, and how to undo it.
     N-A with a reason if nothing persists. -->

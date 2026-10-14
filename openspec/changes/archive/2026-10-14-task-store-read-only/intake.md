# Intake

- **Class:** structural
- **Intent:** For the owner running the task assistant: the registered
  `assistant` can list and search the owner's local task list -- a SQLite
  file on this machine -- through its first real tools, each with a
  capability manifest, the run bounded by a tool-call budget beside the
  model-call budget, and task text read as data, never as instruction. It
  changes nothing in the list: writes are slice 4.
- **Because:** it adds the project's first data store and its schema, the
  first real tools and the capability-manifest format every later tool will
  follow -- a data model, a store and a tool contract, each expensive to
  reverse.
- **Approved:** the owner chose the product on 2026-10-12 ("Approval-gated
  tasks") and the slices in `docs/roadmap.md`; class and scope decided by the
  agent under the owner's standing delegation of the same day.

## Scope, against the roadmap's slice 3

Kept: the SQLite task list and its schema (an ADR); the tools `list` and
`search`; the capability-manifest format and the fixture-proven check that no
tool registers without one; a tool-call budget; task text and tool output as
untrusted data, with an adversarial case asserting no unauthorised effect.

Taken from slice 2: the decision on `invalid_tool_calls`, and
`MODEL_CALLS_PER_RUN` re-measured with tools bound.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

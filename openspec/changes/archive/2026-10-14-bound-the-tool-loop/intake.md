# Intake

- **Class:** structural
- **Intent:** For the owner whose assistant now runs on a real model, over
  their real task list: every route the tool loop can take ends in a stated
  outcome, and every budget comes from runs that were measured. Specifically:
  - a malformed tool call goes back to the model, never ends the run as an
    empty answer;
  - a run whose conversation outgrows its budget ends with a named error;
  - the model is told what it is for, and that task text is data;
  - the call budgets are re-measured against real runs.
- **Because:** it adds a terminal outcome -- the context budget -- and a
  route, the malformed call. It also adds the assistant's first prompt, an
  interface the model reads every turn, and an adversarial case for
  untrusted input. Budgets and prompts are policy the later slices inherit.
- **Approved:** the owner chose the slices (`docs/roadmap.md`, 3b) and, on
  2026-10-14:
  - "Small, fixed batch (Recommended)" -- about 20 measured runs;
  - "End the run with an error (Recommended)" -- the context budget;
  - "Yes, a short factual prompt (Recommended)".

  Class and scope were decided by the agent under the owner's standing
  delegation.

## Scope, against the roadmap's slice 3b

Kept, all four:
- the budgets re-measured;
- the decision on `invalid_tool_calls`;
- a run's budget on what reaches the model;
- task text as untrusted data, with an adversarial case.

The decision on `invalid_tool_calls` is the project's rule
(`.claude/rules/langgraph/graphs.md`, "Errors"): a malformed tool argument is
model-recoverable, and is handed back to the model, bounded.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

# Frame

## Outcome

<!-- Who benefits, and the observable signal that says it worked. Measurable
     where it can be. Kept apart from the requirements, which state behaviour. -->

## Existing options considered

<!-- REQUIRED. The table, or one line: "None -- <glue between this project's own
     parts | a change to its own configuration | an amendment of an existing
     requirement | a defect>". Say what you checked to call an option maintained. -->

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|

**Decision:** <!-- adopt <option> plus a thin layer, or build -- because <the
trade-off in one sentence>. Chosen by <who>. -->

## Orchestration rung

<!-- LLM work only, otherwise N-A. One call | a tool loop (create_agent and its
     middleware) | a hand-written graph -- and the requirement whose control
     flow needs that rung. Climb when a requirement needs it, never before. -->

## Coverage screen

<!-- Mark every row Clear / Partial / Missing / N-A. N-A needs a reason. A
     Missing on a dimension this change touches becomes a question below or a
     requirement. -->

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | | |
| Behaviour -- every rule falsifiable, each with a counter-example | | |
| Determinism -- honestly tagged; every evaluated rule split once more | | |
| Data -- provenance, freshness, what happens when a source is withdrawn | | |
| Untrusted input -- anything ingested that this project did not write | | |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | | |
| Failure -- what the user sees when a dependency is down | | |
| Cost -- tokens, time, money and storage per run | | |
| Ownership -- who decides when a requirement turns out to be wrong | | |

## Defect

<!-- Defect class only, otherwise N-A. The root cause is named before any fix. -->

- **Symptom:**
- **Reproduction:** <!-- exact steps, or the failing test -->
- **Root cause:** <!-- "X, because <evidence>" -- not a guess -->
- **Requirement that should have caught it:** <!-- an existing id (a MODIFIED
  delta) or a missing one (ADDED) -->

## Open questions

<!-- Ask now anything a human can answer in a sentence. Record OPEN only what
     needs data that does not exist yet, and say what would resolve it. -->

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|

# The coverage screen -- nine rows, every change

Traceability enforces a requirement once it exists. It cannot notice a
requirement that should have existed and was never written: a change can be
fully specified, tested and green while missing a cost limit or a failure mode
altogether. The screen is the one mechanism for that omission, and it is
proportional by construction -- most rows on most changes are N-A, with a reason.

Mark each row **Clear** (covered by a requirement or an explicit decision),
**Partial**, **Missing**, or **N-A** (with the reason). Only a **Missing** on a
dimension this change actually touches becomes a question or a requirement.

| Dimension | The question | Typical N-A |
|---|---|---|
| Outcome | Who is this for, and what observable thing says it worked? | never -- every change has an outcome |
| Behaviour | Is every requirement falsifiable, with a counter-example? | never |
| Determinism | Is each requirement honestly tagged, and has every `evaluated` one been split once more? | no LLM output involved |
| Data | Provenance, freshness, and what happens when a source is withdrawn or changes shape? | the change reads no data it did not create |
| Untrusted input | Does it ingest anything this project did not write -- user text, crawled pages, retrieved chunks, tool output? If so, that text is data, never instruction. | input is only this project's own configuration |
| Interfaces | Does it change a flag, an env var, an output schema, an embedding, a default, a graph id or a state schema? Each is a contract someone may depend on. | internal refactor |
| Failure | What does the user see when a dependency is down, slow or rate-limited -- and is that a requirement? | no external dependency |
| Cost | What does one run cost in tokens, time, money and storage? Does this change it materially? | no model call, no storage growth |
| Ownership | Who decides when a requirement here turns out wrong? | the project owner, as usual -- say so |

## When untrusted input is Clear-required

If the screen flags untrusted input reaching a model, the minimum is one
requirement that the content is treated as data and never as instruction, and
one adversarial case in the evaluation set whose assertion is *no unauthorised
effect* -- never a particular wording. Anything deeper waits for the trigger in
`.claude/sdd/deferred-register.md`.

## What the screen replaced

A ten-dimension coverage map, a risk screen, three assurance profiles, a
production-readiness block and a security verifier were all proposed for this
one problem. Nine rows, marked in the frame, do the job proportionally; the
rest is deferred with explicit triggers rather than added as ceremony.

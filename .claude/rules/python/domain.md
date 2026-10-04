---
paths:
  - "src/*/domain/**"
---

# The domain layer -- pure decisions

The most important boundary in the project, and the reason the unit suite runs
in a fraction of a second.

- **Standard library only.** No SDK, no client, no framework, no other layer of
  this package. An architecture test enforces it as an allowlist, and the edit
  guard refuses the common SDK imports at write time.
- **The environment is an argument.** `resolve_provider(env, override)`, never
  `os.getenv` inside: a test hands it a dict instead of patching a process.
- **Deterministic.** No `random`, no `datetime.now()`, no `uuid4()`. Take a clock
  or an id generator as a parameter when you need one -- a function that answers
  differently each call cannot be asserted with `==`.
- **This is where decisions live:** precedence, validation, eligibility,
  classification, routing, budgets, masking. Not in an adapter, not inline at
  the call site.
- **Raise `ValueError` for anything a caller could fix. Never exit.**
- Small pure functions and frozen dataclasses over stateful classes. A function
  that keeps accreting cases is asking for a named value object with its own test.

If you cannot see how to assert it with exact values, it probably does not
belong here.

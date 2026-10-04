---
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*_test.go"
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/__tests__/**"
---

# Tests are executable specifications

- **No real model call in the default suite.** Use a fake. A test that reaches a
  provider is slow, costs money and answers differently every run. The one
  exception is the check for an `evaluated` requirement: marked `live`, outside
  the default suite, its docstring saying why it exists.
- **Never assert generated prose.** Assert structure: a verdict, a schema, an
  exit code, a printed line, the route a graph took. Quality claims belong to a
  judge with an agreed threshold.
- **The lowest tier that can prove it.** A pure decision is a unit test; what a
  user observes at the entry point is an acceptance test. Not the same claim twice.
- **Name the test after the rule** -- `test_zero_override_is_honoured_not_treated_as_absent`,
  never `test_case_2` -- and quote the requirement id in the class docstring.
- **Every test file is claimed** by a requirement's `Proved by`, or `sdd check`
  fails. An unclaimed test is behaviour nobody agreed to.
- **Never weaken or delete a test to make code pass.** Fix the code. If the test
  is wrong, its requirement is wrong too: say so and stop.
- **Read configuration through a clean environment fixture**, so a test cannot
  pass or fail depending on whose machine runs it.

## Three failures that keep recurring

**Testing the halves, not the seam.** Two components, each correct and green,
wired together wrongly. When you test a component, ask what proves it is *used*
-- that is the story test's job.

**A check that cannot fail.** Before trusting a green check, break the thing it
watches and watch it go red. Architecture tests, eval gates, and any assertion
whose subject is another test.

**A double that agrees with itself.** A hand-written stand-in for someone
else's class asserts your memory of the library, not the library. Subclass the
real base class where one exists; otherwise check the double's methods and
signatures against the real class with `inspect`.

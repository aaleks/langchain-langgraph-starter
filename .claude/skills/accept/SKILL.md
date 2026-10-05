---
name: accept
description: "Use when a deterministic requirement in a change has no failing test yet -- including the first requirement of a new story, which also needs its story test. Not for evaluated requirements."
argument-hint: "<REQUIREMENT-ID> [change-id]"
model: inherit
---

# /accept -- one failing test, before any implementation

Requirement: $ARGUMENTS

The requirement is written and approved. This turns it into a test that fails
**for the right reason**, before any code exists. The failing test is the
deliverable. Do not write production code in this skill.

## First: is it deterministic?

Read the requirement's `Kind` in the change's delta spec (or the living spec).

- `deterministic` -- continue.
- `evaluated` -- **stop.** An exact assertion on generated prose is a flake that
  gets deleted in three weeks. Send it to `/eval`, and offer the next
  deterministic requirement instead.
- missing -- the spec is unfinished. Back to `/discover`.

**One requirement per invocation.** Do not write tests for requirements nobody
named. The one addition is the story test, below.

## The story test -- once per story, before its first requirement

A requirement's test proves a decision. It does not prove a user can reach it.
When this is the first requirement of a story (tasks.md names a story test that
does not exist yet), write that test first: driven through the real entry
point, with fakes for every model and service, asserting only what a user would
see at the end -- a printed line, an exit code, a file, a returned value. Run
it. It fails.

**It stays red across every `/tdd` cycle of the story** and goes green only when
the last requirement is wired in. A story test still red when every requirement
is green is a finding, not a nuisance: a decision tested in isolation, green,
and never called by anything is exactly what it catches.

Skip it, and say so in the report, when the story already has one, or when the
requirement's only observable behaviour *is* the entry point -- then the
requirement's own test is the story test.

## Why first

A test written after the code asserts what the code happens to do. A test
written from the requirement asserts what was agreed. When they differ, that is
the finding -- and you only see it if the test came first. A test that has
never been red has never been shown capable of failing.

## 1. Read the requirement, not the code

Its scenarios are your test cases; the values are concrete precisely so they can
be transcribed. Do not read the implementation first -- if it exists, it will
bias the test toward what it does.

## 2. Pick the lowest tier that can prove it

| Tier | When | Where |
|---|---|---|
| unit | the requirement is a pure decision | `tests/unit/` |
| integration | it is about wiring, configuration loading, an adapter against a fake | `tests/integration/` |
| acceptance | it is what a user observes at the entry point: output, exit code, a flag | `tests/acceptance/` |

Most deterministic requirements are unit tests, because most of what an LLM
application does is decide things.

A requirement about a graph's route -- nodes visited, an interrupt, an
exhausted budget: if `references/graph-routes.md` exists, read it first. It says
what such a test asserts, and where it lives.

## 3. Write it

- One class per requirement, named after it; the class docstring quotes the id
  and the requirement sentence.
- One test per scenario; a scenario's table rows become parametrised cases.
  **The counter-example is a test too.**
- Name each test after the business rule --
  `test_zero_override_is_honoured_not_treated_as_absent`, never `test_case_2`.

Hard constraints:

- **No real model call.** Use a fake. A test that hits a provider is slow, costs
  money, and answers differently every run.
- **No exact LLM prose in an assertion.** If you want one, the requirement is
  `evaluated`.
- Anything needing a running service carries the project's `live` marker.
- **If you cannot inject a fake, the production code has a seam problem.** Say
  so and stop. Patching internals hides the design problem and couples the test
  to the implementation.

## 4. Run it, and read the failure

Run it with `[commands].test` from `sdd.toml`. It must fail. Then ask why:

| Failure | Meaning |
|---|---|
| import or attribute error -- nothing implements it yet | correct red; proceed |
| an assertion fails on a plausible value | something already does this: stop and tell the user -- the job just changed |
| it passes | the test is wrong: it asserts something trivially true. Rewrite it |

## 5. Close the loop

The requirement's `Proved by` line must name the file and class you wrote --
correct it in the change's delta if it drifted. Then:

```bash
bash .claude/sdd/sdd.sh check
```

This requirement's `SDD003` is gone; any remaining ones belong to requirements
not written yet. Tick the matching box in tasks.md, citing the red you saw.

## Report

1. The requirement id, the file and the test names written.
2. The exact failure message.
3. Why that failure is the right red.
4. The story test: written now, already present, or skipped and why.

Then stop. `/tdd` drives it to green.

## Red flags

| Thought | Reality |
|---|---|
| "I'll sketch the implementation to see what to test" | That is testing after. Read the requirement, not the code. |
| "This scenario is obvious, skip its test" | The scenario you skip is the one that breaks. Every row, counter-example included. |
| "A mock of the internal helper is quicker" | It proves the helper was called, not that the requirement holds. Find the seam, or report that there is none. |
| "It passed first time -- great" | A test that never failed proves nothing. Rewrite it until it fails for the right reason. |

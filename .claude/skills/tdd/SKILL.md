---
name: tdd
description: "Use when a failing test exists for a requirement and the code to make it pass does not. One cycle per invocation; pass --to-green only when the user asks for a run to green."
argument-hint: "<test or requirement id> [--to-green]"
model: inherit
---

# /tdd -- one cycle: red, green, refactor, challenge, stop

Target: $ARGUMENTS

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Code written before its test is deleted, not kept "as reference" and adapted.
(The Iron Law as Superpowers states it; see .claude/sdd/CREDITS.md.)

**One cycle is one test**: one new test function, or one new case in an
existing parametrised list. Not "drive until everything passes" -- that is the
outer loop. The edge case proposed in CHALLENGE becomes the next red in a
**new** invocation. The only exception is `--to-green`, which the user must ask
for explicitly; never assume it.

```
RED  ->  GREEN  ->  REFACTOR  ->  CHALLENGE  ->  STOP
```

Do not collapse green and refactor. Getting it working and getting it right are
different problems; solving both at once is how you end up with neither.

## 1. Confirm red, and why

Run the one test with `[commands].test` from `sdd.toml`. Not red: stop --
something upstream is wrong; go back to `/accept`.

## 2. Choose the layer

The project's layer rules are in `CLAUDE.md` and `.claude/rules/`. Whatever the
names, **default to the pure decision layer**: if the requirement can be
expressed as a pure decision -- precedence, validation, eligibility, routing, a
budget -- put it there. That is what makes it provable in milliseconds with no
service. The adapter that acts on the decision goes in the outer layer.

If the behaviour seems to need a model in order to be tested, that is the signal
to move the decision inward and pass the model's output in as data. Say so out
loud rather than writing a test around a fake's scripted reply.

## 3. GREEN -- the smallest thing that passes

**Minimum is literal.** If a hard-coded return makes the test pass and nothing
else breaks, that is a legitimate green: it proves the test does not constrain
enough yet, and the next cycle forces the generalisation. No error handling,
logging or configuration that no test demands. Do not implement the edge case
you can already see coming -- that is the next red.

Raise for anything a caller could fix; never exit the process below the entry
point layer.

## 4. Green, then refactor

Run the one test, then the whole suite (`[commands].suite`). Both green before
you touch the shape of the code. Then tidy -- names, duplication, and a comment
saying *why* wherever the code is surprising -- and run the suite again. If a
requirement exists because something broke, the comment says so.

## 5. Full check

`[commands].check` -- format, lint, architecture, `sdd check`, suite. It must
pass before the cycle is done.

## CHALLENGE -- name the next edge case

Propose the single most valuable next case, and why it matters. Draw first from
the requirement's scenarios and counter-examples that have no test yet, then
from boundaries the code now visibly ignores: empty, exactly-at-threshold, zero,
a duplicate, unicode, null. If every scenario of the requirement is asserted and
green, say so, tick its box in tasks.md with that evidence, and name the
requirement `/accept` should take next.

## STOP -- report and wait

1. The test, and the exact red it produced.
2. The production code written, in a sentence or two.
3. What the refactor changed, or that none was needed.
4. The proposed next edge case.
5. The full check's result -- run fresh, not remembered.

Then wait. Do not begin the next cycle.

**`--to-green <test>`:** loop red, green, refactor without stopping until that
test passes -- still one test at a time, still minimum code, still the full
suite green between cycles -- and report every cycle so the sequence stays
reviewable.

## When the code and the requirement disagree

Stop. Do not quietly change either. The requirement is authoritative, but a
requirement written from a wrong assumption is worth knowing about. Say which
one you think is wrong and why; the user decides, and a wrong requirement is
amended by a MODIFIED delta, never by an edit to the living spec.

## Rationalisations

| Excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. The test takes a minute. |
| "I'll test after" | A test written after passes immediately, which proves nothing. |
| "Keep it as reference, write the test first" | You will adapt it. That is testing after. Delete means delete. |
| "Let me add the error handling while I'm here" | No test demands it. It is the next red, or it is nothing. |
| "Weaken this old test so the new code passes" | Never. Fix the code. If the old test is wrong, so is its requirement: stop and say so. |
| "All tests pass" (without running them now) | Evidence before claims: run the command, read the output, then say it. |

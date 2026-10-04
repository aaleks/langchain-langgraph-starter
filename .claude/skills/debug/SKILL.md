---
name: debug
description: "Use when something behaves wrongly -- a bug report, a failing test, a red CI run, unexpected output, a performance surprise -- before proposing any fix."
argument-hint: "<the symptom> [change-id]"
model: inherit
---

# /debug -- root cause first, then a requirement that stays

Symptom: $ARGUMENTS

```
NO FIX WITHOUT A NAMED ROOT CAUSE
```

A symptom fix is a failure that has not happened yet. Until the root cause is
named, with evidence, you may investigate -- read, run, instrument -- but not
fix. (The four phases are Superpowers' systematic debugging, condensed; see
.claude/sdd/CREDITS.md.)

In this method a defect is **a missing or wrong requirement**. So the lane ends
with a requirement in the living spec and a test that would have caught the
defect -- regression discipline that outlives the fix.

## Phase 1 -- investigate

1. **Read the error completely** -- the whole trace, the line numbers, the codes.
2. **Reproduce it reliably.** Exact steps, every time. If it does not reproduce,
   gather more data; do not guess.
3. **Check what changed** -- `git log`, `git diff`, dependency and configuration
   changes, environment differences.
4. **At a boundary between components, instrument before you theorise**: log
   what enters and leaves each one, run once, and find *where* it breaks.
5. **Trace the bad value backwards** to where it originates. Fix at the source,
   not where it surfaced.

## Phase 2 -- compare

Find similar code that works. List every difference between working and broken,
however small; do not assume one "cannot matter".

## Phase 3 -- one hypothesis at a time

"I think X is the root cause because Y." Test it with the smallest possible
change, one variable at a time. Wrong: form a new hypothesis, do not stack
fixes. Not understood: say "I don't understand X" -- and ask.

## Phase 4 -- the requirement, then the fix

1. **Name the requirement that should have caught it:**
   - an existing requirement whose scenarios missed this case -- the change will
     MODIFY it, adding the scenario (often the counter-example nobody wrote);
   - a requirement that never existed -- the change will ADD it.
2. **Record it** in the change's `frame.md`, Defect section: symptom,
   reproduction, root cause with its evidence, and that requirement. No change
   yet? Run `/intake` first -- class `defect`.
3. `/discover` writes the delta; `/accept` writes the failing test, which must
   fail **for the defect's reason** -- the reproduction, captured; `/tdd` fixes
   the root cause, one change, no "while I'm here".

**Three fixes that did not hold means stop.** When each fix reveals a new
problem somewhere else, the pattern is wrong, not the hypothesis. Question the
architecture with the user before a fourth attempt.

## Red flags

| Thought | Reality |
|---|---|
| "Quick fix now, investigate later" | Later never comes, and the quick fix hides the evidence. |
| "Let me try changing X and see" | That is guessing. Form a hypothesis with a reason first. |
| "Several changes at once will be faster" | Then you will not know which one worked, or which one broke the next thing. |
| "It's too small to need a requirement" | A defect that escaped once escapes again without one. The requirement is the fix that lasts. |
| "The test is wrong, not the code" | Possibly -- then the requirement behind it is wrong too. Say so and stop; do not edit the test to pass. |

When the defect is fixed and merged, run `/learn`: what rule, guard, check or
fixture would have caught it earlier?

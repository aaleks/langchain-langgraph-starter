---
name: learn
description: "Use when something went wrong that the method should have caught -- a defect that escaped, a red CI run nobody saw locally, a repeated review finding, a check that passed while checking nothing, or a rationalisation that got past a skill."
argument-hint: "<what went wrong>"
model: inherit
---

# /learn -- every failure leaves something executable behind

What went wrong: $ARGUMENTS

The rules in this method exist because something broke. This stage is what
puts the next one there. Its output is **exactly one** of the following, and
the earlier options win:

| Output | When | Proof it works |
|---|---|---|
| **a requirement** | the product should behave differently | `/intake` a defect or bounded change; the requirement stays in the living spec |
| **a check** | a property is mechanically decidable: a checker rule, an architecture test | **a fixture that reproduces the original failure and goes red** |
| **a guard** | a write that is cheap to detect and expensive to discover later | a hook test that feeds the original edit and sees it refused |
| **a fixture** | an existing check missed a variant of what it claims to catch | the fixture fails before the check is fixed, passes after |
| **a rationalisation row** | a skill was bypassed with a reason that sounded right | the exact words observed, added to that skill's red-flag table |
| **judgement, not automatable** | none of the above can decide it honestly | the reason it cannot be automated, written down |

**Prose is the declared fallback, never the default.** A line in
`.claude/rules/project/lessons.md` is for what genuinely cannot become any of
the above -- and it says why. A lesson that could have been a check and became
a paragraph will be learned again.

## Steps

1. **State the failure in one sentence** -- what happened, and where it was
   finally noticed.
2. **Ask where it should have been caught** -- which stage, which check -- and
   why that did not happen.
3. **Choose the output**, earliest row first, and say why the earlier rows do
   not fit.
4. **Build it, and watch it fail.** A new check or guard without a fixture that
   reproduces the original failure is a check you do not have.
5. **Record it** in `docs/learnings.md`: the date, the failure, the output
   chosen, and a link to the commit or change.

## Method-level lessons

If the lesson would help every project using this method -- a checker rule, a
template slot, a skill's red flag -- mark the entry **upstream** in
`docs/learnings.md`. It belongs in the canonical method and reaches other
projects through `sdd.sh update`, not by being rediscovered in each.

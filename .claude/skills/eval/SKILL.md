---
name: eval
description: "Use when a requirement is tagged evaluated -- groundedness, summary quality, tone, refusal -- and needs a scored check against an agreed threshold, or when live eval checks need running or a failure diagnosing."
argument-hint: "<REQUIREMENT-ID> | --run"
model: inherit
---

# /eval -- the non-deterministic half

Target: $ARGUMENTS

`/tdd` proves `deterministic` requirements exactly. This proves `evaluated`
ones against a threshold somebody agreed. It is the only place a real model call
belongs in a test -- marked `live`, outside the default suite.

**Never propose lowering a threshold to get green.** A lowered threshold is a
product decision, not a test fix. If a threshold is genuinely wrong, say so with
the evidence, and let the user decide.

## Mode A -- build the check for a requirement

### 1. Confirm it is genuinely evaluated

Read its `Kind`. `deterministic` -- stop, it belongs to `/accept`. Missing --
back to `/discover`. `evaluated` -- try **once more** to split it with
`../discover/references/splitting-rules.md`. Every requirement moved out of
eval-land becomes fast, free and exact; report what you split first.

### 2. Pick the metric -- cheap and objective before a judge

| Claim | Metric | Cost |
|---|---|---|
| the output parses / conforms to a type | parse success rate | free, exact |
| the output is the right length | p50 / p90 length | free |
| a boolean verdict is right on labelled cases | accuracy against labels | free once labelled |
| a judge catches a planted flaw | pass/fail on that case | one call |
| the answer is grounded in its source | judge groundedness | paid, noisy |
| the summary is good | judge rubric | paid, noisy, hardest to trust |

Reach for a model judge only when nothing objective expresses the claim. Then:
a rubric with explicit scoring anchors, temperature zero, and **the judge
checked against human-labelled cases before it is trusted**. An unvalidated
judge is a random number generator with good manners -- a small local judge has
scored a summary with a planted hallucination as grounded.

### 3. The dataset -- written by a human

The cases live under the ground-truth path in `sdd.toml` `[guards]`, one case
per line with a stable `id` and a `source` saying where it came from. **The edit
guard refuses your write there, on purpose**: the failure mode of eval-driven
work is "the eval failed, so adjust the expected answer". Prepare the cases,
show them, and let the user write the file.

Cover the normal case, every counter-example scenario, and the known hard
cases. **Below about 20 cases a threshold measures the sampler, not the
system** -- one case can show a judge has stopped working; it cannot measure
one. Say so rather than quoting a percentage off a handful of cases.

### 4. The check

Marked `live`, its docstring citing the requirement id and the threshold. Assert
the **verdict or the score**, never the wording of a rationale. Record the model
id beside every score: a number without the model that produced it is not
reproducible.

### 5. Threshold, N, Agreed by

Never invented. Ask with `AskUserQuestion`, or leave `OPEN` with an Owner and a
Review by date. When agreed, set `Proved by` to the check, and run
`bash .claude/sdd/sdd.sh check`.

## Mode B -- run them (`--run`)

Run `[commands].live`. Report a table -- requirement, metric, **score, N**,
threshold, pass/fail, model id. A score never appears without its N.

**On a failure, diagnose before touching anything**, in this order:

1. Did the **prompt** change? The most likely cause -- diff the instructions.
2. Did the **model or its version** change? Invisible in a diff: check what the
   configured name actually resolves to.
3. Did the **route** change -- endpoint, gateway, base URL, provider?
4. Is the **case** wrong -- mislabelled, or no longer what the requirement means?

Only the fourth justifies changing the data, and only the user changes it.

## Report

The requirement, its metric, threshold and who agreed it; the score, N and
model id; pass or fail with the ranked diagnosis; and first, any deterministic
requirements you split out along the way.

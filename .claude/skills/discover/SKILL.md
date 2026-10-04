---
name: discover
description: "Use when an approved intake needs its frame, requirements, design or sequence written, or when an existing requirement turns out wrong and must be amended. Not for code or tests."
argument-hint: "<change-id>"
model: inherit
---

# /discover -- from intent to requirements someone approved

Change: $ARGUMENTS

A request is usually one unfalsifiable sentence. This skill asks whether it
should be code this project owns at all, surfaces the requirements hiding in
it, grounds each in real cases, and resolves the unknowns **with the user**.
It writes planning artifacts under `openspec/changes/<id>/` -- and an ADR when
a decision is expensive to reverse -- and nothing else. Code and tests are
`/accept` and `/tdd`, later.

## Before anything: what is approved, and what stage is next

```bash
bash .claude/sdd/sdd.sh status
```

Read `intake.md`. No approved intake: stop and run `/intake`. Then work only
the stages its class requires, presenting each and waiting for approval:

| Class | You write, in order | Approval points |
|---|---|---|
| bounded | brief frame, delta specs, tasks | one: present frame, requirements and sequence together |
| structural | frame; then delta specs; then design (+ ADR) and tasks | three, one per stage |
| defect | delta specs (one requirement), tasks -- `/debug` wrote the frame | one |

A reply approves the stage actually presented. Nothing is written to disk
before its approval: a spec the user has not read must not appear with their
name on the commit.

For each artifact, take the template and the rules from the engine:

```bash
bash .claude/sdd/sdd.sh openspec instructions <frame|specs|design|tasks> --change <id> --json
```

Use its `template`, `instruction` and `rules` as constraints; never copy them
into the file. If the CLI is unavailable, read
`openspec/schemas/sdd-proof/schema.yaml` and its `templates/` directly.

## 1. Frame

**Check what already exists in the repository.** `ls openspec/specs/`, then read
any capability that looks related, in full. If one covers the area, the change
**modifies** it -- two specs describing one feature is how they start
disagreeing.

**Challenge the build -- what exists outside the repository.** The loop turns a
request into requirements equally well whether or not the code should be this
project's. "Crawl a site, retry failures, resume after a stop" splits into
eleven clean requirements, and eleven cycles produce a hand-written crawler.
Nobody decides to build from scratch; the method does it unless this step asks:

> Not "how do I implement what was described?" -- **"what is the best
> engineering solution to the problem that was described?"**

When the request names a capability with an established category of tooling --
crawling, parsing, retries, scheduling, auth, vector stores, evaluation
harnesses, agent runtimes -- name two or three maintained options. For each,
say **what you checked** to call it maintained (a recent release, issues
answered, real adoption; WebSearch and WebFetch are for exactly this -- if you
could not check, say so), what it covers of the request, and the delta. The
extras the user listed are the delta to cover *on top of* an option, not the
reason to build one. Recommend one with the trade-off in a sentence -- a
dependency to own versus code to own -- and put the choice to the user. When
nothing established applies, say so in one line and move on; do not
manufacture a survey. The frame's `Existing options considered` slot records
the decision either way, so it is not re-litigated.

**Orchestration rung** (LLM work only): the lowest rung that expresses the
control flow a requirement needs -- one call, a tool loop, or a hand-written
graph. If `references/orchestration-ladder.md` exists, read it before choosing.

**Coverage screen.** Mark all nine rows Clear, Partial, Missing or N-A, with a
reason for every N-A. Most rows on most changes are N-A, and that is the
proportionality working. A Missing on a dimension the change touches becomes a
question or a requirement. `references/coverage-screen.md` has the questions
behind each row.

**Outcome.** Who benefits and what observable signal says it worked -- kept
apart from the requirements, which state behaviour.

## 2. Requirements

Ask, repeatedly: *what would I have to observe to say this is wrong?* Each
answer is a requirement: an **invariant**, not a description of a function.

| Not a requirement | A requirement |
|---|---|
| "The provider is resolved" | "The provider SHALL be chosen by override, then the environment, then the default" |
| "Handles missing keys" | "Only a provider that needs a credential SHALL be checked for one" |

**Classify each -- the determinism boundary.** Could `assert result == expected`
prove it? Then it is `deterministic`, and it almost certainly belongs in the
pure decision layer. If the honest answer is "well, roughly", it is
`evaluated`. Before accepting `evaluated`, try once to split it:
`references/splitting-rules.md`. The decision is deterministic; only the
judgement feeding it is evaluated. If everything is `evaluated`, the decisions
have not been separated from the generation yet -- go back.

**Ground each in scenarios with real values.** The normal case first, then
boundaries, then genuinely different outcomes. Several rows of one case read
better as a table inside one scenario. Every requirement gets at least one
scenario titled `Counter-example -- ...`: where it deliberately does not apply.
A requirement with only positive scenarios is usually a truism or two
requirements; on a threshold rule the counter-example *is* the off-by-one.
Talk in plain sentences while discovering; the scenario format is just how the
agreed cases get recorded.

**Name the proof now.** A deterministic requirement's Proved by line names its
test -- `tests/unit/test_providers.py::TestProviderPrecedence` -- at the lowest
tier that can prove it. The test
does not exist yet; `/accept` writes it next, and `sdd check` stays red until
it does. That red is the forcing function that stops a spec describing a
system nobody built.

**Evaluated: never invent a number.** Threshold, N and Agreed by are asked
for, or recorded OPEN with an Owner and a Review by date. A number you
invented becomes a gate, and is discovered to be arbitrary three changes later.

**Triage the unknowns.** A question a human can answer now -- a policy, a
preference, a threshold they hold an opinion on -- is asked with
`AskUserQuestion`, one at a time, with three or four concrete options drawn
from the scenarios and your recommendation first. A question whose answer does
not exist yet -- it needs data, a measurement, a run -- is recorded OPEN with
what would resolve it. An OPEN question a human could have answered in one
sentence is a cop-out dressed as rigour.

### Before showing anything: the checklist

- No two scenarios that differ only in a value. Two rows proving one case feel thorough and test one case.
- More than about eight requirements means the change is too big. Split it into changes.
- A requirement with no example is not understood yet. Ask for one.
- A scenario needing three paragraphs of setup means the design is wrong, or the requirement crosses a layer boundary.
- No requirement whose proof would assert generated prose.

### How it reads while the session runs

Plain, compact, nothing written yet:

```
Existing options: none -- a decision about this project's own configuration.

PROVIDER-PRECEDENCE: the provider is chosen by override, then the environment, then the default
  Kind:            deterministic -> tests/unit/test_providers.py::TestProviderPrecedence
  Scenario:        DEFAULT_PROVIDER=ollama with override openai -> openai
  Counter-example: override claude-x -> refused, listing the valid names
  Question:        should an unknown name fail, or warn and fall back?
```

On approval, write the delta at `specs/<capability>/spec.md` -- ADDED, or
MODIFIED with the **whole** existing block copied then edited, or REMOVED with
Reason and Migration -- then:

```bash
bash .claude/sdd/sdd.sh openspec validate <id> --strict
bash .claude/sdd/sdd.sh check
```

Expect `SDD003` for each named-but-unwritten test, and nothing else.

## 3. Design -- structural only

The how, with the alternatives considered. A decision expensive to reverse
also gets an ADR in `docs/decisions/`. If the rung is a hand-written graph,
fill the orchestration design: the node table is the contract.

## 4. Sequence -- tasks.md

An order and a critical path, never code. One group per requirement in
dependency order, the wiring point, and -- for more than one requirement -- the
**story test**: the acceptance test, driven through the real entry point, that
stays red until the last group lands.

## Report, then stop

Built or adopted, and the delta. How many requirements, the
deterministic/evaluated split, questions resolved versus left OPEN, and which
requirement `/accept` takes first. Do not start writing tests.

## When a requirement turns out wrong

Never edit the living spec in `openspec/specs/`. A wrong requirement is
amended by a change: a MODIFIED delta that says what changed and why, or a
REMOVED one with its migration. The disagreement between a requirement and
reality is the finding -- say which one you think is wrong, with the evidence,
and let the user decide.

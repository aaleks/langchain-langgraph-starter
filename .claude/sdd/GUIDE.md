# Guide -- one change, end to end

Read this once. It follows a single request through every stage, shows the
files that appear and the commands that run, and then the three shorter paths.

The request: *"the app should pick its chat model from a flag, then the
environment, then a default."*

## 1. `/intake` -- class it, say it, wait

There is no model selection in the repository yet, so this is not bounded --
bounded measures the repository, not familiarity. It is a new capability:
**structural**.

```
Class: structural -- a new capability, model-selection; nothing exists to amend.
Intent: every entry point resolves the same chat model the same way.
Stages: frame, specs, design, tasks, apply, verify, land.
Change id: add-model-selection
```

On "yes": `bash .claude/sdd/sdd.sh openspec new change add-model-selection`, and
`openspec/changes/add-model-selection/intake.md` records the class, the intent
and who approved them.

## 2. `/discover` -- frame

**Existing options considered.** Choosing between this project's own settings
is project-specific glue: one line saying so. (A crawler, a retry policy or a
vector store would get two or three maintained options, what was checked, the
delta, and a recommendation -- and the user would choose.)

**Orchestration rung:** N-A -- no model call is made by this capability.

**Coverage screen** -- nine rows, most of them N-A with a reason:

| Dimension | Mark | Note |
|---|---|---|
| Interfaces | Missing | a new `--model` flag and a `CHAT_MODEL` variable: both become contracts |
| Failure | Missing | what does a user see for an unknown model name? |
| Untrusted input | N-A | only this project's own configuration is read |
| ... | | |

The two Missing rows become a requirement and a question. The question -- fail,
or warn and fall back? -- is put to the user with `AskUserQuestion`, a
recommendation first. They choose: fail, listing the valid names.

Presented and approved; then `frame.md` is written.

## 3. `/discover` -- requirements

```
MODEL-PRECEDENCE: the model is chosen by flag, then CHAT_MODEL, then the default
  Kind:            deterministic -> tests/unit/test_model_selection.py::TestModelPrecedence
  Scenario:        CHAT_MODEL=small with --model large -> large
  Counter-example: --model "" -> refused: an empty flag is not "no flag"

MODEL-UNKNOWN-REFUSED: an unknown model name is refused, naming the valid ones
  Kind:            deterministic -> tests/unit/test_model_selection.py::TestUnknownModelRefused
  Counter-example: a known name in another case ("LARGE") -> accepted as large
```

Both are decisions, so both are `deterministic` and live in the pure decision
layer. Approved; the delta goes to `specs/model-selection/spec.md` under
`## ADDED Requirements`, opening with `## Purpose`. Then:

```bash
bash .claude/sdd/sdd.sh openspec validate add-model-selection --strict   # valid
bash .claude/sdd/sdd.sh check                                            # 2 x SDD003
```

The two SDD003s -- tests named but not written -- are the forcing function, not a
mistake: a spec cannot describe a system nobody built and stay green.

## 4. `/discover` -- design and sequence

`design.md` records the one decision worth recording -- the flag's name and the
variable's -- and `tasks.md` the order: MODEL-PRECEDENCE first (MODEL-UNKNOWN
refines it), wired into the CLI, with a story test in `tests/acceptance/` that
runs the entry point with `--model large` and reads the banner. It stays red
until the last group lands.

## 5. `/accept` then `/tdd`, one requirement at a time

`/accept MODEL-PRECEDENCE` writes the story test (red), then
`TestModelPrecedence` -- one test per scenario, the counter-example included --
and runs it: `ImportError`, nothing implements it yet. That is the right red.

`/tdd` takes one test to green with the least code, runs the whole suite, then
refactors, and **stops** with the next edge case it would take:
*"`--model` given twice -- last one wins, or refused?"* That question goes back
to the user; it is not decided inside a cycle.

Each requirement's box in `tasks.md` is ticked with the evidence that turned
it green. When the last one lands, the story test turns green.

## 6. `/verify` -- three lenses, fresh context

`[commands].check` runs fresh first. Then three agents in parallel: does each
test prove its requirement (both counter-examples asserted?), is the code wrong
anywhere no requirement looks, is each decision in the right layer. Findings are
capped and ranked; `verify.md` records SHIP or DO NOT SHIP and the evidence.

## 7. `/land` -- evidence, archive, integrate

```bash
bash scripts/check.sh                                              # fresh, read
bash .claude/sdd/sdd.sh openspec archive add-model-selection --yes
bash .claude/sdd/sdd.sh check                                      # living spec now claims the tests
```

The archive commit is the branch's last, so the living spec and the code land
together. Then the user chooses: open a PR, merge locally, or keep the branch.

## The shorter paths

**A defect** -- *"`--model " large"` with a leading space is refused."*
`/intake` says defect; `/debug` reproduces it, finds the cause (no trimming before
the lookup), and names the requirement that should have caught it:
MODEL-UNKNOWN-REFUSED, whose scenarios never tried whitespace. The change
MODIFIES it -- the whole block, plus a scenario. `/accept` writes the test that
reproduces the defect; `/tdd` fixes the cause. The defect is now a permanent
part of the living spec.

**A bounded change** -- *"list the valid names alphabetically."* It changes a flow
that exists: a brief frame, one MODIFIED requirement, tasks, prove, verify, land.
No design.md -- and the intake class says why.

**A spike** -- *"could the model list come from the provider's API instead?"*
`skip_specs: true`, a question, a probe with a time box, and a verdict in
`intake.md`: `kill -- every provider pages differently; a static list is
cheaper to own`. Archived, so the idea does not come back in three months
wearing a different sentence.

## What stops a shortcut

| Shortcut | What happens |
|---|---|
| a requirement with no test | `sdd check` fails: SDD002 or SDD003 |
| a test no requirement claims | `sdd check` fails: SDD006 |
| a requirement with only happy paths | `sdd check` fails: SDD007 |
| an evaluated requirement with an invented threshold | `/discover` and `/eval` refuse to invent one; an empty one fails SDD005 |
| an SDK imported into the decision layer | the edit guard refuses it; the architecture test fails |
| editing the expected answers to pass an eval | the edit guard refuses the write |
| editing the living spec by hand | the edit guard asks the user |
| a claim of "tests pass" with no run | the first law; `/land` runs the check itself |
| a test that does not prove its requirement | nothing mechanical -- `/verify`'s proof lens, and a reader |

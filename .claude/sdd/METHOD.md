# The method

Spec-driven development with proof, for projects that build on language
models. OpenSpec runs the lifecycle of specifications; this layer holds every
requirement to the test that proves it; a short list of laws keeps an agent
honest at every stage.

Everything else in this directory is an edit to one row of the tables below.

---

## 1. Four laws -- at every stage

1. **Evidence before claims.** Identify the command that proves a claim, run it
   fresh, read the output, then state the result with the evidence. It covers
   paraphrases, summaries, hand-offs and PR text. A subagent's "done" is a claim.
2. **Approval covers the stage actually presented.** Approving an idea does not
   approve artifacts that do not exist yet. Resume at the earliest incomplete stage.
3. **Report findings, fix nothing,** in any stage whose job is to look.
4. **One place holds the specification**: `openspec/specs/` (current truth) and
   `openspec/changes/` (in flight). No other spec, plan or design document.

## 2. Seven non-negotiables

If adopting a tool, a convention or a shortcut costs one of these, the shortcut
is wrong. `/verify` escalates a violation to BLOCKER by construction.

1. Traceability in both directions fails the build.
2. The determinism boundary: every requirement is `deterministic` or
   `evaluated`, and generated prose is never asserted.
3. Secrets and evaluation ground truth are never written by an agent.
4. Measure before asserting a threshold; report N beside every score.
5. Challenge the build before drafting a requirement.
6. Report findings and fix nothing, in a separate pass.
7. Prove a requirement at the lowest tier that can prove it.

## 3. The spine

```
INTAKE --+-- spike ------> probe --> verdict (go | clarify | kill) --> archive
         +-- defect -----> DEBUG --> frame (root cause) --> one requirement --> PROVE --> VERIFY --> LAND --> LEARN
         +-- bounded ----> frame (brief) --> specs --> tasks ----------------> PROVE --> VERIFY --> LAND
         +-- structural -> frame --> specs --> design (+ ADR) --> tasks ------> PROVE --> VERIFY --> LAND --> LEARN

         every class is one OpenSpec change; LAND archives it into the living spec
```

The class is said out loud, approved, and recorded in `intake.md`. **The ratchet
is one-way**: complexity found mid-change upgrades the class; nothing downgrades.
A stage skipped by class is skipped on the record -- which is what makes it a
method rather than a habit.

## 4. The stage contract

A stage is defined by what it consumes, what it produces, the gate it holds and
what enforces that gate. A stage whose output nothing consumes is ceremony; a
gate nothing enforces is a suggestion.

| Stage | Skill | Consumes | Produces | Gate | Enforced by |
|---|---|---|---|---|---|
| Intake | `/intake` | a request | `intake.md`: class, intent, approval | the human approves the class | the schema: nothing is ready before intake |
| Frame | `/discover` | the intake | `frame.md`: outcome, build-or-adopt, orchestration rung, coverage screen, questions | the human answers what is askable | required template slots |
| Debug (defect) | `/debug` | a symptom | the root cause and the requirement that should have caught it, in `frame.md` | root cause before any fix | the failing test must reproduce the defect |
| Specify | `/discover` | the frame | delta specs | the human approves the requirements as presented | `openspec validate --strict`; `sdd check` red until each test exists |
| Design (structural) | `/discover` | the frame | `design.md`, and an ADR for what is expensive to reverse | the human approves | conditional artifact, on the record via the class |
| Sequence | `/discover` | specs, design | `tasks.md`: order, wiring point, story test | the human approves the order | the story test stays red until the last group lands |
| Prove | `/accept`, `/tdd`, `/eval` | one requirement | a failing test, the least code to pass it, a refactor | red observed before green; one cycle per invocation | the suite, the architecture tests, the edit guards |
| Verify | `/verify` | a change whose tasks are all checked | `verify.md`: verdict, evidence, findings | SHIP needs zero BLOCKERs | three fresh-context lenses; escalation by construction |
| Land | `/land` | a verified change | the archive commit, then a PR or a merge | evidence run fresh | `[commands].check`, the same list CI runs |
| Learn | `/learn` | anything that went wrong | a requirement, check, guard, fixture, rationalisation row -- or "judgement, not automatable" | prose is the fallback, never the default | a fixture proving the new check catches the old failure |

`/quality` sits outside the spine: a repository-wide audit by the same auditors,
before a release or after a large slice.

## 5. Proportionality

| Stage | spike | defect | bounded | structural |
|---|---|---|---|---|
| intake | yes | yes | yes | yes |
| frame | -- | root cause | brief | full |
| specs | -- (`skip_specs`) | one requirement | amend or add | full |
| design | -- | -- | -- | yes, plus an ADR when irreversible |
| tasks | -- | yes | yes | yes, with a story test |
| prove | -- | yes | yes | yes, per requirement |
| verify | -- | yes | yes | yes |
| land | archive the verdict | yes | yes | yes |
| learn | if it changed a mind | always | if something went wrong | always |

## 6. The requirement

OpenSpec's container, with the proof inside it:

```markdown
### Requirement: PROVIDER-PRECEDENCE
The system SHALL choose the provider by explicit override, then the environment,
then the built-in default.

- **Kind:** deterministic
- **Proved by:** `tests/unit/test_providers.py::TestProviderPrecedence`

#### Scenario: Override beats the environment
| Given | Then |
|---|---|
| environment `ollama`, override `openai` | `openai` |

#### Scenario: Counter-example -- an unknown name is refused, not defaulted
- **GIVEN** the override `claude-x`
- **THEN** the call is rejected, listing the valid names
```

- **A stable id** -- `<CAPABILITY>-<RULE>`, upper kebab -- survives rewording,
  reordering and archive. Tests and reviews cite it.
- **`evaluated`** replaces a bare `Proved by` with `Threshold`, `N` and
  `Agreed by`. OPEN is legal; silence is not; a number is never invented.
- **Exceptions** -- `Status: NOT MET`, anything OPEN -- carry `Owner` and
  `Review by`. An exception without a date becomes furniture.
- **A counter-example** is mandatory: the case where the rule deliberately does
  not apply. On a threshold rule it is the off-by-one test that mutation tools
  most often fail to generate.

`sdd check` enforces six rules and nothing else: Kind declared; proof named and
resolvable; evaluated thresholds, N and agreement; every test file claimed;
a counter-example present; exceptions owned and dated. Anything more is a
template slot or a reader's judgement.

## 7. The determinism boundary

| Kind | When | Proved by |
|---|---|---|
| `deterministic` | `assert result == expected` could prove it | a test with exact assertions, usually on the pure decision layer |
| `evaluated` | only a judgement about generated text could | a scored check, marked `live`, against an agreed threshold and an N |

Before accepting `evaluated`, split once: the **decision** is deterministic, the
**judgement** feeding it is evaluated (presence vs correctness, shape vs
content, trigger vs output, policy vs prose). Most of an LLM application turns
out to be decisions; only the final text is generated.

## 8. Review

Three lenses, each with fresh context: **proof** (`spec-compliance`) -- does the
named test prove its requirement, every scenario included; **defects**
(`code-reviewer`) -- is the code wrong where no requirement looks; **placement**
(`architecture-guardian`) -- is each decision in the right layer. Findings are
BLOCKER, MAJOR or MINOR, capped at twenty, and a violated non-negotiable is a
BLOCKER whatever the lens called it. A lens that returned nothing returned
nothing; it did not say "clean".

## 9. Landing

Fresh evidence, then **archive inside the branch as its last commit**, then a
PR or a merge. The code and the living spec land together; the default branch
never carries a living spec claiming behaviour it does not have.

## 10. Learning

After anything goes wrong, exactly one output: a requirement, a check (with a
fixture reproducing the original failure), a guard, a fixture, a rationalisation
row in the skill that was bypassed -- or an explicit "judgement, not
automatable". Prose is the declared fallback. Logged in `docs/learnings.md`;
lessons that would help every project are marked upstream.

## 11. Whether it works

`sdd stats` reads, from files: the deterministic share of requirements; the
requirements amended (MODIFIED) and removed after implementation; defects that
amended an existing requirement versus added a missing one; and the stages each
intake class skipped. Cycles per requirement need session data and are reported
as not collected. A method change is argued from these, not from taste.

## 12. Three tiers

| Tier | What | Where | Changes when |
|---|---|---|---|
| universal | the laws, the requirement format, the stages, the checker | `.claude/sdd/`, skills, agents, `rules/sdd/`, hooks, the schema | the method releases |
| adapter | where specs and tests live; the project's commands; its ground truth | `sdd.toml` | the project's layout changes |
| project | its architecture, its packs' conventions, its lessons, its context | `CLAUDE.md`, `rules/project/`, `openspec/config.yaml` | the project decides |

A stack pack (`python`, `langgraph`) is universal for every project on that
stack. It may seed project-owned files and add rules to the settings install
seeds -- the langgraph pack's local-only runtime does both -- after which they
belong to the project. A place where the method had to be edited outside the
adapter to fit a project is a tier violation: record it, and move that thing
into the adapter or out of the method.

## 13. What was refused, and what waits

Refused, so they are not re-proposed: a second home for specifications (Spec
Kit's artifact set beside OpenSpec); plans that contain code; per-test metadata
in place of reading tests; worktrees and subagent-per-task as defaults; a
production-readiness block (the coverage screen replaced it); assurance profiles
(the intake classes replaced them). Deferred, each with the condition that
brings it back: `deferred-register.md`.

## 14. The card

```
INTAKE      class it, say it, record it; the class only ratchets up
  spike       a question -> probe -> go | clarify | kill. No requirement, no test.
  defect      reproduce -> root cause -> the requirement that should have caught it
  bounded     brief frame, amend or add, no design
  structural  the full graph, and an ADR for what is irreversible
FRAME       build or adopt (maintained options, the delta, who chose)
            coverage screen: nine rows, Clear / Partial / Missing / N-A + reason
SPEC        ADDED / MODIFIED / REMOVED; each requirement: SHALL, stable id, Kind,
            Proved by | Threshold + N + Agreed by, a counter-example scenario
SEQUENCE    order, wiring point, story test -- never code
PROVE       one requirement per cycle: red -> green -> refactor -> challenge -> stop
            evaluated -> /eval, never ==
VERIFY      proof | defects | placement, fresh context each; cap 20; fix nothing
LAND        evidence first; archive in the branch; then PR or merge
LEARN       a requirement, check, guard, fixture or row -- not a paragraph
ALWAYS      one place holds the spec; never assert generated prose;
            humans write secrets and ground truth; N beside every score
```

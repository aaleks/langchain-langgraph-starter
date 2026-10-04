---
name: verify
description: "Use when every task of a change is checked and it needs review before landing, or when asked whether a change is ready, correct, or still agrees with its requirements."
argument-hint: "<change-id>"
model: inherit
disallowed-tools: Edit, NotebookEdit
---

# /verify -- does the change prove what it claims, and is it right?

Change: $ARGUMENTS

Report findings; fix nothing. A finding acted on in the same pass is a finding
nobody reviewed. `Edit` is removed while this skill runs; `Write` stays for one
file only -- the change's `verify.md`.

## 0. Preconditions

`bash .claude/sdd/sdd.sh status` -- every task in the change's tasks.md is
checked. If not, stop: the change is still in apply.

## 1. Evidence -- run it fresh

Run `[commands].check` from `sdd.toml` now, in this session, and read the
output: exit code, counts, failures. Earlier runs, a subagent's summary, and
"it passed a minute ago" are not evidence. Any failure is a BLOCKER: record it,
skip the lenses, write the verdict.

## 2. Three lenses, fresh context each -- in parallel

Issue the three `Agent` calls **in one message**. Give each the change id, its
requirement ids (from the delta specs), and the diff range
(`git merge-base HEAD <base>`..HEAD). Never your session history: a fresh
reviewer sees the work product, not your reasoning about it.

| Lens | Agent | The question |
|---|---|---|
| proof | `spec-compliance` | Does each named test prove its requirement -- every scenario, counter-example included? Is there behaviour in the diff that no requirement claims? |
| defects | `code-reviewer` | Is the code wrong in a way no requirement mentions? |
| placement | `architecture-guardian` | Is each decision in the right layer, and does every boundary hold? |

When the diff touches graphs, tools or checkpointers and the langgraph pack is
installed, add `graph-architecture-guardian` and `agent-capability-auditor` to
the same message.

## 3. What you check yourself

Cheap, and best done holding the change in one head:

- **Exceptions still accurate.** Every OPEN and NOT MET in the change: still
  unmet, still wanted, owner and review date sensible?
- **Determinism honest.** A `deterministic` requirement whose test hedges --
  `assert "sunny" in answer` against a real model -- is misclassified.
- **Interfaces.** A new environment variable, flag, default or user-visible
  message in the diff with no requirement behind it is code-to-spec drift.
- **The frame.** A capability with established tooling and no `Existing options
  considered` decision is a build nobody chose.

## 4. Consolidate

- Merge duplicates across lenses; keep the most specific location.
- Severity: **BLOCKER** stops the land, **MAJOR** must be fixed or explicitly
  accepted by the user, **MINOR** is recorded.
- **Escalation is by construction, not judgement.** A violation of any
  non-negotiable is BLOCKER whatever a lens called it:
  1. traceability holds in both directions (`sdd check` green);
  2. no test makes a real model call by default, and none asserts generated prose;
  3. secrets and evaluation ground truth were not written by an agent -- a change
     to golden data needs the user to confirm they wrote it;
  4. no score without its N, no threshold that was invented;
  5. a capability with established tooling went through build-or-adopt;
  6. this review fixed nothing;
  7. each requirement is proved at the lowest tier that can prove it.
- **Cap at twenty findings**, most severe first; summarise the rest in one line.
  A forty-finding report is not read.
- A lens that returned nothing returned nothing -- write "no findings", never
  "clean". Those differ, and the second is a claim the silent lens did not make.

## 5. Write verify.md -- the one file this skill writes

From `openspec/schemas/sdd-proof/templates/verify.md`: verdict, the commit sha
reviewed, the evidence (each command and what it printed), the findings, and
**Not checked** -- every lens or check that did not run, and why.

**SHIP** only with zero BLOCKERs and every MAJOR either fixed or accepted by the
user in writing. Otherwise **DO NOT SHIP**, and the single most important fix.

## Report

One line: SHIP or DO NOT SHIP, and the first thing to fix. Then the counts per
severity and what was checked. "No drift across 4 requirements, 3 lenses and
the full check" is a result; "looks good" is not -- and never invent a finding
to look thorough.

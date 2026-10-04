---
name: quality
description: "Use when a release is near, a large slice has landed, or someone asks for a repo-wide audit of whether the specs, the architecture and the tests' strength still hold -- not for reviewing one change."
argument-hint: "[--mutation] [--determinism] [--observability] [--graphs]"
model: inherit
disallowed-tools: Edit, NotebookEdit
---

# /quality -- one report from the auditors, across the whole repository

Options: $ARGUMENTS

`/verify` reviews one change before it lands. This audits everything that has
landed: independent agents, fresh context each, and a persisted report. Report
findings; fix nothing. `Write` stays for one file only -- `quality-report.md`.

## Gate 0 -- the mechanical checks, once

```bash
bash .claude/sdd/sdd.sh check
```

and `[commands].architecture` from `sdd.toml`. Running them here once saves
each agent rediscovering a red suite. If either fails, stop and report -- but
say **which** red, because two of them mean opposite things:

| What failed | Means | Severity |
|---|---|---|
| a named test does not exist, named by an in-flight change | mid-loop: `/discover` named it, `/accept` has not written it | **Expected** -- name the requirements and stop; do not escalate |
| a named test does not exist, named by the living spec | the living spec claims a test that is gone | **Critical** |
| a test file no requirement claims | behaviour exists that nothing describes | **Critical** |
| an architecture contract | a boundary was crossed | **Critical** |

Reporting the first row as a defect trains people to ignore the check -- the one
outcome that makes it worthless.

## The auditors -- independent, so in one message

Always: `spec-compliance` (every living requirement: COVERED / PARTIAL / MISSING
with the file and line that justify it) and `architecture-guardian` (VIOLATION /
WARNING / NOTE, especially what the contracts cannot see: a decision in an
adapter, an exit below the entry point).

Opt-in, by cost:

| Flag | Agent | Why opt-in |
|---|---|---|
| `--mutation` | `mutation-analyst` | runs `[commands].strength`: minutes, not seconds |
| `--determinism` | `determinism-auditor` | cheap; pass it whenever tests changed |
| `--observability` | `observability-auditor` | when entry points, logging or tracing changed |
| `--graphs` | the langgraph pack's four auditors | when graphs, tools or checkpointers exist |

A flag not passed is recorded under **Not checked** with the command that would
run it. Silence would read as "no findings".

## Severity -- one table, so reports stay comparable

| Source | Its label | Report as |
|---|---|---|
| gate 0 | contract failed, unclaimed test, living spec names a missing test | **Critical** |
| spec-compliance | MISSING | **Critical** |
| architecture-guardian | VIOLATION | **Critical** |
| determinism-auditor | any finding | **Critical** |
| any | a violated non-negotiable (.claude/sdd/METHOD.md) | **Critical**, by construction |
| spec-compliance | PARTIAL | **Major** |
| architecture-guardian | WARNING | **Major** |
| mutation-analyst | survivor in a function a requirement relies on | **Major** |
| mutation-analyst | other survivor in the decision layer | **Minor** |
| architecture-guardian | NOTE | **Minor** |
| spec-compliance | COVERED | **Informational** -- count them, never list them |

## Output -- quality-report.md at the repository root

Overwrite it: it is generated and gitignored, and a stale one is worse than none.

```markdown
# Quality report

> /quality on <branch> at <sha> -- steps run: ... -- steps skipped: ...

## Verdict
<one sentence; "clean" only if every step ran and returned nothing>

## Critical | Major | Minor | Informational
| # | Finding | Where | Source |

## Coverage
| Capability | Requirements | Covered | Partial | Missing |

## Not checked
<every step skipped, and the command that would run it -- never empty unless all ran>
```

## Rules

1. **Never fix.** Every agent here is read-only, and so is this.
2. **Never invent a severity** an agent did not give. Your own observations go
   under Informational, labelled as yours.
3. **An agent that returns nothing returned nothing** -- never "clean".
4. **A skipped step goes in Not checked.** What is not done is recorded, not omitted.
5. **The verdict reads in one line.** If someone must read the tables to know
   whether to ship, the verdict failed.

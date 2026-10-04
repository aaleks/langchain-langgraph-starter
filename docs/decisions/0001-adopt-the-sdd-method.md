# 1. Adopt the merged SDD method: OpenSpec for the lifecycle, our layer for the proof

Date: 2026-10-04
Status: Accepted

## Context

The method this starter adopts was built in a LangChain playground and then
reviewed three times against the projects occupying the same ground --
OpenSpec, Superpowers and Spec Kit. The reviews converged on one shape: the
playground's method owns *proof* (requirement-to-test traceability failing the
build, the determinism boundary, guards, auditors) and lacks *lifecycle*
(nothing for a requirement that turns out wrong) and *flow* (no intake, no
defect lane, no review stage, no landing, no learning). Its `sdd/` and `.claude/`
copies had drifted apart, and the copy that ran was weaker than the one that shipped.

Before deciding, the external pieces were verified rather than assumed:

- **OpenSpec 1.14** was installed and run. The extended requirement format --
  `Kind`, `Proved by`, thresholds, a counter-example scenario -- passes
  `validate --strict`, and `archive` preserves every one of those fields
  verbatim. The final review's kill criterion "archive loses a Proved by link"
  does not fire. A forked schema carries the stage graph; there is no per-change
  conditional artifact, so proportionality lives in the artifacts' instructions
  and in `skip_specs`.
- **Superpowers 6.4** switches itself on at session start; its brainstorming
  writes design documents to `docs/superpowers/specs/` -- a second place for a
  specification -- and it defaults to worktrees and plans containing code.
  Claude Code's cloud sessions do not install plugins a repository declares.
- **Claude Code itself** changed under the old method: a skill's `allowed-tools`
  pre-approves rather than restricts; a Stop hook's stdout and any exit-0
  stderr never reach Claude.

## Decision

Four choices, each made by the project owner from presented options:

| Question | Chosen | Rejected, and why |
|---|---|---|
| Spec engine | **OpenSpec CLI as the engine only**, pinned, telemetry off; our skills are the single front door | OpenSpec's generated `/opsx` skills alongside ours: two front doors, a task loop that fights one-cycle `/tdd`. No engine: re-implementing archive is what "challenge the build" forbids |
| Superpowers | **Self-contained**: its best ideas adapted into our skills, credited | Requiring the plugin: absent in cloud sessions; auto-triggered flows that create a second spec location |
| First version | **The method plus a walking skeleton** with every check live and green | Method only: the layer rules would check nothing. A worked example: it would encode product choices not yet made |
| Tooling | **Bash hooks and a Python checker** -- standard library only, so any project with a Python 3.11+ runs it | Node: one less prerequisite where OpenSpec is used, but a language the owner does not maintain |

## Consequences

**Good.** A requirement that turns out wrong now has a procedure -- a MODIFIED or
REMOVED delta, reviewed and archived. The stage contract is executable by
OpenSpec. A defect becomes a permanent requirement. The method checks itself
through its own specs and 21 fixtures, and is distributed by a manifest that
refuses to drift.

**Costly.** Node 20.19+ for OpenSpec, Python 3.11+ for the checker, bash for the
hooks -- three runtimes, chosen deliberately. Four vocabularies merged into one
means more to read the first time. Every change is an OpenSpec change, though a
bounded one is three short files.

**Kill criteria**, kept from the final review: stop and return to the plain
loop if the checker cannot enforce its rules without knowing the test
framework, if archive loses a `Proved by` link, or if a bounded change takes
more steps than it did before. The first two are tested; the third is measured
by `sdd stats` over the first changes.

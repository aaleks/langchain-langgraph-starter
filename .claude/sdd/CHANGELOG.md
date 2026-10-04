# Changelog

The SDD method's own history -- one changelog for the method and its docs.
Every shipped file is listed in `manifest.json`; `sdd.sh manifest --check`
fails when one changes without the version moving and an entry here.

## 0.2.0 -- 2026-10-04

The merged method: OpenSpec runs the lifecycle; this layer carries the proof.
First release in its own home, and successor to the `sdd/` toolkit 0.1.0 of the
project the method was built in (see README, "Where this came from").

### Added

- **OpenSpec as the engine**, pinned at 1.14.0 with telemetry off, through
  `sdd.sh openspec`. The `sdd-proof` schema makes the stage contract executable:
  intake -> frame -> specs (+ design) -> tasks -> verify, with required-slot
  templates and each stage's invariants injected where they apply.
- **Intake classes** -- spike, defect, bounded, structural -- said out loud,
  ratcheting only upward, and recorded, so the stages each class skipped can be
  counted.
- **The extended requirement format**: a stable upper-kebab id, `Kind`,
  `Proved by`, `Threshold` / `N` / `Agreed by`, `Owner` / `Review by` on every
  exception, and a mandatory counter-example scenario.
- **The proof checker** -- Python standard library only, any stack: six closed
  rules, deltas and the adapter checked, OpenSpec's diagnostic envelope, and 21
  fixtures -- 17 that must go red, 4 counter-examples that must stay green.
- **New stages**: `/intake`, `/debug` (root cause first; a defect becomes a
  requirement), `/land` (evidence, archive inside the branch, then integrate),
  `/learn` (every failure leaves a check, guard, fixture or requirement behind).
- **`/verify` as three fresh-context lenses** -- proof, defects, placement -- with
  findings capped and a violated non-negotiable escalated by construction; the
  new `code-reviewer` agent is the defects lens.
- **Four laws and seven non-negotiables**, loaded in every session from
  `.claude/rules/sdd/laws.md`.
- **The frame**: build-or-adopt and a nine-row coverage screen as required slots.
- **Packs**: `python` (layer rules) and `langgraph` (the orchestration ladder,
  graph rules, and four auditors: graph architecture, durability, agent
  capabilities, graph evaluation).
- **Distribution**: a manifest of every shipped file with its pack and hash;
  `install` that never overwrites; `update` that replaces only what a project
  never touched; `manifest --check` for the canonical repository.
- **`sdd stats`** -- method health read from files -- and a SessionStart hook that
  says where each in-flight change stands.

### Changed

- Specs moved from numbered `docs/specs/NNN-*.md` files with positional rule ids
  to OpenSpec capabilities with stable ids, changed through deltas.
- Every skill description says **when** to use it, never how it works.
- Read-only stages use `disallowed-tools`. In current Claude Code a skill's
  `allowed-tools` pre-approves tools; it never restricted them, so the previous
  "this skill cannot edit" claims were false.
- Hook messages now reach their reader: the Stop hook reports through
  `systemMessage` and the prompt note through `additionalContext`. Plain stdout
  from a Stop hook, and stderr from any hook that exits 0, never left the debug log.
- Agents are pinned by model alias (`opus`) and skills `inherit` the session's
  model, so no version-numbered id can go stale in one tree and not another.

### Retired

- The dual `sdd/` and `.claude/` trees, the hand-maintained spec index and
  status vocabulary, and `/discover` writing numbered spec files.

# Changelog

The SDD method's own history -- one changelog for the method and its docs.
Every shipped file is listed in `manifest.json`; `sdd.sh manifest --check`
fails when one changes without the version moving and an entry here.

## 0.3.0 -- 2026-10-05

LangGraph on the developer's machine only, and the langgraph pack's
production rules. Measured before written: with `langgraph-cli 0.4.32` and
`langgraph-api 0.15.1`, the development server reaches LangSmith in ways
tracing switches do not stop. The evidence is in the change
`langgraph-local-runtime`, archived with this release.

### Added

- **`seeds/serve.sh`, seeded as `scripts/serve.sh` by the langgraph pack** --
  the one way to start the development server. It binds 127.0.0.1, opens no
  browser, passes on an allowlist of flags (`--host`, `--tunnel` and
  `--studio-url` are refused), and starts the server from the local-only
  environment:
  - tracing off through all four switches;
  - every LangSmith credential empty;
  - the LangSmith endpoint at a closed local port;
  - the CLI's analytics and version check off.

  It refuses a `langgraph.json` `env` key, and a `.env` that sets a LangSmith
  credential or switches tracing on -- naming the variable, never its value.
  Requirements `LOCAL-SERVE-LOOPBACK`, `LOCAL-SERVE-ENVIRONMENT` and
  `LOCAL-SERVE-REFUSALS`.
- **`seeds/settings.langgraph.json`**, merged into the settings install seeds.
  The agent runs in the same local-only environment, and is denied
  `smith.langchain.com`, `--studio-url`, `--tunnel`, `langgraph deploy`,
  `langgraph up`, and every way of starting the server but the wrapper. Each
  deny rule is proved load-bearing. Requirement `LOCAL-AGENT-SETTINGS`.
- **Pack seeds in install**: a pack seeds its own files, and adds `env` and
  `permissions` rules to the settings being seeded -- never to settings a
  project already has, which are reported for a merge by hand. A merge that
  would drop or override a key is refused before anything is written.
  `update` reports a pack seed the project lacks. Requirement `DIST-PACK-SEEDS`.
- **`rules/langgraph/runtime.md`**: the local server, what replaces Studio
  (`draw_mermaid()` text, the local API, route tests), and how to re-measure
  at every upgrade that nothing leaves the machine.
- **`skills/accept/references/graph-routes.md`** (langgraph pack): what a test
  of a graph's route asserts -- nodes visited, terminal outcome, interrupt and
  resume on the same thread, an exhausted budget -- with a scripted fake model.
- **The design record gains** a Kind column on the node table (read, decide,
  write), and slots for identity, errors by class, streaming, observability,
  runtime and the test plan. Persistence now asks for encryption and retention.

### Changed

- **`rules/langgraph/graphs.md`**: where things go (the source and test trees);
  read, decide and write nodes; an error-class table with one handling per
  class; the subgraph criterion; persistence ownership, encryption, strict
  deserialisation and retention; the test tier for each claim.
- **The four langgraph auditors** check what the rules now say:
  - graph architecture: no `env` in `langgraph.json`, and the runtime stays
    local;
  - durability: rebuild-and-resume as the proof of durability, ownership and
    encryption;
  - graph evaluation: error classes and topology against design.md;
  - agent capabilities: no tool reaching a host the design did not name.
- `/accept` points at the graph-route reference when it exists, as `/discover`
  does for the ladder, instead of carrying LangGraph detail in a core skill.
- **The edit guard asks** before a write to `scripts/serve.sh` or to
  `.claude/sdd/seeds/`, as it does for `scripts/check.sh` -- the local-only
  runtime is enforcement too. Requirement `GUARD-ASK`, amended.
- `lib.sh` declares its shell for shellcheck, which now runs clean on every
  script when each is checked on its own.

### Fixed

- **`sdd status` honours `skip_specs: true`** in a change's `.openspec.yaml`,
  as `openspec status` does. A change declaring it was reported as stuck at
  `specs`. Requirement `HOOKS-NEXT-STAGE`, amended.

### Upgrading from 0.2.0

`update` brings the shipped files. With the langgraph pack:

1. Run `install` again with the same packs to seed `scripts/serve.sh`.
2. Merge the `env` and `deny` entries of `seeds/settings.langgraph.json` into
   `.claude/settings.json` by hand.

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

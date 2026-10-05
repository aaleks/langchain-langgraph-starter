# Sequence

- **Order:** the two guard rules first, each test-first. They are the only
  behaviour here that a test can prove. The prose follows the gap trace in
  `frame.md`, a file at a time, and the release closes the change.
- **Wiring point:** the PreToolUse hook, `.claude/hooks/guard-edits.sh` --
  already wired in the seeded settings.
- **Story test:** N-A. Each requirement's only observable behaviour is the
  hook's answer to one payload, so its own test is the story test.

## 1. GUARD-RUNTIME-DATA

- [x] 1.1 /accept GUARD-RUNTIME-DATA -- red for the right reason
  (`AssertionError: 2 != 0` for `.langgraph_api/...` and each store: allowed, not refused; the counter-example green already)
- [x] 1.2 /tdd -- every scenario, counter-example included, asserted and green
  (guard rule 4; `test_hooks.py`: 31 tests OK)

## 2. GUARD-SERVER-CONFIG

- [x] 2.1 /accept GUARD-SERVER-CONFIG -- red for the right reason
  (`AssertionError: 2 != 0` for both env writes; removing the key and a config without it green already)
- [x] 2.2 /tdd -- every scenario, counter-example included, asserted and green
  (guard rule 7, judging only the new text; `test_hooks.py`: 31 tests OK)

## 3. Routes are named where requirements are written

- [x] 3.1 The schema's specs instruction, `/discover`'s requirements step, and a route checklist in the orchestration ladder
  (`openspec schema validate sdd-proof`: valid; `openspec instructions specs` on a probe change prints the route rule at lines 66-71)
- [x] 3.2 `accept/references/graph-routes.md` points at the checklist

## 4. The pack's rules against the source plan

- [x] 4.1 `graphs.md`: the source tree; memory apart from execution state; node boundaries; errors; tools; persistence; seven test layers; vertical slices; Deep Agents
- [x] 4.2 The ladder: the middleware with its defaults (langchain 1.4.3), Deep Agents' place, build order
  (defaults read from the installed classes: both retries `on_failure="continue"`; both limits `run_limit=None`; `exit_behavior` `"end"` and `"continue"`)
- [x] 4.3 The auditors, and `/verify` adding the durability and graph-evaluation auditors
- [x] 4.4 The frame template's non-goals; the design template's Runtime and Test plan slots
  (`openspec schema validate sdd-proof`: valid)

## 5. The project

- [x] 5.1 Roadmap slices 1, 3 and 4; the architecture overview's tree; the OpenSpec context
  (`openspec validate --all --strict`: 1 passed)
- [x] 5.2 Release: VERSION 0.4.0, CHANGELOG, manifest; the full check passes (`[commands].check` in sdd.toml)
  (manifest: 107 files at 0.4.0; `bash scripts/check.sh`: all checks passed -- 117 method tests, 35 method requirements traced, suite 30 passed and 3 skipped; shellcheck clean)

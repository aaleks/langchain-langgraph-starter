# Intake

- **Class:** bounded, `skip_specs: true`
- **Intent:** For whoever runs the checks: `bash scripts/check.sh` and the
  commands in `sdd.toml` run pytest as `uv run python -m pytest`, so the one
  list of checks runs on a machine whose Application Control refuses the
  `pytest.exe` launcher -- the owner's, since 2026-10-16 ("An Application
  Control policy has blocked this file. (os error 4551)").
- **Because:** it changes how an existing flow -- the check script and the
  method's adapter -- starts the same tool; no requirement, test, interface or
  output moves, and the suite proves it by running.
- **Approved:** the agent, under the owner's standing delegation to run each
  cycle unattended (2026-10-15); a tooling change with no behaviour change, no
  significant decision.

## Scope

- `scripts/check.sh`: its three `uv run pytest` lines.
- `sdd.toml` `[commands]`: `suite`, `test`, `architecture`, `live`.
- Not the method's seeds (`.claude/sdd/seeds/`): a launcher refused by one
  machine's policy is this project's, not every project's.
- Not `CLAUDE.md`'s command list: `uv run pytest` is still the command a
  person types on most machines; one line says what to use where it is
  refused.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

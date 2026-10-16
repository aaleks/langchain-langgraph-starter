# Tasks

No requirement moves (`skip_specs: true`): the proof is the full check run on
this machine and on CI.

## 1. The commands

- [x] 1.1 `scripts/check.sh`: architecture, suite and live run as
  `uv run python -m pytest`, with one comment saying why
- [x] 1.2 `sdd.toml` `[commands]`: `suite`, `test`, `architecture` and `live`
  the same
- [x] 1.3 `CLAUDE.md`'s command list: one line for a machine that refuses the
  launcher

## 2. Proof

- [x] 2.1 `bash scripts/check.sh` ends `all checks passed` on this machine
- [x] 2.2 `bash scripts/check.sh live` passes here
- [ ] 2.3 CI's check passes on the pull request

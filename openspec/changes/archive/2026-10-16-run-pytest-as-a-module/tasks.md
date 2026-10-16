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

- [x] 2.1 `bash scripts/check.sh` ends `all checks passed` on this machine:
  suite 494
- [x] 2.2 `bash scripts/check.sh live` run here: **fails 1 of 14** --
  `tests/acceptance/agents/test_openwebui_live.py::TestAnsweredByOpenWebUI`,
  the owner's Open WebUI answering `401 Your API key has been invalidated`;
  the other 13 pass. Not this change: the credentials in `.env` are the
  owner's, and the same test passed on 2026-10-16 before them
- [x] 2.3 CI's check passes on the pull request: #15, Linux, pass

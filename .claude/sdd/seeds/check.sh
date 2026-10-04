#!/usr/bin/env bash
# Every check that must pass, in one place. A terminal, CI and /land all run
# this script, so the list of checks cannot drift between them. (The Stop hook
# runs only the fast traceability step -- `sdd.sh check` -- at the end of a turn;
# this is the complete list.)
#
#   bash scripts/check.sh          the default build: no services, no keys, no quota
#   bash scripts/check.sh live     also the tests that need services, models or quota
#
# Stops at the first failure, so a CI log ends at the thing that broke.

set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s ==\n' "$1"; }

step "format"
uv run ruff format --check .

step "lint"
uv run ruff check .

step "architecture: layers, allowlists, conventions"
uv run pytest tests/architecture -q

step "specs: OpenSpec structure"
bash .claude/sdd/sdd.sh openspec validate --all --strict

step "specs: requirement <-> test traceability"
bash .claude/sdd/sdd.sh check

step "the method: its own tests, fixtures and specs"
bash .claude/sdd/sdd.sh selftest
bash .claude/sdd/sdd.sh check --config .claude/sdd/self.toml


step "suite"
uv run pytest -q

if [ "${1:-}" = "live" ]; then
  step "live: real services and models"
  uv run pytest -m live -q
fi

printf '\nall checks passed\n'

#!/usr/bin/env bash
# The one entry point for the method's tooling.
#
#   bash .claude/sdd/sdd.sh check            requirement <-> test traceability
#   bash .claude/sdd/sdd.sh status           where each in-flight change stands
#   bash .claude/sdd/sdd.sh openspec <args>  the pinned OpenSpec CLI
#   bash .claude/sdd/sdd.sh selftest         the method's own tests and fixtures
#   bash .claude/sdd/sdd.sh help             everything else
#
# Bash finds the interpreter so that hooks, CI and a terminal all run the same
# thing on Linux, macOS and Windows (Git Bash). The Python side is standard
# library only; the OpenSpec side needs Node >= 20.19.

set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pinned: the release this method was verified against. Keep in step with
# OPENSPEC_VERSION in sddlib/__init__.py -- a test fails if the two disagree.
OPENSPEC_VERSION="1.14.0"

# A Python >= 3.11 that actually runs. `python3` first; then `python`, because on
# Windows `python3` may be the Store stub that only prints an install hint; then
# uv, which can fetch one. SDD_PYTHON overrides all of it.
find_python() {
  if [ -n "${SDD_PYTHON:-}" ]; then
    printf '%s\n' "$SDD_PYTHON"
    return 0
  fi
  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if command -v uv >/dev/null 2>&1; then
    printf '%s\n' "uv run --no-project --quiet python"
    return 0
  fi
  return 1
}

command="${1:-help}"

case "$command" in
  openspec)
    shift
    if ! command -v npx >/dev/null 2>&1; then
      echo "sdd: OpenSpec needs Node >= 20.19 and npx (https://nodejs.org)." >&2
      echo "     The proof checker does not: 'sdd.sh check' still works." >&2
      exit 127
    fi
    # Telemetry off: a method should not report on the projects that use it.
    export OPENSPEC_TELEMETRY=0
    exec npx --yes "@fission-ai/openspec@${SDD_OPENSPEC_VERSION:-$OPENSPEC_VERSION}" "$@"
    ;;
esac

if ! py="$(find_python)"; then
  echo "sdd: no Python >= 3.11 found (tried python3, python, uv). Set SDD_PYTHON." >&2
  exit 127
fi
read -r -a python_cmd <<<"$py"

case "$command" in
  selftest)
    shift
    # From inside .claude/sdd, `python -m` puts this directory on sys.path (so
    # sddlib imports) and -t makes tests/ the top level (so the helpers do).
    cd "$here"
    exec "${python_cmd[@]}" -m unittest discover -s tests -t tests "$@"
    ;;
  help|-h|--help)
    exec "${python_cmd[@]}" "$here/sdd.py" --help
    ;;
  *)
    exec "${python_cmd[@]}" "$here/sdd.py" "$@"
    ;;
esac

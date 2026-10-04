#!/usr/bin/env bash
# SessionStart hook: tell Claude where each in-flight change stands, so a new
# session resumes at the earliest incomplete stage instead of re-deriving it --
# or skipping one. Plain stdout from SessionStart becomes context.
# Prints nothing when no change is in flight.

set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$here/lib.sh"
cd "$(project_dir)" || exit 0

if out="$(bash .claude/sdd/sdd.sh status --brief 2>&1)"; then
  [ -n "$out" ] && printf '%s\n' "$out"
else
  printf 'SDD: change status unavailable -- %s\n' "$(printf '%s\n' "$out" | head -n 1)"
fi
exit 0

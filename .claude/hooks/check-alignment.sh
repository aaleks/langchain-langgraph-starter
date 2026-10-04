#!/usr/bin/env bash
# Stop hook: when a turn ends with files changed, say whether specs and tests
# still agree.
#
# Advisory. It tells the user through systemMessage -- plain stdout from a Stop
# hook reaches only the debug log -- and never blocks or forces another turn:
# mid-loop red is expected (/discover names a test before /accept writes it),
# and a hook that made Claude keep going would fight the skills that say stop.
# Silent when everything agrees.

set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$here/lib.sh"
cd "$(project_dir)" || exit 0

# Nothing changed since the last commit: nothing new to check.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  exit 0
fi

out="$(bash .claude/sdd/sdd.sh check 2>&1)"
status=$?
[ "$status" -eq 0 ] && exit 0

if [ "$status" -eq 1 ]; then
  errors="$(printf '%s\n' "$out" | grep -E '^  error' | head -n 5 | sed -E 's/^  error +//')"
  message="$(printf 'SDD drift -- %s\n%s\nRun: bash .claude/sdd/sdd.sh check' "$(printf '%s\n' "$out" | head -n 1)" "$errors")"
else
  message="SDD: the proof checker could not run -- $(printf '%s\n' "$out" | head -n 1)"
fi
printf '{"systemMessage":%s}\n' "$(json_string "$message")"
exit 0

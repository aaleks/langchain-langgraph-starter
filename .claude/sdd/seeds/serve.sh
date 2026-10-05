#!/usr/bin/env bash
# The local LangGraph development server -- the one way this project starts it.
#
#   bash scripts/serve.sh [--port N] [--no-reload] [--allow-blocking]
#                         [--wait-for-client] [--server-log-level LEVEL]
#                         [--n-jobs-per-worker N] [--debug-port N]
#
# Local only, by construction (docs/decisions/0004-langgraph-runs-locally.md):
#
#   - bound to 127.0.0.1, and no browser: Studio is LangSmith's web app, and
#     `langgraph dev` opens it by default;
#   - started from the local-only environment below, whatever this shell
#     exports. Measured with langgraph-cli 0.4.32 / langgraph-api 0.15.1:
#     with any LangSmith key present the server reports usage to
#     api.smith.langchain.com even with tracing off, and tracing switched on
#     sends every run there even with no key at all;
#   - refused when langgraph.json or .env would put any of that back.
#
# The in-memory server is for development. Its threads live in .langgraph_api/
# (gitignored), and it proves nothing about durability.
#
# Seeded by the SDD method's langgraph pack; project-owned from then on.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

refuse() {
  printf 'serve: %s\n' "$*" >&2
  exit 2
}

config="langgraph.json"
[ -f "$config" ] || refuse "no $config here -- nothing to serve until a graph is registered (docs/roadmap.md)."

# The server loads langgraph.json's "env" over its own environment, which would
# undo everything below. The graphs get their settings from config/ instead.
flat="$(tr -d '\r\n' < "$config")"
if grep -Eq '"env"[[:space:]]*:' <<< "$flat"; then
  refuse "$config has an \"env\" key, which the server loads over the local-only environment. Remove it: config/ loads .env for the graphs."
fi

# .env must not put LangSmith back either -- a loader that overrides would undo
# the environment below. Names are reported; values are never printed.
credentials='LANGSMITH_API_KEY|LANGCHAIN_API_KEY|LANGSMITH_CONTROL_PLANE_API_KEY|LANGGRAPH_CLOUD_LICENSE_KEY'
tracing='LANGSMITH_TRACING|LANGSMITH_TRACING_V2|LANGCHAIN_TRACING_V2|LANGCHAIN_TRACING'
if [ -f .env ]; then
  found="$(sed -nE \
    -e "s/^[[:space:]]*(export[[:space:]]+)?($credentials)[[:space:]]*=[[:space:]]*['\"]?[^'\"[:space:]#].*/\\2/p" \
    -e "s/^[[:space:]]*(export[[:space:]]+)?($tracing)[[:space:]]*=[[:space:]]*['\"]?(true|True|TRUE|1)(['\"[:space:]#].*)?$/\\2/p" \
    .env | sort -u | tr '\n' ' ')"
  if [ -n "$found" ]; then
    refuse ".env sets ${found% } -- LangSmith never reaches this server. Remove it (its value was not printed)."
  fi
fi

# Flags: an allowlist. Anything that would expose the server or name a Studio
# origin -- --host, --tunnel, --studio-url -- is refused, never passed on.
port=2024
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --no-reload | --allow-blocking | --wait-for-client)
      args+=("$1") ;;
    --port)
      [ $# -ge 2 ] || refuse "--port needs a value."
      port="$2"
      shift ;;
    --port=*)
      port="${1#--port=}" ;;
    --server-log-level | --n-jobs-per-worker | --debug-port)
      [ $# -ge 2 ] || refuse "$1 needs a value."
      args+=("$1" "$2")
      shift ;;
    --server-log-level=* | --n-jobs-per-worker=* | --debug-port=*)
      args+=("$1") ;;
    *)
      refuse "${1%%=*} is not passed to the server: local only (docs/decisions/0004-langgraph-runs-locally.md). Allowed: --port, --no-reload, --allow-blocking, --wait-for-client, --server-log-level, --n-jobs-per-worker, --debug-port." ;;
  esac
  shift
done

# The local-only environment -- the same twelve variables as the agent's
# settings (.claude/settings.json "env"):
#   - tracing off through all four switches: the server reads LANGSMITH_TRACING
#     first, the langsmith client reads *_TRACING_V2 first;
#   - credentials emptied, not unset: a .env loader that does not override
#     (python-dotenv's default) then leaves them empty, and both libraries read
#     a blank key as no key;
#   - the endpoint at a closed local port: tracing switched back on fails
#     loudly here instead of reaching api.smith.langchain.com;
#   - the CLI's usage analytics and the server's PyPI version check off.
export LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false LANGCHAIN_TRACING_V2=false LANGCHAIN_TRACING=false
export LANGSMITH_API_KEY='' LANGCHAIN_API_KEY='' LANGSMITH_CONTROL_PLANE_API_KEY='' LANGGRAPH_CLOUD_LICENSE_KEY=''
export LANGSMITH_ENDPOINT=http://127.0.0.1:9 LANGCHAIN_ENDPOINT=http://127.0.0.1:9
export LANGGRAPH_CLI_NO_ANALYTICS=1 LANGGRAPH_NO_VERSION_CHECK=true

exec uv run langgraph dev --config "$config" --host 127.0.0.1 --port "$port" --no-browser ${args[@]+"${args[@]}"}

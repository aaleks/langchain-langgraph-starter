# Shared helpers for the SDD hooks. Sourced, never executed.
#
# Portable on purpose: bash 3.2 (macOS's default) and Git Bash on Windows. So no
# ${var,,}, no associative arrays, no mapfile -- and no jq, which a Windows
# machine rarely has. JSON is read with sed, which is enough for the few string
# fields a hook needs.

# The project root: where Claude Code started the session.
project_dir() {
  printf '%s\n' "${CLAUDE_PROJECT_DIR:-$PWD}"
}

# The first string value of "key" in a JSON document, unescaped enough for paths.
json_field() {
  printf '%s' "$1" \
    | sed -nE "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\".*/\\1/p" \
    | head -n 1 \
    | sed -e 's/\\\\/\\/g' -e 's/\\"/"/g'
}

# A path made relative to the project root, with forward slashes. Windows paths
# compare case-insensitively (C: and c: are one drive), so compare lowercased.
project_relative() {
  local path root lower_path lower_root
  # shellcheck disable=SC1003  # '\\' is tr's backslash, not an escaped quote
  path=$(printf '%s' "$1" | tr '\\' '/')
  # shellcheck disable=SC1003
  root=$(project_dir | tr '\\' '/')
  root="${root%/}"
  lower_path=$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')
  lower_root=$(printf '%s' "$root" | tr '[:upper:]' '[:lower:]')
  case "$lower_path" in
    "$lower_root"/*) path="${path:${#root}+1}" ;;
  esac
  printf '%s\n' "${path#./}"
}

# Every string in a one-line TOML array: toml_array <file> <section> <key>.
# sdd check refuses a [guards] array split across lines, so one line is enough.
toml_array() {
  [ -f "$1" ] || return 0
  awk -v section="$2" -v key="$3" '
    /^[[:space:]]*\[/ { header = $0; gsub(/[][[:space:]]/, "", header); current = header; next }
    current == section {
      line = $0
      sub(/#.*/, "", line)
      if (line ~ "^[[:space:]]*" key "[[:space:]]*=") {
        sub(/^[^=]*=/, "", line)
        while (match(line, /"[^"]*"/)) {
          print substr(line, RSTART + 1, RLENGTH - 2)
          line = substr(line, RSTART + RLENGTH)
        }
      }
    }' "$1"
}

# A JSON string literal: quotes, backslashes, tabs and newlines escaped.
json_string() {
  printf '%s' "$1" | awk '
    BEGIN { ORS = "" ; printf "\"" }
    {
      gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); gsub(/\t/, "\\t")
      if (NR > 1) printf "\\n"
      printf "%s", $0
    }
    END { printf "\"" }'
}

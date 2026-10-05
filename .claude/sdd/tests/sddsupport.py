"""Fixtures as txtar archives: one readable file per failure a check claims to catch.

    # what this fixture demonstrates
    expect-errors: SDD007
    expect-warnings:
    today: 2026-10-04
    -- sdd.toml --
    ...
    -- openspec/specs/cap/spec.md --
    ...

The expectations are EXACT sets: a fixture that starts producing an extra
diagnostic fails as surely as one that stops producing its own. Adding a check
means adding a fixture here -- /learn's rule -- and the data-driven test picks it
up with no further wiring.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDD = HERE.parent
FIXTURES = SDD / "fixtures"
if str(SDD) not in sys.path:
    sys.path.insert(0, str(SDD))

MARKER = re.compile(r"^-- (.+?) --$")
HEADERS = {"expect-errors": "error", "expect-warnings": "warning", "expect-infos": "info"}
DEFAULT_TODAY = date(2026, 10, 4)


@dataclass
class Fixture:
    name: str
    description: str
    expect: dict[str, set[str]]
    today: date
    files: dict[str, str]


def load_fixture(path: Path) -> Fixture:
    header: list[str] = []
    files: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if match := MARKER.match(line.rstrip("\r\n")):
            current = match.group(1).strip()
            files[current] = ""
        elif current is None:
            header.append(line.rstrip("\r\n"))
        else:
            files[current] += line

    expect: dict[str, set[str]] = {severity: set() for severity in HEADERS.values()}
    today, description = DEFAULT_TODAY, []
    for line in header:
        if line.startswith("#") or not line.strip():
            description.append(line.lstrip("# ").strip())
            continue
        key, _, value = (part.strip() for part in line.partition(":"))
        if key in HEADERS:
            expect[HEADERS[key]] = {code.strip() for code in value.split(",") if code.strip()}
        elif key == "today":
            today = date.fromisoformat(value)
        else:
            # A misspelled header would silently assert nothing -- refuse it.
            raise ValueError(f"{path.name}: unknown fixture header {key!r}")
    return Fixture(path.stem, " ".join(d for d in description if d), expect, today, files)


def materialize(fixture: Fixture, destination: Path) -> Path:
    for rel, content in fixture.files.items():
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return destination


def all_fixtures(kind: str) -> list[Path]:
    return sorted((FIXTURES / kind).glob("*.txtar"))


def run_fixture(name_or_path: str | Path):
    """Materialise a check fixture in a temporary project and run the checker on it."""
    from sddlib.check import run

    path = Path(name_or_path)
    if not path.suffix:
        path = FIXTURES / "check" / f"{name_or_path}.txtar"
    fixture = load_fixture(path)
    with tempfile.TemporaryDirectory() as tmp:
        root = materialize(fixture, Path(tmp))
        result = run(root, today=fixture.today)
    return fixture, result


# -- the local runtime: scripts/serve.sh and the agent's deny rules ------------

SEEDS = SDD / "seeds"
SERVE_SEED = SEEDS / "serve.sh"
LANGGRAPH_SETTINGS = SEEDS / "settings.langgraph.json"
BASH = shutil.which("bash")

# The local-only environment, transcribed from LOCAL-SERVE-ENVIRONMENT. The
# wrapper and the agent's settings must each equal it -- one environment,
# written in two places, held together by the tests rather than by memory.
LOCAL_ONLY = {
    "LANGSMITH_TRACING": "false",
    "LANGSMITH_TRACING_V2": "false",
    "LANGCHAIN_TRACING_V2": "false",
    "LANGCHAIN_TRACING": "false",
    "LANGSMITH_API_KEY": "",
    "LANGCHAIN_API_KEY": "",
    "LANGSMITH_CONTROL_PLANE_API_KEY": "",
    "LANGGRAPH_CLOUD_LICENSE_KEY": "",
    "LANGSMITH_ENDPOINT": "http://127.0.0.1:9",
    "LANGCHAIN_ENDPOINT": "http://127.0.0.1:9",
    "LANGGRAPH_CLI_NO_ANALYTICS": "1",
    "LANGGRAPH_NO_VERSION_CHECK": "true",
}

# A stand-in for uv, first on PATH: it records what it was asked to start and
# the variables it was started with, and starts nothing. `printenv` tells a
# variable set to empty from one that is not set at all.
FAKE_UV = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_UV_DIR/argv"
for name in $FAKE_UV_VARS; do
  if value=$(printenv "$name"); then printf '%s=%s\\n' "$name" "$value"; fi
done > "$FAKE_UV_DIR/env"
"""

DEFAULT_CONFIG = '{"graphs": {"chat": "./src/app/infrastructure/agents/registry.py:chat"}}\n'


@dataclass
class Served:
    """What `bash scripts/serve.sh` did: its exit, and what it asked uv to start."""

    run: subprocess.CompletedProcess
    argv: list[str] | None  # None: the server was never started
    env: dict[str, str] | None


def serve_project(destination: Path, config: str | None = DEFAULT_CONFIG) -> Path:
    """A project holding the seeded wrapper and, unless None, a langgraph.json."""
    (destination / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SERVE_SEED, destination / "scripts" / "serve.sh")
    if config is not None:
        (destination / "langgraph.json").write_text(config, encoding="utf-8")
    return destination


def run_serve(project: Path, *args: str, exports: dict[str, str] | None = None) -> Served:
    """Run the project's wrapper as a person would, with the stand-in uv on PATH."""
    record = project / ".fake-uv"
    record.mkdir(exist_ok=True)
    for stale in ("argv", "env"):
        (record / stale).unlink(missing_ok=True)
    fake = record / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    exports = exports or {}
    # A clean start: nothing LangSmith- or LangGraph-shaped leaks in from the
    # machine running the tests, so only what a test exports can be seen.
    base = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("LANGSMITH_", "LANGCHAIN_", "LANGGRAPH_"))
    }
    env = {
        **base,
        **exports,
        "PATH": f"{record}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_UV_DIR": str(record),
        "FAKE_UV_VARS": " ".join([*LOCAL_ONLY, *exports]),
    }
    run = subprocess.run(
        [BASH, str(project / "scripts" / "serve.sh"), *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    argv_file, env_file = record / "argv", record / "env"
    argv = argv_file.read_text(encoding="utf-8").splitlines() if argv_file.is_file() else None
    seen = None
    if env_file.is_file():
        seen = dict(
            line.split("=", 1) for line in env_file.read_text(encoding="utf-8").splitlines()
        )
    return Served(run, argv, seen)


def bash_rule_pattern(rule: str) -> re.Pattern | None:
    """A `Bash(...)` permission rule as Claude Code documents it: `*` stands for
    any text, spaces included; everything else is literal; the whole command
    must match. None for a rule on another tool."""
    match = re.fullmatch(r"Bash\((.*)\)", rule, re.DOTALL)
    if match is None:
        return None
    parts = re.split(r"(\*)", match.group(1))
    return re.compile("".join(".*" if p == "*" else re.escape(p) for p in parts), re.DOTALL)


def denied(command: str, rules: list[str]) -> bool:
    """Whether a deny list refuses a command.

    Claude Code splits a compound command and denies when any part matches.
    Every rule here has the form `*text*` (a test checks that), and for such a
    rule matching the whole command is the same as matching any part -- so the
    splitting need not be modelled, and is not.
    """
    patterns = [p for p in map(bash_rule_pattern, rules) if p is not None]
    return any(p.fullmatch(command) for p in patterns)

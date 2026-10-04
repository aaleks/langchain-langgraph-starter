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

import re
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

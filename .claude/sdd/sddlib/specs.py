"""Reading requirements out of OpenSpec Markdown, without OpenSpec.

The method keeps OpenSpec's container and adds its own fields inside it:

    ### Requirement: PROVIDER-PRECEDENCE
    The system SHALL choose the provider by override, then environment, then default.

    - **Kind:** deterministic
    - **Proved by:** `tests/unit/test_providers.py::TestProviderPrecedence`

    #### Scenario: Override beats environment
    ...
    #### Scenario: Counter-example -- an unknown name is refused, not defaulted
    ...

This parser reads files, not the OpenSpec CLI, on purpose: if OpenSpec
disappeared tomorrow the specs and their proof would survive as plain Markdown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# <CAPABILITY>-<RULE>, upper kebab. A sentence would change when someone rewords
# it, and every test docstring and review that cites it would break silently.
REQUIREMENT_ID = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")

FENCE = re.compile(r"^\s*(```|~~~)")
H2 = re.compile(r"^##\s+(.+?)\s*#*\s*$")
REQUIREMENT = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$")
H3 = re.compile(r"^###\s")
SCENARIO = re.compile(r"^####\s+Scenario:\s*(.+?)\s*$")
H4 = re.compile(r"^####\s")
FIELD = re.compile(r"^\s*[-*]\s+\*\*(?P<key>[A-Za-z][A-Za-z ]*?):\*\*\s*(?P<value>.*)$")
BULLET = re.compile(r"^\s*[-*+]\s")
COUNTER_EXAMPLE = re.compile(r"^\s*counter[\s-]?examples?\b", re.IGNORECASE)

DELTA_SECTIONS = {
    "added requirements": "added",
    "modified requirements": "modified",
    "removed requirements": "removed",
    "renamed requirements": "renamed",
}

# Requirements whose rules are checked: the current truth, and what a change
# will make true when it is archived. REMOVED and RENAMED entries are names only.
CHECKED = ("living", "added", "modified")


@dataclass
class FieldValue:
    text: str
    line: int


@dataclass
class Requirement:
    id: str
    file: str  # project-relative, POSIX separators
    line: int
    section: str  # living | added | modified | removed | renamed | stray
    capability: str
    change: str | None = None  # the change id, for a delta
    fields: dict[str, FieldValue] = field(default_factory=dict)
    scenarios: list[tuple[str, int]] = field(default_factory=list)

    @property
    def target(self) -> str:
        return f"{self.file}:{self.line}"

    def value(self, name: str) -> str | None:
        found = self.fields.get(name.lower())
        return found.text.strip() if found else None

    @property
    def has_counter_example(self) -> bool:
        return any(COUNTER_EXAMPLE.match(title) for title, _ in self.scenarios)


def parse(text: str, *, file: str, capability: str, change: str | None) -> list[Requirement]:
    """Every `### Requirement:` block in one file, with its fields and scenarios.

    Fields are the `- **Key:** value` bullets between the heading and the first
    scenario; a value may continue on indented lines. Fenced code and HTML
    comments are skipped, so a spec can show an example of the format -- and a
    template's guidance comments -- without either being read as a requirement.
    """
    requirements: list[Requirement] = []
    section = "living" if change is None else "stray"
    current: Requirement | None = None
    last_field: str | None = None
    in_fence = in_comment = False

    for number, raw in enumerate(text.splitlines(), start=1):
        if FENCE.match(raw):
            in_fence, last_field = not in_fence, None
            continue
        if in_fence:
            continue
        line, in_comment = _strip_comments(raw, in_comment)

        if match := H2.match(line):
            section = _section(match.group(1), change)
            current, last_field = None, None
            continue
        if match := REQUIREMENT.match(line):
            current = Requirement(
                id=match.group(1),
                file=file,
                line=number,
                section=section,
                capability=capability,
                change=change,
            )
            requirements.append(current)
            last_field = None
            continue
        if H3.match(line):
            current, last_field = None, None
            continue
        if current is None:
            continue
        if match := SCENARIO.match(line):
            current.scenarios.append((match.group(1), number))
            last_field = None
            continue
        if H4.match(line) or current.scenarios:
            last_field = None
            continue
        if match := FIELD.match(line):
            last_field = match.group("key").strip().lower()
            current.fields[last_field] = FieldValue(match.group("value").strip(), number)
            continue
        if last_field and line[:1] in (" ", "\t") and line.strip() and not BULLET.match(line):
            current.fields[last_field].text += " " + line.strip()
            continue
        if not line.strip():
            last_field = None
    return requirements


def load_living(root: Path, living: str) -> tuple[list[Requirement], int]:
    """Requirements in the living specs, and how many capability files hold them."""
    base = root / living
    files = sorted(base.rglob("spec.md"))
    requirements: list[Requirement] = []
    for path in files:
        capability = path.parent.relative_to(base).as_posix() or path.parent.name
        requirements += parse(
            path.read_text(encoding="utf-8"),
            file=path.relative_to(root).as_posix(),
            capability=capability,
            change=None,
        )
    return requirements, len(files)


def load_changes(root: Path, changes: str | None) -> tuple[list[Requirement], int]:
    """Requirements in every in-flight change's delta specs, and the count of changes.

    `changes/archive/` is history, not truth, and is never checked.
    """
    if not changes:
        return [], 0
    base = root / changes
    requirements: list[Requirement] = []
    in_flight = sorted(d for d in base.iterdir() if d.is_dir() and d.name != "archive")
    for change in in_flight:
        specs = change / "specs"
        if not specs.is_dir():
            continue
        for path in sorted(specs.rglob("*.md")):
            requirements += parse(
                path.read_text(encoding="utf-8"),
                file=path.relative_to(root).as_posix(),
                capability=path.parent.relative_to(specs).as_posix(),
                change=change.name,
            )
    return requirements, len(in_flight)


def _section(heading: str, change: str | None) -> str:
    if change is None:
        return "living"
    return DELTA_SECTIONS.get(heading.strip().lower(), "stray")


def _strip_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    """Remove HTML comments, which may span lines."""
    out = ""
    while line:
        if in_comment:
            end = line.find("-->")
            if end < 0:
                return out, True
            line, in_comment = line[end + 3 :], False
        else:
            start = line.find("<!--")
            if start < 0:
                return out + line, False
            out, line, in_comment = out + line[:start], line[start + 4 :], True
    return out, in_comment

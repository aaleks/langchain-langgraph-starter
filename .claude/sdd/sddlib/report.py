"""One shape for every finding: hook, terminal, CI and agent read the same thing.

The envelope -- severity, code, message, target, fix -- is OpenSpec's own
diagnostic shape, so a tool that already reads `openspec validate --json` reads
this without learning a second format.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from . import VERSION

SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class Diagnostic:
    severity: str  # error | warning | info
    code: str  # SDDnnn -- stable, so a fixture can expect it
    message: str
    target: str  # path:line, or a path
    fix: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r}")


@dataclass
class Summary:
    capabilities: int = 0
    requirements: int = 0
    deterministic: int = 0
    evaluated: int = 0
    changes: int = 0
    change_requirements: int = 0
    test_files: int = 0
    claimed: int = 0

    def describe(self) -> str:
        return (
            f"{_n(self.capabilities, 'capability', 'capabilities')}, "
            f"{_n(self.requirements, 'requirement')} "
            f"({self.deterministic} deterministic, {self.evaluated} evaluated); "
            f"{_n(self.changes, 'change')} in flight "
            f"({_n(self.change_requirements, 'requirement')}); "
            f"{_n(self.test_files, 'test file')}, {self.claimed} claimed"
        )


@dataclass
class Result:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)

    def add(self, severity: str, code: str, message: str, target: str, fix: str = "") -> None:
        self.diagnostics.append(Diagnostic(severity, code, message, target, fix))

    def count(self, severity: str) -> int:
        return sum(1 for d in self.diagnostics if d.severity == severity)

    @property
    def ok(self) -> bool:
        return self.count("error") == 0

    def codes(self, severity: str) -> set[str]:
        return {d.code for d in self.diagnostics if d.severity == severity}


def render_text(result: Result) -> str:
    errors, warnings = result.count("error"), result.count("warning")
    head = "sdd check: OK" if result.ok else "sdd check: FAILED"
    lines = [f"{head} -- {errors} error(s), {warnings} warning(s)"]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    for d in sorted(
        result.diagnostics, key=lambda d: (order[d.severity], *_place(d.target), d.code)
    ):
        lines.append(f"  {d.severity:<7} {d.code}  {d.target}  {d.message}")
        if d.fix:
            lines.append(f"          fix: {d.fix}")
    lines.append(f"  checked: {result.summary.describe()}")
    return "\n".join(lines)


def _place(target: str) -> tuple[str, int]:
    """Sort path:line by path, then by line as a number -- not ':15' before ':3'."""
    path, _, line = target.rpartition(":")
    return (path, int(line)) if line.isdigit() else (target, 0)


def _n(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def render_json(result: Result) -> str:
    return json.dumps(
        {
            "tool": "sdd",
            "version": VERSION,
            "ok": result.ok,
            "summary": asdict(result.summary),
            "diagnostics": [asdict(d) for d in result.diagnostics],
        },
        indent=2,
    )

"""Where each in-flight change stands, read from its files.

Used by the SessionStart hook so a new session resumes at the earliest
incomplete stage instead of re-deriving it -- or worse, skipping one. Reads the
change directories directly rather than calling OpenSpec: a hook must be fast
and must not need the network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CLASS = re.compile(r"^\s*[-*]\s+\*\*Class:\*\*\s*`?([a-z]+)", re.MULTILINE)
VERDICT = re.compile(r"\*\*Verdict:\*\*\s*`?(SHIP|DO NOT SHIP|GO|CLARIFY|KILL)\b", re.IGNORECASE)
DONE = re.compile(r"^\s*[-*]\s+\[[xX]\]", re.MULTILINE)
TODO = re.compile(r"^\s*[-*]\s+\[\s\]", re.MULTILINE)
# OpenSpec's own declaration that a change has no delta specs. Without reading
# it, a declared skip looks like a missing stage and a session resumes at specs.
SKIP_SPECS = re.compile(r"^skip_specs:\s*true\s*$", re.MULTILINE | re.IGNORECASE)

# The sdd-proof schema's planning artifacts, in order. design.md is conditional:
# only a structural change must have one.
STAGES = ("intake", "frame", "specs", "design", "tasks", "verify")


@dataclass
class ChangeStatus:
    id: str
    klass: str | None
    present: dict[str, bool]
    tasks_done: int
    tasks_total: int
    verdict: str | None
    skips_specs: bool = False

    @property
    def next_stage(self) -> str | None:
        if self.klass == "spike":
            return None if self.verdict else "intake (record the verdict: go | clarify | kill)"
        for stage in STAGES:
            if stage == "design" and self.klass != "structural":
                continue
            if stage == "specs" and self.skips_specs:
                continue
            if stage == "verify" and self.tasks_total and self.tasks_done < self.tasks_total:
                return f"apply ({self.tasks_done}/{self.tasks_total} tasks done)"
            if not self.present[stage]:
                return stage
        return "land" if (self.verdict or "").upper() == "SHIP" else "verify (verdict is not SHIP)"

    def _mark(self, stage: str) -> str:
        if self.present[stage]:
            return "+"
        return "~" if stage == "specs" and self.skips_specs else "-"

    def line(self) -> str:
        marks = " ".join(f"{s}{self._mark(s)}" for s in STAGES)
        tasks = f" tasks {self.tasks_done}/{self.tasks_total}" if self.tasks_total else ""
        verdict = f" verdict {self.verdict}" if self.verdict else ""
        nxt = self.next_stage
        return f"{self.id} [{self.klass or 'unclassified'}] {marks}{tasks}{verdict}" + (
            f" -> next: {nxt}" if nxt else " -> done"
        )


def read(root: Path, changes: str = "openspec/changes") -> list[ChangeStatus]:
    base = root / changes
    if not base.is_dir():
        return []
    statuses = []
    for change in sorted(d for d in base.iterdir() if d.is_dir() and d.name != "archive"):
        intake = _text(change / "intake.md")
        tasks = _text(change / "tasks.md")
        verify = _text(change / "verify.md")
        specs = change / "specs"
        verdict = VERDICT.search(verify) or VERDICT.search(intake)
        statuses.append(
            ChangeStatus(
                id=change.name,
                klass=(m.group(1) if (m := CLASS.search(intake)) else None),
                present={
                    "intake": bool(intake),
                    "frame": (change / "frame.md").is_file(),
                    "specs": specs.is_dir() and any(specs.rglob("*.md")),
                    "design": (change / "design.md").is_file(),
                    "tasks": bool(tasks),
                    "verify": bool(verify),
                },
                tasks_done=len(DONE.findall(tasks)),
                tasks_total=len(DONE.findall(tasks)) + len(TODO.findall(tasks)),
                verdict=verdict.group(1).upper() if verdict else None,
                skips_specs=bool(SKIP_SPECS.search(_text(change / ".openspec.yaml"))),
            )
        )
    return statuses


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""

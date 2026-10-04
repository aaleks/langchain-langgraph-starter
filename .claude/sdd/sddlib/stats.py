"""Is the method working? The numbers that turn a method change from taste into evidence.

Read from files only -- the living specs and the archived changes -- so they
cost nothing to collect. The one number files cannot give, cycles per
requirement, is reported as not collected rather than estimated.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .specs import load_living, parse
from .status import CLASS

ARTIFACTS = ("frame", "specs", "design", "tasks", "verify")


def collect(root: Path, living: str = "openspec/specs", changes: str = "openspec/changes") -> dict:
    requirements, _ = load_living(root, living) if (root / living).is_dir() else ([], 0)
    kinds = Counter(r.value("kind") or "missing" for r in requirements)
    decided = kinds["deterministic"] + kinds["evaluated"]

    archive = root / changes / "archive"
    by_class: dict[str, Counter] = defaultdict(Counter)
    deltas = Counter()
    defects = Counter()
    for change in sorted(d for d in archive.iterdir() if d.is_dir()) if archive.is_dir() else []:
        intake = change / "intake.md"
        match = CLASS.search(intake.read_text(encoding="utf-8")) if intake.is_file() else None
        klass = match.group(1) if match else "unclassified"
        sections = Counter()
        specs = change / "specs"
        for path in sorted(specs.rglob("*.md")) if specs.is_dir() else []:
            for requirement in parse(
                path.read_text(encoding="utf-8"), file=str(path), capability="", change=change.name
            ):
                sections[requirement.section] += 1
        deltas.update(sections)
        by_class[klass]["changes"] += 1
        for artifact in ARTIFACTS:
            present = (
                (specs.is_dir() and any(specs.rglob("*.md")))
                if artifact == "specs"
                else (change / f"{artifact}.md").is_file()
            )
            if not present:
                by_class[klass][f"skipped {artifact}"] += 1
        if klass == "defect":
            defects[
                "modified an existing requirement"
                if sections["modified"]
                else "added a missing requirement"
            ] += 1

    return {
        "deterministic share": f"{kinds['deterministic']}/{decided}"
        if decided
        else "no requirements yet",
        "requirements amended after implementation (MODIFIED deltas archived)": deltas["modified"],
        "requirements removed (REMOVED deltas archived)": deltas["removed"],
        "defects": dict(defects) or "none archived yet",
        "stages skipped, by intake class": {k: dict(v) for k, v in sorted(by_class.items())}
        or "no archived changes yet",
        "cycles per requirement": "not collected -- needs session data, which files do not hold",
    }


def register(sub: argparse._SubParsersAction) -> None:
    cmd = sub.add_parser("stats", help="method health: what the specs and the archive say")
    cmd.add_argument("--json", action="store_true")
    cmd.set_defaults(handler=_stats)


def _stats(root: Path, args: argparse.Namespace) -> int:
    numbers = collect(root)
    if args.json:
        print(json.dumps(numbers, indent=2))
        return 0
    for name, value in numbers.items():
        if isinstance(value, dict):
            print(f"{name}:")
            for key, inner in value.items():
                print(f"  {key}: {inner}")
        else:
            print(f"{name}: {value}")
    return 0

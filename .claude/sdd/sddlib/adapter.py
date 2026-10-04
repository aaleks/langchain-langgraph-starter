"""sdd.toml: the one file that says where this project keeps its specs and tests.

Everything else in the method is the same in every project. This file is the
adapter -- the tier-2 layer between a universal method and one project's
layout -- and it is deliberately small.

An unrecognised key is REFUSED, not ignored. A setting that silently does
nothing is worse than one that is rejected: its author believes it took
effect, and finds out when a check turns out never to have been checking.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KNOWN: dict[str, frozenset[str]] = {
    "specs": frozenset({"living", "changes"}),
    "tests": frozenset({"roots", "patterns", "exempt", "symbols"}),
    # Read by skills and agents so they never hard-code a test runner.
    # The checker itself never executes them.
    "commands": frozenset(
        {"check", "suite", "test", "architecture", "lint", "format", "live", "strength"}
    ),
    # Read by .claude/hooks/guard-edits.sh, which is bash -- see _guards_on_one_line.
    "guards": frozenset({"ground_truth"}),
}

SYMBOL_MODES = ("python", "none")

# How `file::Name` resolves when symbols = "python": any class or function
# definition, nested or not. A regex rather than `ast`, so a test file with a
# syntax error still has its names found -- the check must not depend on the
# thing it checks being importable.
PYTHON_SYMBOLS = r"^\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)"


class AdapterError(ValueError):
    """sdd.toml is missing, malformed, or names something that does not exist."""


@dataclass(frozen=True)
class Adapter:
    path: Path
    living: str
    changes: str | None
    test_roots: tuple[str, ...]
    test_patterns: tuple[str, ...]
    exempt: tuple[str, ...] = ()
    symbols: str = "python"
    commands: dict[str, str] = field(default_factory=dict)
    ground_truth: tuple[str, ...] = ()

    @property
    def symbol_pattern(self) -> re.Pattern[str] | None:
        if self.symbols == "none":
            return None
        if self.symbols == "python":
            return re.compile(PYTHON_SYMBOLS, re.MULTILINE)
        return re.compile(self.symbols.removeprefix("regex:"), re.MULTILINE)


def load(config: Path, root: Path) -> Adapter:
    """Read and validate the adapter. Raises AdapterError with the fix in the message."""
    if not config.is_file():
        raise AdapterError(
            f"{_rel(config, root)} not found. Create it from .claude/sdd/seeds/sdd.toml -- "
            "it says where this project keeps its specs and its tests."
        )
    text = config.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise AdapterError(f"{_rel(config, root)} is not valid TOML: {exc}") from exc

    problems = _unknown_keys(data)
    problems += _guards_on_one_line(text)
    if problems:
        raise AdapterError(f"{_rel(config, root)}: " + "; ".join(problems))

    specs, tests = data.get("specs", {}), data.get("tests", {})
    living = _string(specs, "specs.living", required=True)
    changes = _string(specs, "specs.changes")
    roots = _strings(tests, "tests.roots", required=True)
    patterns = _strings(tests, "tests.patterns", required=True)
    exempt = _strings(tests, "tests.exempt")
    symbols = _string(tests, "tests.symbols") or "python"
    _validate_symbols(symbols)
    commands = {
        k: _string(data.get("commands", {}), f"commands.{k}") or ""
        for k in data.get("commands", {})
    }
    ground_truth = _strings(data.get("guards", {}), "guards.ground_truth")

    # A configured directory that does not exist is a misconfiguration, never an
    # empty project. Passing here would be a check that checks nothing, forever.
    missing = [p for p in [living, changes, *roots] if p and not (root / p).is_dir()]
    if missing:
        raise AdapterError(
            f"{_rel(config, root)} names directories that do not exist: {', '.join(missing)}. "
            "Create them (an empty directory is an honest empty project) or correct the path."
        )

    return Adapter(
        path=config,
        living=_posix(living),
        changes=_posix(changes) if changes else None,
        test_roots=tuple(_posix(r) for r in roots),
        test_patterns=tuple(patterns),
        exempt=tuple(_posix(e) for e in exempt),
        symbols=symbols,
        commands=commands,
        ground_truth=tuple(ground_truth),
    )


def _unknown_keys(data: dict) -> list[str]:
    problems = []
    for section, value in data.items():
        if section not in KNOWN:
            problems.append(f"unknown section [{section}] (known: {', '.join(sorted(KNOWN))})")
            continue
        if not isinstance(value, dict):
            problems.append(f"[{section}] must be a table")
            continue
        for key in value:
            if key not in KNOWN[section]:
                problems.append(
                    f"unknown key {section}.{key} (known: {', '.join(sorted(KNOWN[section]))})"
                )
    return problems


def _guards_on_one_line(text: str) -> list[str]:
    """The edit guard is bash and reads `[guards]` arrays a line at a time.

    So an array split across lines would be silently half-read by the hook --
    exactly the silent-ignore this module refuses. Enforce the shape the hook
    can read rather than hope.
    """
    problems, section = [], None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped.strip("[] ")
            continue
        if section == "guards" and "=" in stripped and not stripped.startswith("#"):
            value = stripped.split("=", 1)[1].split("#", 1)[0].strip()
            if value.startswith("[") and not value.endswith("]"):
                key = stripped.split("=", 1)[0].strip()
                problems.append(
                    f"guards.{key} must be written on one line -- the edit guard is bash "
                    "and reads it line by line"
                )
    return problems


def _string(table: dict, name: str, required: bool = False) -> str | None:
    key = name.split(".")[-1]
    value = table.get(key)
    if value is None:
        if required:
            raise AdapterError(f"sdd.toml: {name} is required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"sdd.toml: {name} must be a non-empty string")
    return value


def _strings(table: dict, name: str, required: bool = False) -> list[str]:
    key = name.split(".")[-1]
    value = table.get(key)
    if value is None:
        if required:
            raise AdapterError(f"sdd.toml: {name} is required")
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise AdapterError(f"sdd.toml: {name} must be a list of non-empty strings")
    if required and not value:
        raise AdapterError(f"sdd.toml: {name} must not be empty")
    return value


def _validate_symbols(mode: str) -> None:
    if mode in SYMBOL_MODES:
        return
    if mode.startswith("regex:"):
        try:
            pattern = re.compile(mode.removeprefix("regex:"))
        except re.error as exc:
            raise AdapterError(f"sdd.toml: tests.symbols regex does not compile: {exc}") from exc
        if pattern.groups < 1:
            raise AdapterError("sdd.toml: tests.symbols regex needs a group capturing the name")
        return
    raise AdapterError(
        f"sdd.toml: tests.symbols must be one of {', '.join(SYMBOL_MODES)} or regex:<pattern>"
    )


def _posix(path: str) -> str:
    return path.replace("\\", "/").strip("/").removeprefix("./")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)

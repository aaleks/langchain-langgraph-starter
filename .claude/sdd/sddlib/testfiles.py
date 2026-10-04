"""Which files are tests, and which names a test file defines.

Language-neutral by construction: a test file is a basename pattern under a
root, and a name is whatever the adapter's symbol pattern captures. Python is
the default pattern, not an assumption.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from .adapter import Adapter

SKIP_PARTS = frozenset({"__pycache__", "node_modules", ".venv", ".git"})


def is_test_name(name: str, adapter: Adapter) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in adapter.test_patterns)


def is_exempt(rel: str, adapter: Adapter) -> bool:
    # fnmatch's `*` also matches `/`, so `tests/architecture/*` covers the
    # directory's whole subtree -- fixtures included.
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in adapter.exempt)


def under_roots(rel: str, adapter: Adapter) -> bool:
    return any(rel == root or rel.startswith(root + "/") for root in adapter.test_roots)


def discover(root: Path, adapter: Adapter) -> list[str]:
    """Every test file that must be claimed by a requirement, project-relative."""
    found: set[str] = set()
    for test_root in adapter.test_roots:
        for path in (root / test_root).rglob("*"):
            if not path.is_file() or SKIP_PARTS.intersection(path.parts):
                continue
            rel = path.relative_to(root).as_posix()
            if is_test_name(path.name, adapter) and not is_exempt(rel, adapter):
                found.add(rel)
    return sorted(found)


class SymbolIndex:
    """Names defined per file, read once each."""

    def __init__(self, root: Path, pattern: re.Pattern[str] | None) -> None:
        self._root, self._pattern = root, pattern
        self._cache: dict[str, set[str]] = {}

    @property
    def enabled(self) -> bool:
        return self._pattern is not None

    def names(self, rel: str) -> set[str]:
        if rel not in self._cache:
            text = (self._root / rel).read_text(encoding="utf-8", errors="replace")
            self._cache[rel] = set(self._pattern.findall(text)) if self._pattern else set()
        return self._cache[rel]

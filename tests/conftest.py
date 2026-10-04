"""Shared fixtures.

Deliberately small. Domain functions take the environment as an explicit
argument, so most tests need no fixture at all -- hiding that behind one would
obscure the point of the layering.

A `fake_llm` fixture arrives with the first change that adds langchain-core
(docs/roadmap.md, slice 1). No test may call a real model; see
.claude/rules/sdd/tests.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

# `NAME=value` or `# NAME=value`: a documented variable, set or not.
_DOCUMENTED = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)


def documented_variables() -> list[str]:
    """Every variable .env.example documents -- the single list of what is read."""
    return sorted(set(_DOCUMENTED.findall(ENV_EXAMPLE.read_text(encoding="utf-8"))))


def pytest_collection_modifyitems(config, items):
    """Skip `live` tests unless the command line explicitly asked for them.

    addopts carries -m 'not live', but a command-line -m REPLACES that
    expression rather than ANDing with it. So `pytest -m "not slow"` silently
    re-selects every live test and makes real calls -- measured in the project
    this method came from, three of them. This closes that hole without
    breaking the documented `pytest -m live`.
    """
    markexpr = config.getoption("markexpr", "") or ""
    asked_for_live = bool(re.search(r"(^|[\s(])live\b", markexpr)) and not re.search(
        r"\bnot\s+live\b", markexpr
    )
    if asked_for_live:
        return
    skip = pytest.mark.skip(reason="live test: run it with -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def clean_env(monkeypatch):
    """A process environment with every documented variable removed.

    Without this, whatever is in the developer's real .env leaks into a test,
    and it passes or fails depending on whose machine runs it.
    """
    for name in documented_variables():
        monkeypatch.delenv(name, raising=False)
    return monkeypatch

"""Shared fixtures.

Deliberately small. Domain functions take the environment as an explicit
argument, so most tests need no fixture at all -- hiding that behind one would
obscure the point of the layering.

No test may call a real model (.claude/rules/sdd/tests.md): `fake_llm` scripts
one, and `add_tool` records what a tool loop asked of its only tool.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, tool

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


# -- models and tools ----------------------------------------------------------

_call_ids = itertools.count(1)


def propose(*calls: tuple[str, dict[str, Any]]) -> AIMessage:
    """An AI message proposing these tool calls, each under a fresh id."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{next(_call_ids)}", "type": "tool_call"}
            for name, args in calls
        ],
    )


def answer(text: str = "done") -> AIMessage:
    """An AI message proposing no tool call. Its text is never asserted."""
    return AIMessage(content=text)


class ScriptedChatModel(GenericFakeChatModel):
    """`GenericFakeChatModel`, one scripted message per call, that accepts tools.

    Every fake in langchain_core inherits `bind_tools` from `BaseChatModel`,
    which raises NotImplementedError, so `create_agent` cannot bind tools to a
    stock fake. Binding changes nothing here: the script decides what the model
    proposes. `calls` counts the model calls a run made.
    """

    calls: int = 0

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> Any:
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return super()._generate(*args, **kwargs)


@pytest.fixture
def fake_llm():
    """Build a scripted model. Each message is copied as it is served, so a
    script may repeat one, or run forever: `(propose(...) for _ in count())`."""

    def build(script: Iterable[AIMessage]) -> ScriptedChatModel:
        return ScriptedChatModel(messages=(m.model_copy(deep=True) for m in script))

    return build


@dataclass
class RecordingTool:
    tool: BaseTool
    calls: list[dict[str, int]]


@pytest.fixture
def add_tool() -> RecordingTool:
    """A fake `add(a, b)` tool that records each call's arguments."""
    calls: list[dict[str, int]] = []

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        calls.append({"a": a, "b": b})
        return a + b

    return RecordingTool(tool=add, calls=calls)

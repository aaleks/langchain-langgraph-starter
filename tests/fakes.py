"""Fakes for the tests that run a graph: a scripted chat model and a recording tool.

Imported only by those tests, through the fixtures in conftest.py or directly,
so a domain unit run never pays for importing langchain_core.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

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


def malformed(
    name: str, raw_arguments: str, *, count: int = 1, with_id: bool = True, content: str = ""
) -> AIMessage:
    """An AI message proposing `count` calls of `name` whose arguments cannot be
    parsed, as langchain-core records them from a model's reply: invalid tool
    calls -- each with an id, unless `with_id` is False."""
    return AIMessage(
        content=content,
        invalid_tool_calls=[
            {
                "name": name,
                "args": raw_arguments,
                "id": f"call_{next(_call_ids)}" if with_id else None,
                "error": f"Function {name} arguments:\n\n{raw_arguments}\n\nare not valid JSON.",
                "type": "invalid_tool_call",
            }
            for _ in range(count)
        ],
    )


def answer(text: str = "done") -> AIMessage:
    """An AI message proposing no tool call. Its text is never asserted."""
    return AIMessage(content=text)


class ScriptedChatModel(GenericFakeChatModel):
    """`GenericFakeChatModel`, one scripted reply per call, that accepts tools.

    Every fake in langchain_core inherits `bind_tools` from `BaseChatModel`, which
    raises NotImplementedError, so `create_agent` cannot bind tools to a stock
    fake. Here binding records the tools' names in `bound` and changes nothing
    else: the script decides what the model proposes. Each call is counted in
    `calls`, and its input recorded in `seen`. A scripted exception is raised by
    the call that reaches it.

    Trustworthy on `invoke` only: the inherited `_stream` cannot stream a
    proposal -- with no text it raises ("No generation chunks were returned"),
    with text it drops the `tool_calls` and the proposal reads as an answer.
    Streaming arrives with the local server (serve-first-graph-locally), and
    needs the fake taught first.
    """

    calls: int = 0
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    bound: list[str] = Field(default_factory=list)

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> Any:
        self.bound = [convert_to_openai_tool(t)["function"]["name"] for t in tools]
        return self

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        # The parent's three lines, with room for a scripted exception: an
        # iterator cannot be peeked, so the reply is drawn here, not in super().
        self.calls += 1
        self.seen.append(list(messages))
        reply = next(self.messages)
        if isinstance(reply, BaseException):
            raise reply
        message = AIMessage(content=reply) if isinstance(reply, str) else reply
        return ChatResult(generations=[ChatGeneration(message=message)])


def scripted_model(script: Iterable[AIMessage | BaseException]) -> ScriptedChatModel:
    """Each message is copied as it is served, so a script may repeat one, or run
    forever: `(propose(...) for _ in itertools.count())`."""
    return ScriptedChatModel(
        messages=(m.model_copy(deep=True) if isinstance(m, AIMessage) else m for m in script)
    )


def manifested(fake: BaseTool, output: type = int) -> BaseTool:
    """A fake tool given a reading tool's manifest, under its own name: the
    factory refuses a tool without one (TOOLS-MANIFEST)."""
    from starter.domain.agents.budgets import TOOL_CALLS_PER_RUN
    from starter.domain.agents.capabilities import Capability

    fake.metadata = {
        "capability": Capability(
            name=fake.name,
            output=output,
            errors=(),
            idempotent=True,
            timeout_seconds=1.0,
            retry="none",
            calls_per_run=TOOL_CALLS_PER_RUN,
            side_effect="read",
            audit_event=None,
        )
    }
    return fake


@dataclass
class RecordingTool:
    tool: BaseTool
    calls: list[dict[str, int]]


def recording_add() -> RecordingTool:
    """A fake `add(a, b)` tool that records each call's arguments."""
    calls: list[dict[str, int]] = []

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        calls.append({"a": a, "b": b})
        return a + b

    return RecordingTool(tool=manifested(add), calls=calls)

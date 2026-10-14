"""The assistant's own middleware: the routes `create_agent` leaves open."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    hook_config,
)
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from starter.domain.agents.budgets import CONTEXT_CHARS_PER_CALL, ContextBudgetExceededError


class AnswerInvalidCalls(AgentMiddleware):
    """A reply proposing only calls whose arguments cannot be parsed is handed
    back to the model, one error tool message per call -- the model-recoverable
    class (ASSISTANT-TOOL-ERROR). Without this, `create_agent` ends the run on
    it, an empty answer (measured). Beside a well-formed call, the tool node
    answers it already."""

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.invalid_tool_calls or last.tool_calls:
            return None
        answers = [
            ToolMessage(
                content=f"Error: {call.get('error') or 'the arguments could not be parsed'}",
                tool_call_id=call["id"],
                name=call.get("name"),
                status="error",
            )
            for call in last.invalid_tool_calls
        ]
        return {"messages": answers, "jump_to": "model"}


class ContextBudget(AgentMiddleware):
    """Each model call's size, counted before it is made: over
    `CONTEXT_CHARS_PER_CALL`, the run ends without calling the model
    (ASSISTANT-CONTEXT-BUDGET)."""

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        _within_budget(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # The local server runs the graph with `astream`: a middleware with only
        # the synchronous hook raises NotImplementedError there (measured).
        _within_budget(request)
        return await handler(request)


def _within_budget(request: ModelRequest) -> None:
    system = [request.system_message] if request.system_message is not None else []
    count = call_chars([*system, *request.messages])
    if count > CONTEXT_CHARS_PER_CALL:
        raise ContextBudgetExceededError(count, CONTEXT_CHARS_PER_CALL)


def call_chars(messages: Iterable[BaseMessage]) -> int:
    """What a model call sends, in characters: each message's text, and each tool
    call's arguments. `scripts/measure_tool_loop.py` counts with this too."""
    total = 0
    for message in messages:
        content = message.content
        total += len(content if isinstance(content, str) else json.dumps(content))
        for call in getattr(message, "tool_calls", None) or []:
            total += len(json.dumps(call.get("args", {})))
    return total

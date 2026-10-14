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

from starter.domain.agents.budgets import (
    MODEL_OUTPUT_TOKENS,
    OutputBudgetExceededError,
    check_context_chars,
)


class AnswerInvalidCalls(AgentMiddleware):
    """A reply proposing only calls whose arguments cannot be parsed is handed
    back to the model, one error tool message per call -- the model-recoverable
    class (ASSISTANT-TOOL-ERROR). Without this, `create_agent` ends the run on
    it, an empty answer (measured). Beside a well-formed call, the tool node
    answers it already.

    The message is fixed: the model's own output is never repeated -- it would
    double in the context -- and a streamed reply records no parse error to
    quote. A call without an id cannot be answered, so the reply is left as it
    is, as LangChain's own patching leaves it -- answering the others would send
    the endpoint a call with no answer, which it refuses."""

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.invalid_tool_calls or last.tool_calls:
            return None
        if not all(call.get("id") for call in last.invalid_tool_calls):
            # Answering some would leave one unanswered, and the endpoint refuses
            # that. The reply is stored without them -- the same id replaces it --
            # so the thread's next turn sends no call left unanswered either.
            return {"messages": [last.model_copy(update={"invalid_tool_calls": []})]}
        answers = [
            ToolMessage(
                content=invalid_call_answer(call.get("name") or "the tool"),
                tool_call_id=call["id"],
                name=call.get("name"),
                status="error",
            )
            for call in last.invalid_tool_calls
        ]
        return {"messages": answers, "jump_to": "model"}


def invalid_call_answer(name: str) -> str:
    return f"Error: the arguments for {name} are not valid JSON; send them again as a JSON object."


class OutputBudget(AgentMiddleware):
    """A reply cut off at `MODEL_OUTPUT_TOKENS` ends the run: never taken for an
    answer, its calls never run (ASSISTANT-OUTPUT-BUDGET). Listed before
    `AnswerInvalidCalls`, so it runs first: a cut-off call is usually a malformed
    one, and is not to be handed back."""

    def after_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and _cut_off(last):
            raise OutputBudgetExceededError(MODEL_OUTPUT_TOKENS)
        return None


def _cut_off(reply: AIMessage) -> bool:
    """Stopped at the cap: its finish reason says so, or -- an Ollama model behind
    Open WebUI reports `stop` even when its own `num_predict` stopped it
    (measured) -- its output tokens reached the cap."""
    if reply.response_metadata.get("finish_reason") == "length":
        return True
    usage = reply.usage_metadata or {}
    return usage.get("output_tokens", 0) >= MODEL_OUTPUT_TOKENS


class ContextBudget(AgentMiddleware):
    """Each model call's size, counted before it is made: over
    `CONTEXT_CHARS_PER_CALL`, the run ends without calling the model
    (ASSISTANT-CONTEXT-BUDGET)."""

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        check_context_chars(request_chars(request))
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # The local server runs the graph with `astream`: a middleware with only
        # the synchronous hook raises NotImplementedError there (measured).
        check_context_chars(request_chars(request))
        return await handler(request)


def request_chars(request: ModelRequest) -> int:
    system = [request.system_message] if request.system_message is not None else []
    return call_chars([*system, *request.messages])


def call_chars(messages: Iterable[BaseMessage]) -> int:
    """What a model call sends, in characters: each message's text, each tool
    call's arguments, and each malformed call's raw arguments -- langchain-openai
    sends those too. `scripts/measure_tool_loop.py` counts with this."""
    total = 0
    for message in messages:
        content = message.content
        total += len(content if isinstance(content, str) else json.dumps(content))
        for call in getattr(message, "tool_calls", None) or []:
            total += len(json.dumps(call.get("args", {})))
        for call in getattr(message, "invalid_tool_calls", None) or []:
            total += len(call.get("args") or "")
    return total

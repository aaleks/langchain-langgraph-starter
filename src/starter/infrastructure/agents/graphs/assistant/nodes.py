"""The assistant's nodes -- each one effect, its decisions the domain's.

Each node has a synchronous and an asynchronous body: the local server runs
the graph with `astream`, and a tool written async runs only on that path.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.prebuilt import ToolNode

from starter.application.prompts import ASSISTANT_PROMPT, INVALID_CALL_ANSWER, UNRUN_CALL_ANSWER
from starter.domain.agents.budgets import (
    check_context_chars,
    check_model_calls,
    check_reply_output,
    check_tool_calls,
)
from starter.domain.agents.routing import keep_malformed_calls, unanswered_calls
from starter.infrastructure.agents.graphs.assistant.state import AssistantState


def start_run(state: AssistantState) -> dict[str, Any]:
    """Every run starts its budgets at zero, whatever the thread holds from an
    earlier run (ASSISTANT-BUDGETS-PER-RUN), and on a transcript with every call
    answered: a call an earlier run left -- it ended between a reply and its
    tools -- is answered as not run (ASSISTANT-NO-CALL-LEFT-UNANSWERED)."""
    update: dict[str, Any] = {"model_calls": 0, "tool_calls": 0}
    answered = _answer_left_calls(state["messages"])
    if answered is not None:
        # Each answer must follow its reply, before the next message: the
        # transcript is written again, in order, its ids kept.
        update["messages"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES), *answered]
    return update


def _answer_left_calls(messages: list[AnyMessage]) -> list[AnyMessage] | None:
    """The transcript with an answer after each reply for every call of it left
    unanswered, or None when there is none."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    rewritten: list[AnyMessage] = []
    added = False
    for message in messages:
        rewritten.append(message)
        if not isinstance(message, AIMessage):
            continue
        proposed = [call["id"] for call in message.tool_calls if call.get("id")]
        proposed += [call["id"] for call in message.invalid_tool_calls if call.get("id")]
        for call_id in unanswered_calls(proposed, answered):
            rewritten.append(
                ToolMessage(content=UNRUN_CALL_ANSWER, tool_call_id=call_id, status="error")
            )
            added = True
    return rewritten if added else None


def call_model(model: BaseChatModel, tools: Sequence[BaseTool]) -> Runnable:
    """Ask the model for its next reply, within the run's budgets.

    Refused before the call: past `MODEL_CALLS_PER_RUN`, or past
    `CONTEXT_CHARS_PER_CALL`. Refused after it: a reply cut off at its cap --
    never taken for an answer, its calls never run. The count is written only
    when the node finishes, so a retry of it spends no budget."""
    bound = model.bind_tools(list(tools)) if tools else model

    def prepare(state: AssistantState) -> list[BaseMessage]:
        check_model_calls(state["model_calls"])
        messages = [SystemMessage(ASSISTANT_PROMPT), *state["messages"]]
        check_context_chars(call_chars(messages))
        return messages

    def update(state: AssistantState, reply: BaseMessage) -> dict[str, Any]:
        if isinstance(reply, AIMessage):
            usage = reply.usage_metadata or {}
            check_reply_output(
                reply.response_metadata.get("finish_reason"), usage.get("output_tokens", 0)
            )
        stored = _stored(reply)
        if stored.id is not None and any(m.id == stored.id for m in state["messages"]):
            # An id the transcript holds would replace that message where it
            # stands; without one, the reply is appended under a new id.
            stored = stored.model_copy(update={"id": None})
        return {"messages": [stored], "model_calls": state["model_calls"] + 1}

    def sync(state: AssistantState) -> dict[str, Any]:
        return update(state, bound.invoke(prepare(state)))

    async def asynchronous(state: AssistantState) -> dict[str, Any]:
        return update(state, await bound.ainvoke(prepare(state)))

    return RunnableLambda(sync, afunc=asynchronous, name="call_model")


def run_tools(tools: Sequence[BaseTool]) -> Runnable:
    """Answer every call the last reply proposes, within the run's tool-call budget.

    Well-formed calls run through LangGraph's `ToolNode`: an unknown tool and
    arguments its schema refuses come back as error tool messages, and a tool's
    own exception propagates (ASSISTANT-TOOL-ERROR, ASSISTANT-ERRORS-PROPAGATE).
    Each malformed call is answered with a fixed error, so the model can send it
    again. A turn that would pass `TOOL_CALLS_PER_RUN` runs none of its calls."""
    tool_node = ToolNode(list(tools))

    def proposed(state: AssistantState) -> tuple[AIMessage, int, list[ToolMessage]]:
        reply = state["messages"][-1]
        spent = check_tool_calls(
            state["tool_calls"],
            well_formed=len(reply.tool_calls),
            malformed=len(reply.invalid_tool_calls),
        )
        return reply, spent, [_invalid_call_answer(call) for call in reply.invalid_tool_calls]

    def sync(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        reply, spent, answers = proposed(state)
        if reply.tool_calls:
            answers = [*tool_node.invoke(state, config)["messages"], *answers]
        return {"messages": answers, "tool_calls": spent}

    async def asynchronous(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        reply, spent, answers = proposed(state)
        if reply.tool_calls:
            answers = [*(await tool_node.ainvoke(state, config))["messages"], *answers]
        return {"messages": answers, "tool_calls": spent}

    return RunnableLambda(sync, afunc=asynchronous, name="run_tools")


def _stored(reply: BaseMessage) -> BaseMessage:
    """The reply as the transcript keeps it: without its malformed calls when one
    lacks an id -- it could not be answered, and the endpoint refuses a call left
    unanswered on the thread's next turn (ASSISTANT-ROUTING)."""
    if not isinstance(reply, AIMessage) or not reply.invalid_tool_calls:
        return reply
    if keep_malformed_calls(call.get("id") for call in reply.invalid_tool_calls):
        return reply
    return reply.model_copy(update={"invalid_tool_calls": []})


def _invalid_call_answer(call: dict[str, Any]) -> ToolMessage:
    """The fixed answer to a malformed call (ASSISTANT-TOOL-ERROR)."""
    return ToolMessage(
        content=INVALID_CALL_ANSWER.format(name=call.get("name") or "the tool"),
        tool_call_id=call["id"],
        name=call.get("name"),
        status="error",
    )


def call_chars(messages: Iterable[BaseMessage]) -> int:
    """What a model call sends, in characters: each message's text, each tool
    call's arguments, and each malformed call's raw arguments -- langchain-openai
    sends those too (ASSISTANT-CONTEXT-BUDGET). `scripts/measure_tool_loop.py`
    counts with this."""
    total = 0
    for message in messages:
        content = message.content
        total += len(content if isinstance(content, str) else json.dumps(content))
        for call in getattr(message, "tool_calls", None) or []:
            total += len(json.dumps(call.get("args", {})))
        for call in getattr(message, "invalid_tool_calls", None) or []:
            total += len(call.get("args") or "")
    return total

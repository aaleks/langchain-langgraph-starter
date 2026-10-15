"""The assistant's nodes -- each one effect, its decisions the domain's.

Each node has a synchronous and an asynchronous body: the local server runs
the graph with `astream`, and a tool written async runs only on that path.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
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
from langgraph.types import interrupt
from pydantic import ValidationError

from starter.application.prompts import (
    ASSISTANT_PROMPT,
    INVALID_CALL_ANSWER,
    NOT_PROPOSED_ANSWER,
    REJECTED_ANSWER,
    UNRUN_CALL_ANSWER,
)
from starter.domain.agents.approvals import (
    describe_write,
    outcome_message,
    read_decisions,
    write_key,
)
from starter.domain.agents.budgets import (
    check_context_chars,
    check_model_calls,
    check_reply_output,
    check_tool_calls,
)
from starter.domain.agents.routing import keep_malformed_calls, unanswered_calls
from starter.domain.tasks import TaskRefused, TaskWrite, write_arguments
from starter.infrastructure.agents.graphs.assistant.state import AssistantState
from starter.infrastructure.stores.tasks import TaskWriter


def start_run(state: AssistantState) -> dict[str, Any]:
    """Every run starts its budgets at zero, whatever the thread holds from an
    earlier run (ASSISTANT-BUDGETS-PER-RUN), and on a transcript with every call
    answered: a call an earlier run left -- it ended between a reply and its
    tools -- is answered as not run (ASSISTANT-NO-CALL-LEFT-UNANSWERED)."""
    update: dict[str, Any] = {"model_calls": 0, "tool_calls": 0, "write_decisions": {}}
    answered = _answer_left_calls(state["messages"])
    if answered is not None:
        # Each answer must follow its reply, before the next message: the
        # transcript is written again, in order, its ids kept.
        update["messages"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES), *answered]
    return update


def _answer_left_calls(messages: list[AnyMessage]) -> list[AnyMessage] | None:
    """The transcript with an answer after each reply for every call of it left
    unanswered, or None when there is none.

    A call is answered only by a tool message right after its reply -- what the
    endpoint checks -- never by one elsewhere: a backend may use an id again in
    a later turn. A call without an id cannot be answered, and is left."""
    rewritten: list[AnyMessage] = []
    added = False
    for index, message in enumerate(messages):
        rewritten.append(message)
        if not isinstance(message, AIMessage):
            continue
        answered = set()
        for following in messages[index + 1 :]:
            if not isinstance(following, ToolMessage):
                break
            answered.add(following.tool_call_id)
        calls = [*message.tool_calls, *message.invalid_tool_calls]
        proposed = [call["id"] for call in calls if call.get("id")]
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


def run_tools(tools: Sequence[BaseTool], writes: Mapping[str, BaseTool]) -> Runnable:
    """Answer every call the last reply proposes but its writes, within the run's
    tool-call budget -- every well-formed call counting, a write's too.

    Reads, and calls to a tool not given, run through LangGraph's `ToolNode`: an
    unknown tool and arguments its schema refuses come back as error tool
    messages, and a tool's own exception propagates (ASSISTANT-TOOL-ERROR,
    ASSISTANT-ERRORS-PROPAGATE). Each malformed call is answered with a fixed
    error. A write is checked -- by its tool's schema and the task list's rules
    -- and answered here only when refused; one accepted waits for the owner
    (ASSISTANT-WRITE-PROPOSAL). A turn that would pass `TOOL_CALLS_PER_RUN` runs
    none of its calls."""
    tool_node = ToolNode(list(tools))

    def proposed(state: AssistantState) -> tuple[AIMessage, list, int, list[ToolMessage]]:
        reply = state["messages"][-1]
        spent = check_tool_calls(
            state["tool_calls"],
            well_formed=len(reply.tool_calls),
            malformed=len(reply.invalid_tool_calls),
        )
        others = [call for call in reply.tool_calls if call["name"] not in writes]
        answers = [_invalid_call_answer(call) for call in reply.invalid_tool_calls]
        for call in reply.tool_calls:
            if call["name"] in writes:
                checked = checked_write(call, writes[call["name"]])
                if isinstance(checked, str):
                    answers.append(_not_proposed(call, checked))
        return reply, others, spent, answers

    def only(reply: AIMessage, calls: list) -> dict[str, Any]:
        # The tool node runs every call of the reply it is given: here, the others.
        return {"messages": [reply.model_copy(update={"tool_calls": calls})]}

    def sync(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        reply, others, spent, answers = proposed(state)
        if others:
            answers = [*tool_node.invoke(only(reply, others), config)["messages"], *answers]
        return {"messages": answers, "tool_calls": spent}

    async def asynchronous(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        reply, others, spent, answers = proposed(state)
        if others:
            ran = await tool_node.ainvoke(only(reply, others), config)
            answers = [*ran["messages"], *answers]
        return {"messages": answers, "tool_calls": spent}

    return RunnableLambda(sync, afunc=asynchronous, name="run_tools")


def checked_write(call: dict[str, Any], tool: BaseTool) -> TaskWrite | str:
    """The write a call proposes, checked by its tool's schema and by the task
    list's rules -- or why it was refused."""
    try:
        arguments = tool.args_schema.model_validate(call["args"]).model_dump()
    except ValidationError:
        return "its arguments do not match its schema"
    try:
        return tool.metadata["write"](**arguments)
    except TaskRefused as refused:
        return str(refused)


def _not_proposed(call: dict[str, Any], why: str) -> ToolMessage:
    return ToolMessage(
        content=NOT_PROPOSED_ANSWER.format(name=call["name"], reason=why),
        tool_call_id=call["id"],
        name=call["name"],
        status="error",
    )


def waiting_writes(messages: Sequence[AnyMessage], writes: Mapping[str, BaseTool]) -> list:
    """The last reply's write calls no tool message after it answers: those the
    checks accepted, waiting for the owner."""
    reply, answered = _last_reply(messages)
    return [
        call for call in reply.tool_calls if call["name"] in writes and call["id"] not in answered
    ]


def _last_reply(messages: Sequence[AnyMessage]) -> tuple[AIMessage, set[str]]:
    index = max(i for i, m in enumerate(messages) if isinstance(m, AIMessage))
    answered = {m.tool_call_id for m in messages[index + 1 :] if isinstance(m, ToolMessage)}
    return messages[index], answered


def review_writes(writes: Mapping[str, BaseTool]):
    """Pause for the owner's decision on each waiting write, in LangChain's
    approval request (ASSISTANT-WRITE-APPROVAL, docs/decisions/0009). Nothing is
    written here: on resume, the node runs again from the start, and returns the
    decisions as state."""

    def review(state: AssistantState) -> dict[str, Any]:
        waiting = waiting_writes(state["messages"], writes)
        checked = [checked_write(call, writes[call["name"]]) for call in waiting]
        names = list(dict.fromkeys(call["name"] for call in waiting))
        answer = interrupt(
            {
                "action_requests": [
                    {
                        "name": call["name"],
                        "args": write_arguments(write),
                        "description": describe_write(write),
                    }
                    for call, write in zip(waiting, checked, strict=True)
                ],
                "review_configs": [
                    {"action_name": name, "allowed_decisions": ["approve", "reject"]}
                    for name in names
                ],
            }
        )
        decisions = read_decisions(answer, len(waiting))
        return {
            "write_decisions": {
                call["id"]: decision for call, decision in zip(waiting, decisions, strict=True)
            }
        }

    return review


def apply_writes(writes: Mapping[str, BaseTool], writer: TaskWriter | None):
    """Decide each waiting write through the task list's writer, under the key
    from the thread, the reply and the call -- once, however often the step is
    replayed (ASSISTANT-WRITE-DECISIONS, ASSISTANT-WRITE-KEY) -- and answer each
    call with what became of it."""

    def apply(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        waiting = waiting_writes(state["messages"], writes)
        reply, _ = _last_reply(state["messages"])
        thread = config["configurable"]["thread_id"]
        # Every key before any write: one too long ends the run, nothing written.
        keys = [write_key(thread, reply.id, call["id"]) for call in waiting]
        answers = []
        for call, key in zip(waiting, keys, strict=True):
            write = checked_write(call, writes[call["name"]])
            if state["write_decisions"].get(call["id"]) == "approve":
                outcome = writer.apply(write, key)
                content = json.dumps(outcome_message(outcome))
                status = "success" if outcome.outcome == "applied" else "error"
            else:
                writer.reject(write, key)
                content, status = REJECTED_ANSWER, "error"
            answers.append(
                ToolMessage(
                    content=content, tool_call_id=call["id"], name=call["name"], status=status
                )
            )
        return {"messages": answers}

    return apply


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

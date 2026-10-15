"""The assistant's nodes -- each one effect, its decisions the domain's.

Each node has a synchronous and an asynchronous body: the local server runs
the graph with `astream`, and a tool written async runs only on that path.
"""

from __future__ import annotations

import json
import uuid
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
from langgraph.constants import CONFIG_KEY_CHECKPOINTER
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
from starter.domain.agents.routing import (
    calls_to_rename,
    keep_malformed_calls,
    unanswered_calls,
)
from starter.domain.tasks import (
    CreateTask,
    TaskRefused,
    TaskWrite,
    WriteOutcome,
    write_arguments,
)
from starter.infrastructure.agents.graphs.assistant.state import AssistantState
from starter.infrastructure.stores.tasks import TaskWriter


def start_run(writes: Mapping[str, BaseTool], writer: TaskWriter | None):
    """Every run starts its budgets at zero, whatever the thread holds from an
    earlier run (ASSISTANT-BUDGETS-PER-RUN), and on a transcript with every call
    answered: a call an earlier run left -- it ended between a reply and its
    tools -- is answered as not run (ASSISTANT-NO-CALL-LEFT-UNANSWERED). A write
    the store recorded under its key is answered with that outcome instead: the
    run that applied it may have ended before its answer was stored."""

    def start(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        update: dict[str, Any] = {"model_calls": 0, "tool_calls": 0, "write_decisions": {}}
        thread = config.get("configurable", {}).get("thread_id")

        def recorded(reply: AIMessage, call: dict[str, Any]) -> WriteOutcome | None:
            if writer is None or thread is None or call.get("name") not in writes:
                return None
            try:
                return writer.recorded(write_key(str(thread), reply.id, call["id"]))
            except ValueError:  # a key too long was never recorded
                return None

        answered = _answer_left_calls(state["messages"], recorded)
        if answered is not None:
            # Each answer must follow its reply, before the next message: the
            # transcript is written again, in order, its ids kept.
            update["messages"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES), *answered]
        return update

    return start


def _answer_left_calls(messages: list[AnyMessage], recorded) -> list[AnyMessage] | None:
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
        by_id = {call["id"]: call for call in calls if call.get("id")}
        for call_id in unanswered_calls(list(by_id), answered):
            outcome = recorded(message, by_id[call_id])
            if outcome is not None:
                rewritten.append(_answer(by_id[call_id], outcome))
            else:
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

    def proposed(
        state: AssistantState, config: RunnableConfig
    ) -> tuple[AIMessage, list, int, list[ToolMessage]]:
        reply = state["messages"][-1]
        spent = check_tool_calls(
            state["tool_calls"],
            well_formed=len(reply.tool_calls),
            malformed=len(reply.invalid_tool_calls),
        )
        others = [call for call in reply.tool_calls if call["name"] not in writes]
        answers = [_invalid_call_answer(call) for call in reply.invalid_tool_calls]
        configurable = config.get("configurable", {})
        thread = configurable.get("thread_id")
        # A pause needs a checkpointer to come back to, not only a thread id.
        checkpointer = configurable.get(CONFIG_KEY_CHECKPOINTER)
        for call in reply.tool_calls:
            if call["name"] in writes:
                checked = _proposal(call, writes[call["name"]], thread, reply.id, checkpointer)
                if isinstance(checked, str):
                    answers.append(_not_proposed(call, checked))
        return reply, others, spent, answers

    def only(reply: AIMessage, calls: list) -> dict[str, Any]:
        # The tool node runs every call of the reply it is given: here, the others.
        return {"messages": [reply.model_copy(update={"tool_calls": calls})]}

    def sync(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        reply, others, spent, answers = proposed(state, config)
        if others:
            answers = [*tool_node.invoke(only(reply, others), config)["messages"], *answers]
        return {"messages": answers, "tool_calls": spent}

    async def asynchronous(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        reply, others, spent, answers = proposed(state, config)
        if others:
            ran = await tool_node.ainvoke(only(reply, others), config)
            answers = [*ran["messages"], *answers]
        return {"messages": answers, "tool_calls": spent}

    return RunnableLambda(sync, afunc=asynchronous, name="run_tools")


def _proposal(
    call: dict[str, Any],
    tool: BaseTool,
    thread: str | None,
    reply_id: str,
    config_checkpointer: object,
) -> TaskWrite | str:
    """A write call as the owner may be asked about it -- or why it may not: its
    values refused, no thread to pause on, or a key too long to record it."""
    if thread is None or config_checkpointer is None:
        return "there is no thread to pause on for the owner's decision"
    try:
        write_key(str(thread), reply_id, call["id"])
    except ValueError:
        return "its key would be too long to record"
    return checked_write(call, tool)


def checked_write(call: dict[str, Any], tool: BaseTool) -> TaskWrite | str:
    """The write a call proposes, checked by its tool's schema -- strictly: a
    `true` or a `"1"` is not a task id -- and by the task list's rules, or why it
    was refused."""
    try:
        arguments = tool.args_schema.model_validate(call["args"], strict=True).model_dump()
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


def review_writes(writes: Mapping[str, BaseTool], writer: TaskWriter | None):
    """Pause for the owner's decision on each waiting write, in LangChain's
    approval request (ASSISTANT-WRITE-APPROVAL, docs/decisions/0009). Nothing is
    written here: on resume, the node runs again from the start, and returns the
    decisions as state. Every waiting write is asked about, in the reply's order,
    so each decision meets the action it was given for, however the rules change
    before the resume; one the rules refuse by now is shown as not valid, and
    `apply_writes` answers it."""

    def review(state: AssistantState) -> dict[str, Any]:
        asked = [
            (call, checked_write(call, writes[call["name"]]))
            for call in waiting_writes(state["messages"], writes)
        ]
        names = list(dict.fromkeys(call["name"] for call, _ in asked))
        answer = interrupt(
            {
                "action_requests": [_action_request(call, write, writer) for call, write in asked],
                "review_configs": [
                    {"action_name": name, "allowed_decisions": ["approve", "reject"]}
                    for name in names
                ],
            }
        )
        decisions = read_decisions(answer, len(asked))
        return {
            "write_decisions": {
                call["id"]: decision for (call, _), decision in zip(asked, decisions, strict=True)
            }
        }

    return review


def _action_request(
    call: dict[str, Any], write: TaskWrite | str, writer: TaskWriter | None
) -> dict[str, Any]:
    if isinstance(write, str):
        return {"name": call["name"], "args": call["args"], "description": f"Not valid: {write}"}
    return {
        "name": call["name"],
        "args": write_arguments(write),
        "description": describe_write(write, _found(writer, write)),
    }


def _found(writer: TaskWriter | None, write: TaskWrite) -> tuple[str, str] | None:
    if writer is None or isinstance(write, CreateTask):
        return None
    return writer.task(write.task_id)


def apply_writes(writes: Mapping[str, BaseTool], writer: TaskWriter | None):
    """Decide the next waiting write through the task list's writer, under the
    key from the thread, the reply and the call, and answer it with what became
    of it -- one write a step, so its answer is stored with it, and a failure
    after it never leaves it unanswered (ASSISTANT-WRITE-DECISIONS,
    ASSISTANT-WRITE-KEY).

    The answer and the route follow the outcome the writer returns, which is the
    one recorded under the key: a replay deciding otherwise is told what was
    done."""

    def apply(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        call = waiting_writes(state["messages"], writes)[0]
        reply, _ = _last_reply(state["messages"])
        decisions = dict(state["write_decisions"])
        write = checked_write(call, writes[call["name"]])
        if isinstance(write, str):
            # Refused by rules that changed while it waited: never decided.
            decisions[call["id"]] = "refused"
            return {"messages": [_not_proposed(call, write)], "write_decisions": decisions}
        key = write_key(str(config["configurable"]["thread_id"]), reply.id, call["id"])
        if decisions.get(call["id"]) == "approve":
            outcome = writer.apply(write, key)
        else:
            outcome = writer.reject(write, key)
        decisions[call["id"]] = "reject" if outcome.outcome == "rejected" else "approve"
        return {"messages": [_answer(call, outcome)], "write_decisions": decisions}

    return apply


def _answer(call: dict[str, Any], outcome: WriteOutcome) -> ToolMessage:
    if outcome.outcome == "rejected":
        content = REJECTED_ANSWER
    else:
        content = json.dumps(outcome_message(outcome))
    status = "success" if outcome.outcome == "applied" else "error"
    return ToolMessage(content=content, tool_call_id=call["id"], name=call["name"], status=status)


def _stored(reply: BaseMessage) -> BaseMessage:
    """The reply as the transcript keeps it: without its malformed calls when one
    lacks an id -- it could not be answered, and the endpoint refuses a call left
    unanswered on the thread's next turn (ASSISTANT-ROUTING) -- and each
    well-formed call under an id of its own: one missing, or already used in the
    reply, is given a new one, so no answer, decision or key can be another
    call's (ASSISTANT-STATE-CONTRACT)."""
    if not isinstance(reply, AIMessage):
        return reply
    if reply.invalid_tool_calls and not keep_malformed_calls(
        call.get("id") for call in reply.invalid_tool_calls
    ):
        reply = reply.model_copy(update={"invalid_tool_calls": []})
    malformed = {call["id"] for call in reply.invalid_tool_calls if call.get("id")}
    renamed = calls_to_rename([call.get("id") for call in reply.tool_calls], malformed)
    if not renamed:
        return reply
    calls = [dict(call) for call in reply.tool_calls]
    for position in renamed:
        calls[position]["id"] = f"call_{uuid.uuid4().hex}"
    return reply.model_copy(update={"tool_calls": calls})


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

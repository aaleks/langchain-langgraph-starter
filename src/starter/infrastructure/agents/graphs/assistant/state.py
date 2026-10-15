"""What the assistant's graph carries between nodes -- and what a checkpoint holds.

A contract, versioned (ASSISTANT-STATE-CONTRACT): a field changed without a new
version fails the suite, because a checkpoint written at one version must be
migrated to the next -- slice 5, with the first durable one. It holds messages
and counts only: never a client, a prompt or a callable.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

ASSISTANT_STATE_VERSION = 1


class AssistantInput(TypedDict):
    """What a run takes: the transcript. A count is never a caller's to set."""

    messages: Annotated[list[AnyMessage], add_messages]


class AssistantState(TypedDict):
    # The transcript; a message whose id is already present replaces it.
    messages: Annotated[list[AnyMessage], add_messages]
    # This run's model turns, and its well-formed tool calls, run or refused;
    # each set to 0 by `start_run`
    # (ASSISTANT-BUDGETS-PER-RUN).
    model_calls: int
    tool_calls: int

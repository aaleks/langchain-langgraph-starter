"""The assistant's conditional edges -- each the domain's policy, read from state."""

from __future__ import annotations

from collections.abc import Mapping

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END

from starter.domain.agents.routing import (
    route_after_reply,
    route_after_tools,
    route_after_writes,
)
from starter.infrastructure.agents.graphs.assistant.nodes import waiting_writes
from starter.infrastructure.agents.graphs.assistant.state import AssistantState


def after_reply(state: AssistantState) -> str:
    """To `run_tools` when the reply proposes any call, else the end (ASSISTANT-ROUTING)."""
    # Always the model's reply: `call_model` is the only way here.
    reply: AIMessage = state["messages"][-1]
    route = route_after_reply(
        well_formed=len(reply.tool_calls), malformed=len(reply.invalid_tool_calls)
    )
    return END if route == "end" else route


def after_tools(writes: Mapping[str, BaseTool]):
    def route(state: AssistantState) -> str:
        """To `review_writes` when a write waits for the owner, else the model."""
        return route_after_tools(waiting_writes=len(waiting_writes(state["messages"], writes)))

    return route


def after_writes(state: AssistantState) -> str:
    """To the model when every write was approved; the end when any was rejected."""
    route = route_after_writes(state["write_decisions"].values())
    return END if route == "end" else route

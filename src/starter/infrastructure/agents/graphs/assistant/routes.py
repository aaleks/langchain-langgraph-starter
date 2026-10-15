"""The assistant's conditional edges -- each the domain's policy, read from state."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.graph import END

from starter.domain.agents.routing import route_after_reply
from starter.infrastructure.agents.graphs.assistant.state import AssistantState


def after_reply(state: AssistantState) -> str:
    """To `run_tools` when the reply proposes any call, else the end (ASSISTANT-ROUTING)."""
    # Always the model's reply: `call_model` is the only way here.
    reply: AIMessage = state["messages"][-1]
    route = route_after_reply(
        well_formed=len(reply.tool_calls), malformed=len(reply.invalid_tool_calls)
    )
    return END if route == "end" else route

"""Composition: dependencies in, a compiled graph out -- the only place one is compiled."""

from __future__ import annotations

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from starter.domain.agents.budgets import MODEL_CALLS_PER_RUN


def build_assistant(model: BaseChatModel, tools: Sequence[BaseTool]) -> CompiledStateGraph:
    """The assistant: a tool loop over `model` and `tools` (docs/decisions/0005)."""
    # exit_behavior="error": the default, "end", injects an AI message saying the
    # limit was reached -- an exhausted budget that reads like an answer.
    budget = ModelCallLimitMiddleware(run_limit=MODEL_CALLS_PER_RUN, exit_behavior="error")
    return create_agent(model=model, tools=list(tools), middleware=[budget])

"""Composition: dependencies in, a compiled graph out -- the only place one is compiled."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRetryMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from starter.domain.agents.budgets import MODEL_CALLS_PER_RUN
from starter.domain.agents.retries import (
    MODEL_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_INITIAL_DELAY_SECONDS,
)


def never(failure: Exception) -> bool:
    """A retry predicate under which no failure is transient."""
    return False


def build_assistant(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    transient: Callable[[Exception], bool] = never,
    initial_delay: float = RETRY_INITIAL_DELAY_SECONDS,
) -> CompiledStateGraph:
    """The assistant: a tool loop over `model` and `tools` (docs/decisions/0005).

    `transient` decides which model failures are retried; it arrives from the
    caller, so this adapter never imports a provider -- and without one, nothing
    is retried. `initial_delay` is the first wait between tries, the domain's;
    tests pass 0.

    The budget counts model turns: a turn's retries happen inside it, so a run
    makes at most `MODEL_CALLS_PER_RUN` turns of at most `1 + MODEL_RETRIES`
    attempts each (ASSISTANT-MODEL-CALL-BUDGET).
    """
    # exit_behavior="error": the default, "end", injects an AI message saying the
    # limit was reached -- an exhausted budget that reads like an answer.
    budget = ModelCallLimitMiddleware(run_limit=MODEL_CALLS_PER_RUN, exit_behavior="error")
    # on_failure="error": the default, "continue", turns the last failure into a
    # message that reads like an answer.
    retry = ModelRetryMiddleware(
        max_retries=MODEL_RETRIES,
        retry_on=transient,
        on_failure="error",
        initial_delay=initial_delay,
        backoff_factor=RETRY_BACKOFF_FACTOR,
    )
    return create_agent(model=model, tools=list(tools), middleware=[budget, retry])

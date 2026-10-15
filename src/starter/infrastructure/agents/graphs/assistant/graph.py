"""The assistant's nodes and edges -- design.md's table, uncompiled.

`factory.py` compiles it: the only place a graph is compiled (tests/architecture).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from starter.domain.agents.retries import (
    MODEL_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_JITTER,
    RETRY_MAX_DELAY_SECONDS,
)
from starter.infrastructure.agents.graphs.assistant import nodes, routes
from starter.infrastructure.agents.graphs.assistant.state import (
    AssistantInput,
    AssistantState,
)


def assistant_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    transient: Callable[[Exception], bool],
    initial_delay: float,
) -> StateGraph:
    """`start_run`, then `call_model` and `run_tools` in turn until the model
    answers without a call (ASSISTANT-GRAPH-TOPOLOGY).

    A model failure `transient` accepts is retried by `call_model`'s policy, at
    most `MODEL_RETRIES` times, the first wait `initial_delay` and each next one
    `RETRY_BACKOFF_FACTOR` times longer, with no random part
    (ASSISTANT-TRANSIENT-RETRY); the last
    failure ends the run."""
    retry = RetryPolicy(
        max_attempts=1 + MODEL_RETRIES,
        initial_interval=initial_delay,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        max_interval=RETRY_MAX_DELAY_SECONDS,
        jitter=RETRY_JITTER,
        retry_on=transient,
    )
    builder = StateGraph(AssistantState, input_schema=AssistantInput, output_schema=AssistantInput)
    builder.add_node("start_run", nodes.start_run)
    builder.add_node("call_model", nodes.call_model(model, tools), retry_policy=retry)
    builder.add_node("run_tools", nodes.run_tools(tools))
    builder.add_edge(START, "start_run")
    builder.add_edge("start_run", "call_model")
    builder.add_conditional_edges("call_model", routes.after_reply, ["run_tools", END])
    builder.add_edge("run_tools", "call_model")
    return builder

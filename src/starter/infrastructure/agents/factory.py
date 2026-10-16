"""Composition: dependencies in, a compiled graph out -- the only place one is compiled."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from starter.domain.agents.budgets import GRAPH_STEP_CEILING, TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import check_capability
from starter.domain.agents.retries import RETRY_INITIAL_DELAY_SECONDS
from starter.infrastructure.agents.graphs.assistant.graph import assistant_graph
from starter.infrastructure.stores.tasks import TaskWriter


def build_assistant(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    transient: Callable[[Exception], bool],
    initial_delay: float = RETRY_INITIAL_DELAY_SECONDS,
    writer: TaskWriter | None = None,
) -> CompiledStateGraph:
    """The assistant: a hand-written graph over `model` and `tools`
    (docs/decisions/0007).

    `transient` decides which model failures are retried; it arrives from the
    caller, so this adapter never imports a provider. It has no default: a graph
    composed without one would quietly retry nothing. `initial_delay` is the
    first wait between tries, the domain's; tests pass 0. `writer` applies the
    writes the owner approves; a write tool without it is refused.
    """
    # Every tool's manifest, before anything is compiled (TOOLS-MANIFEST).
    for given in tools:
        metadata = given.metadata or {}
        check_capability(
            given.name,
            metadata.get("capability"),
            TOOL_CALLS_PER_RUN,
            writer_given=writer is not None,
            builder_given=callable(metadata.get("write")),
        )
    builder = assistant_graph(
        model, tools, transient=transient, initial_delay=initial_delay, writer=writer
    )
    # Set here, so neither the local server nor LangGraph's own default decides
    # it: the budgets end a run long before (ASSISTANT-MODEL-CALL-BUDGET).
    return builder.compile().with_config(recursion_limit=GRAPH_STEP_CEILING)

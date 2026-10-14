"""The assistant's tools: one module each, built over its store, each with its
capability manifest in `tool.metadata["capability"]` (TOOLS-MANIFEST)."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from starter.infrastructure.stores.tasks import TaskStore


def task_tools(store: TaskStore) -> list[BaseTool]:
    """The assistant's tools over `store` -- the one list the registry and the
    measurement both compose with."""
    from starter.infrastructure.agents.tools import list_tasks, search_tasks

    return [list_tasks.build(store), search_tasks.build(store)]

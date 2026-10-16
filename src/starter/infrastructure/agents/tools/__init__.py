"""The assistant's tools: one module each, each with its capability manifest in
`tool.metadata["capability"]` (TOOLS-MANIFEST)."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from starter.infrastructure.stores.tasks import TaskReader


def read_tools(reader: TaskReader) -> list[BaseTool]:
    """The tools that read the task list, over `reader` -- never the store, so
    no tool can reach a writer (task-writes-in-the-store, verify finding 4)."""
    from starter.infrastructure.agents.tools import list_tasks, search_tasks

    return [list_tasks.build(reader), search_tasks.build(reader)]


def write_tools() -> list[BaseTool]:
    """The tools that propose a write: they hold nothing, and the approval route
    applies what the owner approves through the writer the factory is given."""
    from starter.infrastructure.agents.tools import add_task, close_task, reassign_task

    return [add_task.build(), close_task.build(), reassign_task.build()]

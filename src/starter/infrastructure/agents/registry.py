"""The compiled graphs the local server may load -- the only names langgraph.json uses.

Loaded by the server as a file (`./src/starter/.../registry.py:assistant`), not
as a package module, so every import here is absolute.
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from starter.config.settings import Settings, settings_from_process, tasks_db_path
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.tools import task_tools
from starter.infrastructure.models import build_model, is_transient_failure
from starter.infrastructure.stores.tasks import TaskStore


def registered_assistant(settings: Settings | None = None) -> CompiledStateGraph:
    """The assistant the server serves: the settings, read now -- `.env` included,
    so nothing is read before it is loaded -- then the model they choose and the
    task list they name, opened now. A partial or malformed configuration, or a
    task list this version cannot read, is refused here, at the server's start.

    Its tools read the task list (docs/decisions/0006); each carries its
    capability manifest, which the factory checks.
    """
    settings = settings if settings is not None else settings_from_process()
    model = build_model(settings)
    store = TaskStore(tasks_db_path(settings))
    store.open()
    tools = task_tools(store)
    return build_assistant(model, tools=tools, transient=is_transient_failure)


assistant = registered_assistant()

"""The compiled graphs the local server may load -- the only names langgraph.json uses.

Loaded by the server as a file (`./src/starter/.../registry.py:assistant`), not
as a package module, so every import here is absolute.
"""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from starter.config.settings import Settings, settings_from_process
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.models import build_model, is_transient_failure


def registered_assistant(settings: Settings | None = None) -> CompiledStateGraph:
    """The assistant the server serves: the settings, read now -- `.env` included,
    so nothing is read before it is loaded -- then the model they choose. A
    partial or malformed configuration is refused here, at the server's start.

    No tools until the first real one arrives with its capability manifest
    (docs/decisions/0005; .claude/rules/langgraph/graphs.md, "Tools").
    """
    settings = settings if settings is not None else settings_from_process()
    return build_assistant(build_model(settings), tools=[], transient=is_transient_failure)


assistant = registered_assistant()

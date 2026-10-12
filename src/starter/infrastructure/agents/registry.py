"""The compiled graphs the local server may load -- the only names langgraph.json uses.

Loaded by the server as a file (`./src/starter/.../registry.py:assistant`), not
as a package module, so every import here is absolute.
"""

from __future__ import annotations

from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.models import build_offline_model

# No tools until the first real one arrives with its capability manifest
# (docs/decisions/0005; .claude/rules/langgraph/graphs.md, "Tools").
assistant = build_assistant(build_offline_model(), tools=[])

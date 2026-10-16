"""Where the local server keeps the threads' checkpoints: a SQLite file, each
checkpoint stamped with the state's version (docs/decisions/0010).

`langgraph.json` names `durable_checkpointer` as the server's custom
checkpointer, so the server opens it at start and closes it at shutdown. Loaded
by the server as a file, not as a package module, so every import here is
absolute.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from starter.config.settings import checkpoints_db_path, settings_from_process
from starter.domain.agents.state_versions import (
    CheckpointVersionError,
    checkpoint_version_refusal,
)
from starter.infrastructure.agents.graphs.assistant.state import ASSISTANT_STATE_VERSION

# The checkpoint metadata key the stamp is written under (ASSISTANT-CHECKPOINT-VERSION).
STATE_VERSION_KEY = "state_version"


class VersionedSqliteSaver(AsyncSqliteSaver):
    """`AsyncSqliteSaver`, stamping each checkpoint it writes with the state's
    version, and refusing to load one the domain refuses: every run, resume and
    continue loads its thread's checkpoint here, before any node runs."""

    state_version: int = ASSISTANT_STATE_VERSION

    async def aput(self, config, checkpoint, metadata, new_versions) -> Any:
        stamped = {**metadata, STATE_VERSION_KEY: self.state_version}
        return await super().aput(config, checkpoint, stamped, new_versions)

    async def aget_tuple(self, config) -> Any:
        found = await super().aget_tuple(config)
        if found is not None:
            stamp = (found.metadata or {}).get(STATE_VERSION_KEY)
            refusal = checkpoint_version_refusal(stamp, self.state_version)
            if refusal is not None:
                thread = config.get("configurable", {}).get("thread_id")
                raise CheckpointVersionError(f"thread {thread!r}: {refusal}")
        return found


@asynccontextmanager
async def durable_checkpointer() -> AsyncIterator[VersionedSqliteSaver]:
    """The server's checkpointer, on the file `CHECKPOINTS_DB` names -- created,
    with its folder, the first time (LOCAL-SERVER-DURABLE-APPROVAL)."""
    path = checkpoints_db_path(settings_from_process())
    path.parent.mkdir(parents=True, exist_ok=True)
    async with VersionedSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver

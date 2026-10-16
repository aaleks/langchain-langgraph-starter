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

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from starter.config.settings import Settings, checkpoints_db_path, settings_from_process
from starter.domain.agents.state_versions import (
    CheckpointVersionError,
    checkpoint_version_refusal,
)
from starter.infrastructure.agents.graphs.assistant.state import ASSISTANT_STATE_VERSION

# The checkpoint metadata key the stamp is written under (ASSISTANT-CHECKPOINT-VERSION).
STATE_VERSION_KEY = "state_version"


def strict_serializer() -> JsonPlusSerializer:
    """LangGraph's serializer in its strict mode, whatever the environment says: a
    msgpack value naming any constructor but LangGraph's and LangChain's safe
    types is not called, and pickle is refused (ASSISTANT-CHECKPOINT-STRICT). The
    file outlives the process that wrote it."""
    return JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)


class VersionedSqliteSaver(AsyncSqliteSaver):
    """`AsyncSqliteSaver`, stamping each checkpoint it writes with the state's
    version, and refusing to load one the domain refuses: every run, resume and
    continue loads its thread's checkpoint here, before any node runs.

    The stamp is the version of the code that wrote the checkpoint. A version
    that changes the shape of a channel migrates it on load, here, so a
    checkpoint written by version N always holds N's state."""

    state_version: int = ASSISTANT_STATE_VERSION

    @classmethod
    @asynccontextmanager
    async def from_conn_string(cls, conn_string: str) -> AsyncIterator[VersionedSqliteSaver]:
        async with super().from_conn_string(conn_string) as saver:
            saver.serde = strict_serializer()
            yield saver

    async def aput(self, config, checkpoint, metadata, new_versions) -> Any:
        stamped = {**metadata, STATE_VERSION_KEY: self.state_version}
        return await super().aput(config, checkpoint, stamped, new_versions)

    async def aget_tuple(self, config) -> Any:
        found = await super().aget_tuple(config)
        if found is not None:
            self._refuse_if_refused(found, config)
        return found

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        """The thread's checkpoints and writes, copied as they are -- each keeps the
        stamp of the code that wrote it -- after every one is checked: a thread
        holding a checkpoint this code refuses is not copied. The server's own
        copy would write each through `aput`, re-stamping newer state as this
        code's (verify finding)."""
        source = {"configurable": {"thread_id": source_thread_id}}
        found = [c async for c in super().alist(source)]
        for checkpoint in found:
            self._refuse_if_refused(checkpoint, source)
        for checkpoint in sorted(found, key=lambda c: c.config["configurable"]["checkpoint_id"]):
            namespace = checkpoint.config["configurable"].get("checkpoint_ns", "")
            target: dict = {
                "configurable": {"thread_id": target_thread_id, "checkpoint_ns": namespace}
            }
            parent = (checkpoint.parent_config or {}).get("configurable", {}).get("checkpoint_id")
            if parent is not None:
                target["configurable"]["checkpoint_id"] = parent
            metadata = dict(checkpoint.metadata)
            if "thread_id" in metadata:
                metadata["thread_id"] = target_thread_id
            stored = await super().aput(
                target,
                checkpoint.checkpoint,
                metadata,
                checkpoint.checkpoint.get("channel_versions", {}),
            )
            writes: dict[str, list[tuple[str, Any]]] = {}
            for task_id, channel, value in checkpoint.pending_writes or []:
                writes.setdefault(task_id, []).append((channel, value))
            for task_id, task_writes in writes.items():
                await self.aput_writes(stored, task_writes, task_id)

    def _refuse_if_refused(self, found, config) -> None:
        stamp = (found.metadata or {}).get(STATE_VERSION_KEY)
        refusal = checkpoint_version_refusal(stamp, self.state_version)
        if refusal is not None:
            thread = config.get("configurable", {}).get("thread_id")
            raise CheckpointVersionError(f"thread {thread!r}: {refusal}")


@asynccontextmanager
async def durable_checkpointer(
    settings: Settings | None = None,
) -> AsyncIterator[VersionedSqliteSaver]:
    """The server's checkpointer, on the file `CHECKPOINTS_DB` names -- created,
    with its folder, the first time (LOCAL-SERVER-DURABLE-APPROVAL). The server
    calls it with no argument: the process's settings, read now."""
    settings = settings if settings is not None else settings_from_process()
    path = checkpoints_db_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with VersionedSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver

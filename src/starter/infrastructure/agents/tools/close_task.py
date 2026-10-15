"""`close_task`: close an open task -- a proposal only, applied after the owner approves
(TOOLS-TASK-WRITES, docs/decisions/0009)."""

from __future__ import annotations

import sqlite3

from langchain_core.tools import BaseTool, tool

from starter.domain.agents.budgets import TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS, WriteOutcome, task_closing

CAPABILITY = Capability(
    name="close_task",
    output=WriteOutcome,
    # A file that cannot be written, or is locked past the timeout: it propagates.
    errors=(sqlite3.Error,),
    # Once per key, by the writer (docs/decisions/0008).
    idempotent=True,
    timeout_seconds=TASK_STORE_TIMEOUT_SECONDS,
    retry="none",
    calls_per_run=TOOL_CALLS_PER_RUN,
    side_effect="write",
    audit_event="task_writes",
)


def build() -> BaseTool:
    @tool
    def close_task(task_id: int) -> str:
        """Propose closing the open task with this id. The owner approves or rejects
        it before anything is written."""
        raise RuntimeError("close_task runs only through the owner's approval")

    # The domain's builder: checked arguments in, the write the writer applies.
    close_task.metadata = {"capability": CAPABILITY, "write": task_closing}
    return close_task

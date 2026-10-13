"""`list_tasks`: the open tasks, for the model to read (TASKS-LIST)."""

from __future__ import annotations

import json
import sqlite3

from langchain_core.tools import BaseTool, tool

from starter.domain.agents.budgets import TASK_READ_TIMEOUT_SECONDS, TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import TASK_RESULTS_LIMIT, TaskPage
from starter.infrastructure.stores.tasks import TaskStore

CAPABILITY = Capability(
    name="list_tasks",
    output=TaskPage,
    # A file that cannot be read, or is locked past the timeout: it propagates.
    errors=(sqlite3.Error,),
    idempotent=True,
    timeout_seconds=TASK_READ_TIMEOUT_SECONDS,
    retry="none",
    calls_per_run=TOOL_CALLS_PER_RUN,
    side_effect="read",
    audit_event=None,
)


def build(store: TaskStore) -> BaseTool:
    @tool
    def list_tasks() -> str:
        """List the open tasks, oldest first: each task's id, title, assignee and
        notes, and how many more open tasks there are beyond those returned."""
        return json.dumps(store.open_tasks(TASK_RESULTS_LIMIT))

    list_tasks.metadata = {"capability": CAPABILITY}
    return list_tasks

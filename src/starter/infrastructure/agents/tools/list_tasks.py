"""`list_tasks`: the open tasks, for the model to read (TASKS-LIST)."""

from __future__ import annotations

import json
import sqlite3

from langchain_core.tools import BaseTool, tool

from starter.domain.agents.budgets import TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import TASK_RESULTS_LIMIT, TASK_STORE_TIMEOUT_SECONDS, TaskPage
from starter.infrastructure.stores.tasks import TaskStore

CAPABILITY = Capability(
    name="list_tasks",
    output=TaskPage,
    # A file that cannot be read, or is locked past the timeout: it propagates.
    errors=(sqlite3.Error,),
    idempotent=True,
    timeout_seconds=TASK_STORE_TIMEOUT_SECONDS,
    retry="none",
    calls_per_run=TOOL_CALLS_PER_RUN,
    side_effect="read",
    audit_event=None,
)


def build(store: TaskStore) -> BaseTool:
    # Only a reader -- it cannot write -- waiting the manifest's timeout.
    reader = store.reader(CAPABILITY.timeout_seconds)

    @tool
    def list_tasks() -> str:
        """List the open tasks, oldest first: each task's id, title, assignee and
        notes, and how many more open tasks there are beyond those returned."""
        # The text as written: escaped, a letter outside ASCII costs the model six.
        return json.dumps(reader.open_tasks(TASK_RESULTS_LIMIT), ensure_ascii=False)

    list_tasks.metadata = {"capability": CAPABILITY}
    return list_tasks

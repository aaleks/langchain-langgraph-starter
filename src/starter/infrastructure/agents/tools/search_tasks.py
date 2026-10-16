"""`search_tasks`: the open tasks whose title or notes contain a text (TASKS-SEARCH)."""

from __future__ import annotations

import json
import sqlite3
from typing import Annotated

from langchain_core.tools import BaseTool, tool
from pydantic import StringConstraints

from starter.domain.agents.budgets import TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import (
    TASK_RESULTS_LIMIT,
    TASK_STORE_TIMEOUT_SECONDS,
    TITLE_MAX,
    TaskPage,
)
from starter.infrastructure.stores.tasks import TaskReader

# Stripped, then 1 to TITLE_MAX characters: a blank query, or one long enough
# for SQLite to refuse the pattern, fails the tool's own schema, and the tool
# loop hands that back to the model -- the list unread.
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX)]

CAPABILITY = Capability(
    name="search_tasks",
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


def build(reader: TaskReader) -> BaseTool:
    # Only a reader -- it cannot write, nor reach the store -- waiting the
    # manifest's timeout, or the manifest would say what is not so.
    if reader.timeout != CAPABILITY.timeout_seconds:
        raise ValueError(
            f"{CAPABILITY.name} waits {CAPABILITY.timeout_seconds} s; its reader {reader.timeout} s"
        )

    @tool
    def search_tasks(query: Query) -> str:
        """Find the open tasks whose title or notes contain `query`, ignoring
        case, oldest first: each task's id, title, assignee and notes, and how
        many more matched beyond those returned."""
        # The text as written: escaped, a letter outside ASCII costs the model six.
        return json.dumps(reader.search(query, TASK_RESULTS_LIMIT), ensure_ascii=False)

    search_tasks.metadata = {"capability": CAPABILITY}
    return search_tasks

"""Tasks as plain values: what a new one must hold, and the shape a read returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

# The most tasks one read returns; the rest are counted, not sent. A starting
# policy -- a model's context is the cost -- re-measured with real runs (3b).
TASK_RESULTS_LIMIT = 50


@dataclass(frozen=True)
class NewTask:
    title: str
    assignee: str
    notes: str


def new_task(title: str, assignee: str = "", notes: str = "") -> NewTask:
    """A task to add, each field without the spaces around it. A blank title is
    refused, named as the command line names it."""
    title = title.strip()
    if not title:
        raise ValueError("TITLE is blank")
    return NewTask(title=title, assignee=assignee.strip(), notes=notes.strip())


class TaskRow(TypedDict):
    id: int
    title: str
    assignee: str
    notes: str


class TaskPage(TypedDict):
    """A read's result: at most TASK_RESULTS_LIMIT tasks, and how many more matched."""

    tasks: list[TaskRow]
    more: int

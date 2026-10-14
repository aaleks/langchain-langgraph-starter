"""Tasks as plain values: what a new one must hold, and the shape a read returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

# The most tasks one read returns; the rest are counted, not sent. A starting
# policy -- a model's context is the cost -- re-measured with real runs (3b).
TASK_RESULTS_LIMIT = 50

# Each field's limit, in characters: with TASK_RESULTS_LIMIT, the most text one
# read can hand the model. Starting policies, re-measured with real runs (3b).
TITLE_MAX = 200
ASSIGNEE_MAX = 100
NOTES_MAX = 1000

# How long the task list is waited on while another process writes it, by a
# read and by the owner's add alike. A local file; a starting policy.
TASK_STORE_TIMEOUT_SECONDS = 5.0

Field = Literal["title", "assignee", "notes"]


class TaskRefused(ValueError):
    """A new task the list cannot take, naming the field at fault."""

    def __init__(self, field: Field, reason: str) -> None:
        super().__init__(f"the {field} {reason}")
        self.field = field


@dataclass(frozen=True)
class NewTask:
    title: str
    assignee: str
    notes: str


# Control characters but newline and tab: JSON sends each as six characters
# (`\u0001`), so they would slip past the length limits on the way to the model.
CONTROL = frozenset(chr(c) for c in [*range(32), 127] if chr(c) not in "\n\t")
LIMITS: dict[Field, int] = {"title": TITLE_MAX, "assignee": ASSIGNEE_MAX, "notes": NOTES_MAX}


def new_task(title: str, assignee: str = "", notes: str = "") -> NewTask:
    """A task to add, each field without the spaces around it. A blank title, a
    field over its limit, or one holding a control character, is refused,
    naming the field."""
    task = NewTask(title=title.strip(), assignee=assignee.strip(), notes=notes.strip())
    if not task.title:
        raise TaskRefused("title", "is blank")
    for field, limit in LIMITS.items():
        value = getattr(task, field)
        if len(value) > limit:
            raise TaskRefused(field, f"is longer than {limit} characters")
        if CONTROL.intersection(value):
            raise TaskRefused(field, "holds a control character")
    return task


def readable(text: str, field: Field) -> str:
    """A field as it may reach the model, whatever wrote it: no control character
    but newline and tab, and at most its limit long."""
    return "".join(c for c in text if c not in CONTROL)[: LIMITS[field]]


class TaskRow(TypedDict):
    id: int
    title: str
    assignee: str
    notes: str


class TaskPage(TypedDict):
    """A read's result: at most TASK_RESULTS_LIMIT tasks, and how many more matched."""

    tasks: list[TaskRow]
    more: int

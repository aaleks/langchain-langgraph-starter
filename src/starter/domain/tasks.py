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

TextField = Literal["title", "assignee", "notes"]
Field = TextField | Literal["task_id"]


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


# C0 control characters and DEL but newline, carriage return and tab: JSON
# sends each as six characters (`\u0001`), so they would slip past the length
# limits on the way to the model. The three kept cost two; C1 is not escaped.
CONTROL = frozenset(chr(c) for c in [*range(32), 127] if chr(c) not in "\n\r\t")
LIMITS: dict[TextField, int] = {"title": TITLE_MAX, "assignee": ASSIGNEE_MAX, "notes": NOTES_MAX}


def new_task(title: str, assignee: str = "", notes: str = "") -> NewTask:
    """A task to add, each field without the spaces around it. A blank title, a
    field over its limit, or one holding a control character, is refused,
    naming the field."""
    task = NewTask(title=title.strip(), assignee=assignee.strip(), notes=notes.strip())
    if not task.title:
        raise TaskRefused("title", "is blank")
    for field in LIMITS:
        _check_field(field, getattr(task, field))
    return task


def _check_field(field: TextField, value: str) -> None:
    limit = LIMITS[field]
    if len(value) > limit:
        raise TaskRefused(field, f"is longer than {limit} characters")
    if CONTROL.intersection(value):
        raise TaskRefused(field, "holds a control character")
    if not _encodable(value):
        raise TaskRefused(field, "holds a character UTF-8 cannot encode")


def readable(value: str, field: TextField) -> str:
    """A field as it may reach the model, whatever wrote it: without a control
    character but newline, carriage return and tab, and at most its limit long.
    (A value that is not text never arrives: the store reads it as empty.)"""
    return "".join(c for c in value if c not in CONTROL)[: LIMITS[field]]


def _encodable(text: str) -> bool:
    """A lone surrogate -- from argument bytes that were not UTF-8 -- would pass
    every other check and fail only at the write."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


class TaskRow(TypedDict):
    id: int
    title: str
    assignee: str
    notes: str


class TaskPage(TypedDict):
    """A read's result: at most TASK_RESULTS_LIMIT tasks, and how many more matched."""

    tasks: list[TaskRow]
    more: int


# -- writes: what the assistant may propose, once the owner approves (slice 4b) --


@dataclass(frozen=True)
class CreateTask:
    task: NewTask


@dataclass(frozen=True)
class CloseTask:
    task_id: int


@dataclass(frozen=True)
class ReassignTask:
    task_id: int
    assignee: str


TaskWrite = CreateTask | CloseTask | ReassignTask


def task_creation(title: str, assignee: str = "", notes: str = "") -> CreateTask:
    """A new task to add, by the owner's own rules (`new_task`)."""
    return CreateTask(new_task(title, assignee, notes))


def task_closing(task_id: int) -> CloseTask:
    return CloseTask(_checked_id(task_id))


def task_reassignment(task_id: int, assignee: str) -> ReassignTask:
    """The assignee by the rule for one, without the spaces around it; empty
    unassigns."""
    assignee = assignee.strip()
    _check_field("assignee", assignee)
    return ReassignTask(_checked_id(task_id), assignee)


# The largest id SQLite stores: a larger one cannot even be looked up.
TASK_ID_MAX = 2**63 - 1


def _checked_id(task_id: int) -> int:
    # A boolean is an int to Python, and to JSON a model may send one.
    if isinstance(task_id, bool) or not isinstance(task_id, int):
        raise TaskRefused("task_id", "is not a whole number")
    if not 1 <= task_id <= TASK_ID_MAX:
        raise TaskRefused("task_id", f"is not between 1 and {TASK_ID_MAX}")
    return task_id


# The longest key a write is recorded under: the thread, the reply and the
# call (ASSISTANT-WRITE-KEY).
WRITE_KEY_MAX = 300

WriteAction = Literal["create", "close", "reassign"]
Decision = Literal["approve", "reject"]
Outcome = Literal["applied", "refused", "rejected"]


@dataclass(frozen=True)
class WriteOutcome:
    """What became of a write: applied, refused -- the reason says why -- or
    rejected by the owner. `task_id` is the task's, when there is one."""

    outcome: Outcome
    task_id: int | None
    reason: str


def check_write_key(key: str) -> None:
    """Refuse a key that is empty or longer than WRITE_KEY_MAX."""
    if not 1 <= len(key) <= WRITE_KEY_MAX:
        raise ValueError(f"a write's key is 1 to {WRITE_KEY_MAX} characters, not {len(key)}")


def write_action(write: TaskWrite) -> WriteAction:
    if isinstance(write, CreateTask):
        return "create"
    return "close" if isinstance(write, CloseTask) else "reassign"


def write_arguments(write: TaskWrite) -> dict[str, str | int]:
    """The write's own values, as its record holds them."""
    if isinstance(write, CreateTask):
        task = write.task
        return {"title": task.title, "assignee": task.assignee, "notes": task.notes}
    if isinstance(write, CloseTask):
        return {"task_id": write.task_id}
    return {"task_id": write.task_id, "assignee": write.assignee}


def write_task_id(write: TaskWrite) -> int | None:
    """The task a write names; a creation names none until it is applied."""
    return None if isinstance(write, CreateTask) else write.task_id


def write_refusal(task_id: int, status: str | None) -> str | None:
    """Why a closing or reassignment must change nothing, from the task's status
    as found -- None when the task is open, the only state either may change."""
    if status is None:
        return f"no task {task_id}"
    return None if status == "open" else f"task {task_id} is {status}"


@dataclass(frozen=True)
class RecordedWrite:
    """A write as the task list recorded it under a key."""

    action: WriteAction
    arguments: dict[str, str | int]
    outcome: WriteOutcome


def replayed(recorded: RecordedWrite, write: TaskWrite) -> WriteOutcome:
    """What a key already recorded answers, whatever is decided now: its outcome,
    so a write is applied once and a decision is final (TASKS-WRITE-ONCE). A key
    recording another write is a caller's bug, refused."""
    if (recorded.action, recorded.arguments) != (write_action(write), write_arguments(write)):
        raise ValueError("the key already records another write")
    return recorded.outcome

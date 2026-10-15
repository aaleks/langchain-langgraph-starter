"""The owner's approval of a write: what they are shown, what their answer means,
and the key a decision is recorded under (docs/decisions/0009)."""

from __future__ import annotations

from starter.domain.tasks import (
    CreateTask,
    Decision,
    ReassignTask,
    TaskWrite,
    WriteOutcome,
    check_write_key,
)


def describe_write(write: TaskWrite) -> str:
    """One line the owner reads before deciding."""
    if isinstance(write, CreateTask):
        assigned = f", assigned to {write.task.assignee}" if write.task.assignee else ""
        return f'Add the task "{write.task.title}"{assigned}'
    if isinstance(write, ReassignTask):
        if not write.assignee:
            return f"Unassign task {write.task_id}"
        return f"Reassign task {write.task_id} to {write.assignee}"
    return f"Close task {write.task_id}"


def read_decisions(resume: object, count: int) -> list[Decision]:
    """The owner's answer to `count` actions, in order. Only an exact
    `{"type": "approve"}` approves; anything else rejects -- and an answer that
    is not `{"decisions": [...]}` of `count` items rejects every action: the safe
    outcome is no effect."""
    decisions = resume.get("decisions") if isinstance(resume, dict) else None
    if not isinstance(decisions, list) or len(decisions) != count:
        return ["reject"] * count
    return ["approve" if decision == {"type": "approve"} else "reject" for decision in decisions]


def write_key(thread_id: str, reply_id: str, call_id: str) -> str:
    """The key a decision is recorded under: the thread, the reply that proposed
    the call, the call -- the same however often the write is replayed. Not the
    superstep: a replay runs the write at another one (ASSISTANT-WRITE-KEY)."""
    key = f"{thread_id}:{reply_id}:{call_id}"
    check_write_key(key)
    return key


def outcome_message(outcome: WriteOutcome) -> dict[str, str | int | None]:
    """What the model reads of an applied or refused write."""
    message: dict[str, str | int | None] = {"outcome": outcome.outcome, "task_id": outcome.task_id}
    if outcome.outcome == "refused":
        message["reason"] = outcome.reason
    return message

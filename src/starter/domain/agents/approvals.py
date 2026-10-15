"""The owner's approval of a write: what they are shown, what their answer means,
and the key a decision is recorded under (docs/decisions/0009)."""

from __future__ import annotations

import json
import unicodedata

from starter.domain.tasks import (
    CreateTask,
    Decision,
    ReassignTask,
    TaskWrite,
    WriteOutcome,
    check_write_key,
)


def describe_write(write: TaskWrite, found: tuple[str, str] | None = None) -> str:
    """One line the owner reads before deciding. A task named by its id is named
    by its title and status as the list holds them -- `found` -- never by the
    model's word for it. Text from the list or the model is quoted as JSON, so a
    quote or a line break in it cannot read as another action."""
    if isinstance(write, CreateTask):
        assigned = f", assigned to {_quoted(write.task.assignee)}" if write.task.assignee else ""
        return f"Add the task {_quoted(write.task.title)}{assigned}"
    task = f"task {write.task_id}{_as_found(found)}"
    if isinstance(write, ReassignTask):
        if not write.assignee:
            return f"Unassign {task}"
        return f"Reassign {task}, to {_quoted(write.assignee)}"
    return f"Close {task}"


def _as_found(found: tuple[str, str] | None) -> str:
    if found is None:
        return ", which does not exist"
    title, status = found
    # A fixed word, whatever a file written elsewhere holds as a status.
    return f", {_quoted(title)}" + ("" if status == "open" else ", closed")


# Characters an approval UI may draw as a line break or reorder -- line and
# paragraph separators, C1 controls, bidi overrides -- so a description could
# read as another action. JSON escapes the C0 controls; these are escaped too.
_UNSEEN = frozenset({"Cc", "Cf", "Zl", "Zp"})


def _quoted(text: str) -> str:
    quoted = json.dumps(text, ensure_ascii=False)
    return "".join(f"\\u{ord(c):04x}" if unicodedata.category(c) in _UNSEEN else c for c in quoted)


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
    superstep: a replay runs the write at another one. A JSON array: each part
    comes from outside, and a `:` in one must not make it another's
    (ASSISTANT-WRITE-KEY)."""
    key = json.dumps([thread_id, reply_id, call_id], ensure_ascii=False)
    check_write_key(key)
    return key


def outcome_message(outcome: WriteOutcome) -> dict[str, str | int | None]:
    """What the model reads of an applied or refused write."""
    message: dict[str, str | int | None] = {"outcome": outcome.outcome, "task_id": outcome.task_id}
    if outcome.outcome == "refused":
        message["reason"] = outcome.reason
    return message

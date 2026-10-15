"""The writes the task list can take -- built only from values that pass its rules."""

from __future__ import annotations

import pytest

from starter.domain.tasks import (
    CloseTask,
    CreateTask,
    NewTask,
    ReassignTask,
    TaskRefused,
    task_closing,
    task_creation,
    task_reassignment,
)


class TestTaskWriteValues:
    """TASKS-WRITE-VALUES: A write to the task list SHALL be built only from valid
    values: `task_creation(title, assignee, notes)` by TASKS-ADD's rule for each
    field; `task_closing(task_id)` and `task_reassignment(task_id, assignee)` from a
    task id that is a positive integer, not a boolean, and an assignee by
    TASKS-ADD's rule for one -- empty unassigns. A value refused SHALL raise
    `TaskRefused`, naming the field: `title`, `assignee`, `notes` or `task_id`."""

    @pytest.mark.parametrize(
        ("built", "write"),
        [
            (
                lambda: task_creation(" Renew passport ", " sam ", ""),
                CreateTask(NewTask("Renew passport", "sam", "")),
            ),
            (lambda: task_closing(7), CloseTask(7)),
            (lambda: task_reassignment(7, " ana "), ReassignTask(7, "ana")),
            (lambda: task_reassignment(7, ""), ReassignTask(7, "")),
        ],
        ids=["creation", "closing", "reassignment", "unassigned"],
    )
    def test_writes_are_built_from_valid_values(self, built, write):
        assert built() == write

    @pytest.mark.parametrize(
        ("built", "field"),
        [
            (lambda: task_creation("   ", "", ""), "title"),
            (lambda: task_closing(0), "task_id"),
            (lambda: task_closing(-1), "task_id"),
            (lambda: task_closing(True), "task_id"),
            (lambda: task_reassignment(7, "a" * 101), "assignee"),
            (lambda: task_reassignment(7, "x\x1b"), "assignee"),
        ],
        ids=["blank-title", "id-0", "id-negative", "id-boolean", "long-assignee", "control"],
    )
    def test_counter_example_a_value_refused_names_its_field(self, built, field):
        with pytest.raises(TaskRefused) as refused:
            built()

        assert refused.value.field == field

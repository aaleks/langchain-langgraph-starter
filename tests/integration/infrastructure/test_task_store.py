"""The task list's file, opened through `infrastructure/stores/tasks.py` -- a real
SQLite file in a temporary directory, never the owner's."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from starter.infrastructure.stores.tasks import TaskStore


def version_and_tasks(path: Path) -> tuple[int, int]:
    with sqlite3.connect(path) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    db.close()
    return version, count


def sqlite_file(path: Path, *statements: str) -> Path:
    db = sqlite3.connect(path)
    for statement in statements:
        db.execute(statement)
    db.commit()
    db.close()
    return path


class TestTaskSchema:
    """TASKS-SCHEMA: Opening the task list SHALL create the file -- its directory
    included -- and its schema at version 1 when the file does not exist or is
    empty, leave a version-1 list as it is, and refuse any other file -- a newer
    version, or a file that is not a task list -- naming the file, nothing
    written."""

    def test_a_missing_file_and_directory_are_created_at_version_1(self, tmp_path):
        path = tmp_path / "lists" / "tasks.sqlite3"

        TaskStore(path).open()

        assert version_and_tasks(path) == (1, 0)

    def test_an_empty_file_is_created_at_version_1(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        path.write_bytes(b"")

        TaskStore(path).open()

        assert version_and_tasks(path) == (1, 0)

    def test_a_version_1_list_is_left_as_it_is(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()
        sqlite_file(
            path,
            "INSERT INTO tasks (title) VALUES ('Renew passport')",
            "INSERT INTO tasks (title) VALUES ('Call the plumber')",
        )
        before = path.read_bytes()

        TaskStore(path).open()

        assert version_and_tasks(path) == (1, 2)
        assert path.read_bytes() == before

    @pytest.mark.parametrize(
        ("make", "named"),
        [
            (lambda p: sqlite_file(p, "CREATE TABLE t (x)", "PRAGMA user_version = 2"), "2"),
            (lambda p: sqlite_file(p, "CREATE TABLE notes (text TEXT)"), None),
            (lambda p: p.write_text("not a database\n", encoding="utf-8"), None),
        ],
        ids=["a-newer-version", "another-table-at-version-0", "a-text-file"],
    )
    def test_counter_example_a_file_that_is_not_this_task_list_is_refused(
        self, tmp_path, make, named
    ):
        path = tmp_path / "tasks.sqlite3"
        make(path)
        before = path.read_bytes()

        with pytest.raises(ValueError) as refused:
            TaskStore(path).open()

        assert str(path) in str(refused.value)
        if named:
            assert f"version {named}" in str(refused.value)
        assert path.read_bytes() == before

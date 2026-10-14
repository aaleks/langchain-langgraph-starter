"""The task list's file, opened through `infrastructure/stores/tasks.py` -- a real
SQLite file in a temporary directory, never the owner's."""

from __future__ import annotations

import shutil
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


def interrupted_copy(path: Path, copy: Path) -> Path:
    """`path` copied in the middle of a write of 2,000 tasks, its journal beside
    it -- what a writer killed mid-commit leaves behind."""
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA cache_size = 1")  # spill to the file, so the journal is hot
    db.execute("BEGIN EXCLUSIVE")
    db.executemany("INSERT INTO tasks (title) VALUES (?)", [("x" * 150,)] * 2000)
    shutil.copy(path, copy)
    shutil.copy(f"{path}-journal", f"{copy}-journal")
    db.execute("ROLLBACK")
    db.close()
    return copy


class TestTaskSchema:
    """TASKS-SCHEMA: Opening the task list SHALL create the file -- its directory
    included -- and its schema at version 1, in one transaction, when the file
    does not exist or holds no table at version 0; use a version-1 list as it is,
    first recovering a write that was interrupted; and refuse any other file -- a
    newer version, or a file that is not a task list -- naming the file, nothing
    written. The schema SHALL hold each field to its limit (TASKS-ADD)."""

    def test_a_missing_file_and_directory_are_created_at_version_1(self, tmp_path):
        path = tmp_path / "lists" / "tasks.sqlite3"

        TaskStore(path).open()

        assert version_and_tasks(path) == (1, 0)

    def test_an_empty_file_is_created_at_version_1(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        path.write_bytes(b"")

        TaskStore(path).open()

        assert version_and_tasks(path) == (1, 0)

    def test_a_sqlite_file_at_version_0_with_no_table_is_created_at_version_1(self, tmp_path):
        # A header written, no table: not 0 bytes, and not a task list yet.
        path = sqlite_file(tmp_path / "tasks.sqlite3", "PRAGMA application_id = 7")
        assert path.stat().st_size > 0

        TaskStore(path).open()

        assert version_and_tasks(path) == (1, 0)

    def test_an_interrupted_write_is_recovered_not_refused(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()
        sqlite_file(path, "INSERT INTO tasks (title) VALUES ('Renew passport')")
        crashed = interrupted_copy(path, tmp_path / "crashed.sqlite3")
        journal = Path(f"{crashed}-journal")
        assert journal.exists()

        TaskStore(crashed).open()

        assert version_and_tasks(crashed) == (1, 1)
        assert not journal.exists()

    def test_the_schema_holds_the_limits(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()

        with pytest.raises(sqlite3.IntegrityError):
            sqlite_file(path, f"INSERT INTO tasks (title) VALUES ('{'t' * 201}')")

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

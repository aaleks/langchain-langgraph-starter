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


# Version 1 as ADR 0006 wrote it: what an owner's list holds before this version.
VERSION_1 = (
    "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL "
    "CHECK (length(trim(title)) > 0 AND length(title) <= 200), assignee TEXT NOT NULL "
    "DEFAULT '' CHECK (length(assignee) <= 100), notes TEXT NOT NULL DEFAULT '' "
    "CHECK (length(notes) <= 1000), status TEXT NOT NULL DEFAULT 'open' "
    "CHECK (status IN ('open', 'closed')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
)


def version_1_list(path: Path, *titles: str) -> Path:
    return sqlite_file(
        path,
        VERSION_1,
        "PRAGMA user_version = 1",
        *[f"INSERT INTO tasks (title) VALUES ('{title}')" for title in titles],
    )


def tables(path: Path) -> list[str]:
    db = sqlite3.connect(path)
    names = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    db.close()
    return [name for (name,) in names]


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
    included -- and its schema at version 2, in one transaction, when the file does
    not exist or holds no table at version 0; migrate a version-1 list forward to
    version 2 -- adding the table `task_writes` (TASKS-AUDIT), its tasks unchanged
    -- in one transaction; use a version-2 list as it is; recover a write that was
    interrupted first; and refuse any other file -- a newer version, or a file that
    is not a task list -- naming the file, nothing written. The schema SHALL hold
    each field to its limit (TASKS-ADD)."""

    def test_a_missing_file_and_directory_are_created_at_version_2(self, tmp_path):
        path = tmp_path / "lists" / "tasks.sqlite3"

        TaskStore(path).open()

        assert version_and_tasks(path) == (2, 0)
        assert tables(path) == ["task_writes", "tasks"]

    def test_an_empty_file_is_created_at_version_2(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        path.write_bytes(b"")

        TaskStore(path).open()

        assert version_and_tasks(path) == (2, 0)

    def test_a_sqlite_file_at_version_0_with_no_table_is_created_at_version_2(self, tmp_path):
        # A header written, no table: not 0 bytes, and not a task list yet.
        path = sqlite_file(tmp_path / "tasks.sqlite3", "PRAGMA application_id = 7")
        assert path.stat().st_size > 0

        TaskStore(path).open()

        assert version_and_tasks(path) == (2, 0)

    def test_an_interrupted_write_is_recovered_not_refused(self, tmp_path):
        path = version_1_list(tmp_path / "tasks.sqlite3", "Renew passport")
        crashed = interrupted_copy(path, tmp_path / "crashed.sqlite3")
        journal = Path(f"{crashed}-journal")
        assert journal.exists()

        TaskStore(crashed).open()

        assert version_and_tasks(crashed) == (2, 1)
        assert not journal.exists()

    @pytest.mark.parametrize(
        "insert",
        [
            f"INSERT INTO tasks (title) VALUES ('{'t' * 201}')",
            f"INSERT INTO tasks (title, assignee) VALUES ('t', '{'a' * 101}')",
            f"INSERT INTO tasks (title, notes) VALUES ('t', '{'n' * 1001}')",
        ],
        ids=["title-201", "assignee-101", "notes-1001"],
    )
    def test_the_schema_holds_the_limits(self, tmp_path, insert):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()

        with pytest.raises(sqlite3.IntegrityError):
            sqlite_file(path, insert)

    def test_a_creation_that_fails_midway_leaves_the_file_blank(self, tmp_path, monkeypatch):
        from starter.infrastructure.stores import tasks as stores

        class FailsAtTheVersion:
            def __init__(self, db):
                self.db = db

            def execute(self, sql, *args):
                if sql.startswith("PRAGMA user_version ="):
                    raise sqlite3.OperationalError("interrupted before the version")
                return self.db.execute(sql, *args)

            def close(self):
                self.db.close()

        real = stores._connect
        monkeypatch.setattr(stores, "_connect", lambda *a, **k: FailsAtTheVersion(real(*a, **k)))
        path = tmp_path / "tasks.sqlite3"

        with pytest.raises(sqlite3.OperationalError):
            TaskStore(path).open()

        db = sqlite3.connect(path)
        tables = db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        version = db.execute("PRAGMA user_version").fetchone()[0]
        db.close()
        assert (version, tables) == (0, [])

    def test_a_migration_that_fails_midway_leaves_the_list_at_version_1(
        self, tmp_path, monkeypatch
    ):
        from starter.infrastructure.stores import tasks as stores

        class FailsAtTheVersion:
            def __init__(self, db):
                self.db = db

            def execute(self, sql, *args):
                if sql.startswith("PRAGMA user_version ="):
                    raise sqlite3.OperationalError("interrupted before the version")
                return self.db.execute(sql, *args)

            def close(self):
                self.db.close()

        path = version_1_list(tmp_path / "tasks.sqlite3", "Renew passport", "Call the plumber")
        real = stores._connect
        monkeypatch.setattr(stores, "_connect", lambda *a, **k: FailsAtTheVersion(real(*a, **k)))

        with pytest.raises(sqlite3.OperationalError):
            TaskStore(path).open()

        assert version_and_tasks(path) == (1, 2)
        assert tables(path) == ["tasks"]

    def test_a_list_another_opener_made_first_is_left_as_it_is(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()
        sqlite_file(path, "INSERT INTO tasks (title) VALUES ('Renew passport')")

        # As if this opener had looked at the file before the other made it.
        TaskStore(path)._create()

        assert version_and_tasks(path) == (2, 1)

    def test_a_version_1_list_is_migrated_its_tasks_unchanged(self, tmp_path):
        path = version_1_list(tmp_path / "tasks.sqlite3", "Renew passport", "Call the plumber")

        TaskStore(path).open()

        assert version_and_tasks(path) == (2, 2)
        assert tables(path) == ["task_writes", "tasks"]
        db = sqlite3.connect(path)
        rows = db.execute("SELECT id, title, status FROM tasks ORDER BY id").fetchall()
        writes = db.execute("SELECT COUNT(*) FROM task_writes").fetchone()[0]
        db.close()
        assert rows == [(1, "Renew passport", "open"), (2, "Call the plumber", "open")]
        assert writes == 0

    def test_a_version_2_list_is_left_as_it_is(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()
        sqlite_file(
            path,
            "INSERT INTO tasks (title) VALUES ('Renew passport')",
            "INSERT INTO tasks (title) VALUES ('Call the plumber')",
        )
        before = path.read_bytes()

        TaskStore(path).open()

        assert version_and_tasks(path) == (2, 2)
        assert path.read_bytes() == before

    @pytest.mark.parametrize(
        ("make", "named"),
        [
            (lambda p: sqlite_file(p, "CREATE TABLE t (x)", "PRAGMA user_version = 3"), "3"),
            (
                lambda p: sqlite_file(p, "CREATE TABLE notes (x)", "PRAGMA user_version = 1"),
                None,
            ),
            (lambda p: sqlite_file(p, VERSION_1, "PRAGMA user_version = 2"), "2"),
            (lambda p: sqlite_file(p, "CREATE TABLE notes (text TEXT)"), None),
            (lambda p: p.write_text("not a database\n", encoding="utf-8"), None),
        ],
        ids=[
            "a-newer-version",
            "version-1-no-tasks",
            "version-2-no-task-writes",
            "another-table-at-version-0",
            "a-text-file",
        ],
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

    def test_counter_example_a_busy_list_is_not_called_not_a_task_list(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        TaskStore(path).open()
        holder = sqlite3.connect(path, isolation_level=None)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            with pytest.raises(sqlite3.OperationalError):
                TaskStore(path, timeout=1.0).open()
        finally:
            holder.execute("ROLLBACK")
            holder.close()

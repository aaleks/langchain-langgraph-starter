"""`starter tasks add`, driven through the entry point's `main`, against a task
list in a temporary directory -- never the owner's."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from starter.cli.main import main


def open_tasks(path: Path) -> list[tuple[int, str, str, str]]:
    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT id, title, assignee, notes FROM tasks WHERE status = 'open' ORDER BY id"
    ).fetchall()
    db.close()
    return rows


@pytest.fixture
def tasks_db(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "tasks.sqlite3"
    monkeypatch.setenv("TASKS_DB", str(path))
    return path


class TestTasksAdd:
    """TASKS-ADD: `starter tasks add TITLE [--assignee NAME] [--notes TEXT]` SHALL
    add one open task to the task list `TASKS_DB` names -- its title, assignee
    and notes with the spaces around them removed -- print its id alone on
    standard output, and exit 0. A blank title SHALL be refused with exit status
    2 and a message on standard error naming `TITLE`, nothing written; a task
    list that TASKS-SCHEMA refuses SHALL end the command with exit status 1 and
    a message on standard error naming the file."""

    def test_two_tasks_added(self, tasks_db, capsys):
        first = main(["tasks", "add", "  Renew passport ", "--assignee", "sam"])
        first_out = capsys.readouterr().out
        second = main(["tasks", "add", "Call the plumber", "--notes", "after 5pm"])
        second_out = capsys.readouterr().out

        assert (first, first_out) == (0, "1\n")
        assert (second, second_out) == (0, "2\n")
        assert open_tasks(tasks_db) == [
            (1, "Renew passport", "sam", ""),
            (2, "Call the plumber", "", "after 5pm"),
        ]

    @pytest.mark.parametrize("title", ["   ", ""], ids=["spaces", "empty"])
    def test_counter_example_a_blank_title_is_refused_nothing_written(
        self, tasks_db, capsys, title
    ):
        status = main(["tasks", "add", title])
        printed = capsys.readouterr()

        assert status == 2
        assert "TITLE" in printed.err
        assert printed.out == ""
        assert not tasks_db.exists() or open_tasks(tasks_db) == []

    def test_counter_example_a_task_list_that_cannot_be_opened_is_refused(self, tasks_db, capsys):
        db = sqlite3.connect(tasks_db)
        db.execute("CREATE TABLE t (x)")
        db.execute("PRAGMA user_version = 2")
        db.commit()
        db.close()
        before = tasks_db.read_bytes()

        status = main(["tasks", "add", "Renew passport"])
        printed = capsys.readouterr()

        assert status == 1
        assert str(tasks_db) in printed.err
        assert printed.out == ""
        assert tasks_db.read_bytes() == before

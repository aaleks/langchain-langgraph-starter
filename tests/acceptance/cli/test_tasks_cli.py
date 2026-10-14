"""`starter tasks add`, driven through the `starter` script's own function and
its `main`, against a task list in a temporary directory -- never the owner's."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from starter.cli.main import main, run


def open_tasks(path: Path) -> list[tuple[int, str, str, str]]:
    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT id, title, assignee, notes FROM tasks WHERE status = 'open' ORDER BY id"
    ).fetchall()
    db.close()
    return rows


def script(monkeypatch, *argv: str) -> int:
    """The `starter` script, as the shell runs it: its exit status."""
    monkeypatch.setattr(sys, "argv", ["starter", *argv])
    with pytest.raises(SystemExit) as exited:
        run()
    return exited.value.code


@pytest.fixture
def tasks_db(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "tasks.sqlite3"
    monkeypatch.setenv("TASKS_DB", str(path))
    return path


class TestTasksAdd:
    """TASKS-ADD: `starter tasks add TITLE [--assignee NAME] [--notes TEXT]` SHALL
    add one open task to the task list `TASKS_DB` names -- its title (at most
    `TITLE_MAX`, 200 characters), assignee (at most `ASSIGNEE_MAX`, 100) and notes
    (at most `NOTES_MAX`, 1,000), each with the spaces around it removed -- print
    its id alone on standard output, and exit 0. A blank title, or a field over
    its limit, SHALL be refused with exit status 2 and a message on standard
    error naming it -- `TITLE`, `--assignee`, `--notes` -- nothing written, the
    file not even created. A task list that cannot be opened or written --
    TASKS-SCHEMA refusing it, or the file system -- and settings that cannot be
    read SHALL end the command with exit status 1 and a message on standard
    error naming the file, never a traceback."""

    def test_two_tasks_added(self, tasks_db, capsys, monkeypatch):
        first = script(monkeypatch, "tasks", "add", "  Renew passport ", "--assignee", " sam ")
        first_out = capsys.readouterr().out
        second = script(monkeypatch, "tasks", "add", "Call the plumber", "--notes", " after 5pm  ")
        second_out = capsys.readouterr().out

        assert (first, first_out) == (0, "1\n")
        assert (second, second_out) == (0, "2\n")
        assert open_tasks(tasks_db) == [
            (1, "Renew passport", "sam", ""),
            (2, "Call the plumber", "", "after 5pm"),
        ]

    @pytest.mark.parametrize(
        ("args", "named"),
        [
            (["   "], "TITLE"),
            ([""], "TITLE"),
            (["t" * 201], "TITLE"),
            (["Renew passport", "--assignee", "a" * 101], "--assignee"),
            (["Renew passport", "--notes", "n" * 1001], "--notes"),
        ],
        ids=["spaces", "empty", "title-201", "assignee-101", "notes-1001"],
    )
    def test_counter_example_refused_nothing_written(
        self, tasks_db, capsys, monkeypatch, args, named
    ):
        status = script(monkeypatch, "tasks", "add", *args)
        printed = capsys.readouterr()

        assert status == 2
        assert named in printed.err
        assert printed.out == ""
        assert not tasks_db.exists()

    def test_the_limits_themselves_are_accepted(self, tasks_db, capsys):
        status = main(["tasks", "add", "t" * 200, "--assignee", "a" * 100, "--notes", "n" * 1000])

        assert (status, capsys.readouterr().out) == (0, "1\n")

    def test_counter_example_a_task_list_that_cannot_be_opened_is_refused(
        self, tasks_db, capsys, monkeypatch
    ):
        db = sqlite3.connect(tasks_db)
        db.execute("CREATE TABLE t (x)")
        db.execute("PRAGMA user_version = 2")
        db.commit()
        db.close()
        before = tasks_db.read_bytes()

        status = script(monkeypatch, "tasks", "add", "Renew passport")
        printed = capsys.readouterr()

        assert status == 1
        assert str(tasks_db) in printed.err
        assert "Traceback" not in printed.err
        assert printed.out == ""
        assert tasks_db.read_bytes() == before

    def test_counter_example_a_directory_as_the_task_list_is_refused(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setenv("TASKS_DB", str(tmp_path))

        status = main(["tasks", "add", "Renew passport"])
        printed = capsys.readouterr()

        assert status == 1
        assert str(tmp_path) in printed.err
        assert printed.out == ""
        assert list(tmp_path.iterdir()) == []

    def test_counter_example_settings_that_cannot_be_read_are_refused(
        self, tmp_path, capsys, monkeypatch
    ):
        from starter.config import settings as settings_module

        dotenv = tmp_path / ".env"
        dotenv.write_text("OPENWEBUI_MODEL=llama3.1:8b\n", encoding="utf-16")
        monkeypatch.setattr(settings_module, "DOTENV", dotenv)
        monkeypatch.delenv("TASKS_DB")

        status = main(["tasks", "add", "Renew passport"])
        printed = capsys.readouterr()

        assert status == 1
        assert str(dotenv) in printed.err
        assert printed.out == ""

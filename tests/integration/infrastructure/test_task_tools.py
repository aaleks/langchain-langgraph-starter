"""The assistant's task tools over a real task list in a temporary directory: what
each returns to the model, as the JSON the model reads."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from starter.domain.tasks import new_task
from starter.infrastructure.agents.tools import list_tasks, search_tasks
from starter.infrastructure.stores.tasks import TaskReader, TaskStore
from tests.fakes import answer, propose


def task_list(path: Path, *tasks: tuple[str, str, str]) -> TaskStore:
    store = TaskStore(path)
    store.open()
    for title, assignee, notes in tasks:
        store.add(new_task(title, assignee, notes))
    return store


def close(path: Path, *ids: int) -> None:
    db = sqlite3.connect(path)
    db.executemany("UPDATE tasks SET status = 'closed' WHERE id = ?", [(i,) for i in ids])
    db.commit()
    db.close()


def ids(result: str) -> list[int]:
    return [task["id"] for task in json.loads(result)["tasks"]]


def run_proposing(fake_llm, tool, args: dict) -> tuple[list, object]:
    """The assistant, its model proposing one call of `tool`, then answering."""
    from starter.infrastructure.agents.factory import build_assistant

    model = fake_llm([propose((tool.name, args)), answer()])
    graph = build_assistant(model, [tool], transient=lambda failure: False)
    return graph.invoke({"messages": [HumanMessage("go")]})["messages"], model


class TestListTasks:
    """TASKS-LIST: The tool `list_tasks`, taking no arguments, SHALL return the open
    tasks in the order they were added -- at most `TASK_RESULTS_LIMIT` (50) -- as
    the JSON object `{"tasks": [{"id", "title", "assignee", "notes"}, ...], "more":
    n}`, `n` being how many more open tasks there are -- the rows and `n` seeing one
    state of the list -- its text as written: a letter outside ASCII as itself, not
    escaped. Whatever the file holds, each field SHALL reach the model at most its
    limit long (TASKS-ADD), without a C0 control character or DEL but newline,
    carriage return and tab, a value that is not text as empty, and text that is not
    UTF-8 with U+FFFD in place of what cannot be decoded: one read hands it at most
    50 tasks of 1,300 characters, each at most doubled by JSON's escapes (measured:
    132,713 characters, ids 1 to 50). A task list another process holds locked SHALL
    end the run with the store's error after waiting `TASK_STORE_TIMEOUT_SECONDS` --
    SQLite's own wait, which overshoots it (measured: 1 s given, 1.8 s taken; 5 s,
    7.4 s)."""

    def test_the_open_tasks_in_order(self, tmp_path):
        store = task_list(
            tmp_path / "tasks.sqlite3",
            ("Renew passport", "sam", ""),
            ("Call the plumber", "", "after 5pm"),
        )

        result = list_tasks.build(store).invoke({})

        assert json.loads(result) == {
            "tasks": [
                {"id": 1, "title": "Renew passport", "assignee": "sam", "notes": ""},
                {"id": 2, "title": "Call the plumber", "assignee": "", "notes": "after 5pm"},
            ],
            "more": 0,
        }

    def test_text_as_written(self, tmp_path):
        notes = "line one\r\nline two\tend"
        store = task_list(tmp_path / "tasks.sqlite3", ("Čestitka za Ivana ☕", "", notes))

        result = list_tasks.build(store).invoke({})

        assert "Čestitka za Ivana ☕" in result
        assert json.loads(result)["tasks"][0]["notes"] == notes

    @pytest.mark.parametrize(("count", "returned", "more"), [(51, 50, 1), (50, 50, 0), (0, 0, 0)])
    def test_past_the_limit(self, tmp_path, count, returned, more):
        from starter.domain.tasks import TASK_RESULTS_LIMIT

        store = task_list(
            tmp_path / "tasks.sqlite3", *[(f"Task {n}", "", "") for n in range(1, count + 1)]
        )

        result = json.loads(list_tasks.build(store).invoke({}))

        assert TASK_RESULTS_LIMIT == 50
        assert [t["id"] for t in result["tasks"]] == list(range(1, returned + 1))
        assert result["more"] == more

    def test_a_list_another_process_holds_locked_ends_the_run(
        self, tmp_path, fake_llm, monkeypatch
    ):
        from starter.infrastructure.agents.factory import build_assistant

        path = tmp_path / "tasks.sqlite3"
        store = task_list(path, ("Renew passport", "", ""))
        monkeypatch.setattr(
            list_tasks, "CAPABILITY", replace(list_tasks.CAPABILITY, timeout_seconds=1.0)
        )
        model = fake_llm([propose(("list_tasks", {})), answer()])
        graph = build_assistant(model, [list_tasks.build(store)], transient=lambda failure: False)
        holder = sqlite3.connect(path, isolation_level=None)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            started = time.monotonic()
            with pytest.raises(sqlite3.OperationalError):
                graph.invoke({"messages": [HumanMessage("go")]})
            waited = time.monotonic() - started
        finally:
            holder.execute("ROLLBACK")
            holder.close()

        # Measured: 1 s given, 1.8 s taken. Under 3 s: one wait, not two.
        assert 1.0 <= waited < 3.0
        assert model.calls == 1

    def test_a_list_written_without_the_limits_reaches_the_model_within_them(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        db = sqlite3.connect(path)
        db.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title, assignee, "
            "notes, status TEXT NOT NULL DEFAULT 'open', created_at TEXT)"
        )
        db.execute("PRAGMA user_version = 1")
        db.execute(
            "INSERT INTO tasks (title, assignee, notes) VALUES (?, ?, ?)",
            ("Pay\x01" + "t" * 300, "\x1b" + "a" * 2000, "\x07\x7f" + "n" * 2_000_000),
        )
        db.execute(
            "INSERT INTO tasks (title, assignee, notes) VALUES (?, ?, ?)", ("Blob", "", b"\x00\x01")
        )
        db.execute(
            "INSERT INTO tasks (title, assignee, notes) VALUES (NULL, 42, CAST(x'ff' AS TEXT))"
        )
        db.execute("INSERT INTO tasks (title, assignee, notes) VALUES (x'00', x'01', x'02')")
        db.commit()
        db.close()
        store = TaskStore(path)
        store.open()

        first, second, third, fourth = json.loads(list_tasks.build(store).invoke({}))["tasks"]

        assert first["title"] == "Pay" + "t" * 197
        assert first["assignee"] == "a" * 100
        assert first["notes"] == "n" * 1000
        assert second["notes"] == ""
        assert (third["title"], third["assignee"], third["notes"]) == ("", "", "\ufffd")
        assert (fourth["title"], fourth["assignee"], fourth["notes"]) == ("", "", "")

    def test_at_the_bound(self, tmp_path):
        store = task_list(tmp_path / "tasks.sqlite3", *[('"' * 200, '"' * 100, '"' * 1000)] * 51)

        result = list_tasks.build(store).invoke({})

        assert len(result) == 132_713

    def test_the_rows_and_more_see_one_state_of_the_list(self, tmp_path, monkeypatch):
        path = tmp_path / "tasks.sqlite3"
        store = task_list(path, ("One", "", ""), ("Two", "", ""))
        original = TaskReader.connection

        @contextmanager
        def interleaved(self):
            with original(self) as db:
                yield AddsAfterTheRows(db, path)

        monkeypatch.setattr(TaskReader, "connection", interleaved)

        result = json.loads(list_tasks.build(store).invoke({}))

        assert [t["id"] for t in result["tasks"]] == [1, 2]
        assert result["more"] == 0

    def test_counter_example_a_closed_task_is_not_listed(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        store = task_list(path, ("One", "", ""), ("Two", "", ""), ("Three", "", ""))
        close(path, 2)

        result = list_tasks.build(store).invoke({})

        assert ids(result) == [1, 3]
        assert json.loads(result)["more"] == 0


class AddsAfterTheRows:
    """A connection that lets another process add a task once the read's rows
    are fetched, before its count: what a writer between the two would do."""

    def __init__(self, db: sqlite3.Connection, path: Path) -> None:
        self.db, self.path, self.done = db, path, False

    def execute(self, sql: str, *args):
        cursor = self.db.execute(sql, *args)
        if sql.startswith("SELECT id") and not self.done:
            self.done = True
            rows = cursor.fetchall()
            other = sqlite3.connect(self.path, timeout=0)
            try:
                other.execute("INSERT INTO tasks (title) VALUES ('Three')")
                other.commit()
            except sqlite3.OperationalError:
                pass  # held off by the read's own transaction: what it is for
            finally:
                other.close()
            return Fetched(rows)
        return cursor


class Fetched:
    def __init__(self, rows: list) -> None:
        self.rows = rows

    def fetchall(self) -> list:
        return self.rows


SEARCHED = [
    ("Renew passport", "", ""),
    ("Call the plumber", "", "bring the PASSPORT copy"),
    ("Pay 100% deposit", "", ""),
    ("Pay 1000 deposit", "", ""),
    ("file_tax", "", ""),
    ("file tax", "", ""),
    ("copy a\\b", "", ""),
    ("copy ab", "", ""),
    ("Sale", "", "save 50% off"),
    ("Promo", "", "save 500 off"),
    ("Čestitka", "", ""),
]


class TestSearchTasks:
    r"""TASKS-SEARCH: The tool `search_tasks(query)` SHALL return the open tasks whose
    title or notes contain the query -- the spaces around it removed, ASCII letters
    matched regardless of case, every other character as itself, `%`, `_` and `\`
    included -- in the order they were added, at most `TASK_RESULTS_LIMIT`, in
    `list_tasks`' shape and bounds, its text as written. A blank query, or one over
    `TITLE_MAX` characters, SHALL be handed back to the model as an error answering
    its call, the list not read."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("passport", [1, 2]),
            ("  PassPort ", [1, 2]),
            ("100%", [3]),
            ("file_tax", [5]),
            ("a\\b", [7]),
            ("50% off", [9]),
            ("čestitka", []),
            ("Čestitka", [11]),
            ("x" * 200, []),
            ("plumber", [2]),
            ("holiday", []),
        ],
    )
    def test_what_a_query_matches(self, tmp_path, query, expected):
        store = task_list(tmp_path / "tasks.sqlite3", *SEARCHED)

        result = search_tasks.build(store).invoke({"query": query})

        assert ids(result) == expected
        assert json.loads(result)["more"] == 0

    def test_text_as_written(self, tmp_path):
        store = task_list(tmp_path / "tasks.sqlite3", *SEARCHED)

        result = search_tasks.build(store).invoke({"query": "Čestitka"})

        assert '"Čestitka"' in result

    def test_past_the_limit(self, tmp_path):
        store = task_list(
            tmp_path / "tasks.sqlite3", *[(f"Task {n}", "", "") for n in range(1, 52)]
        )

        result = json.loads(search_tasks.build(store).invoke({"query": "task"}))

        assert [t["id"] for t in result["tasks"]] == list(range(1, 51))
        assert result["more"] == 1

    @pytest.mark.parametrize("query", ["   ", "%" * 201], ids=["blank", "over-the-limit"])
    def test_counter_example_a_refused_query_goes_back_to_the_model_unread(
        self, tmp_path, fake_llm, monkeypatch, query
    ):
        def unread(self, query, limit):  # the list must not be read
            raise AssertionError("the list was read for a refused query")

        monkeypatch.setattr(TaskReader, "search", unread)
        store = task_list(tmp_path / "tasks.sqlite3")

        messages, _ = run_proposing(fake_llm, search_tasks.build(store), {"query": query})

        tool_message = messages[2]
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        assert tool_message.status == "error"
        assert tool_message.tool_call_id == messages[1].tool_calls[0]["id"]

    def test_counter_example_a_closed_task_is_not_found(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        store = task_list(path, *SEARCHED)
        close(path, 1)

        result = search_tasks.build(store).invoke({"query": "passport"})

        assert ids(result) == [2]

"""The assistant's task tools over a real task list in a temporary directory: what
each returns to the model, as the JSON the model reads."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from starter.domain.tasks import new_task
from starter.infrastructure.agents.tools import list_tasks, search_tasks
from starter.infrastructure.stores.tasks import TaskStore
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


class TestListTasks:
    """TASKS-LIST: The tool `list_tasks`, taking no arguments, SHALL return the
    open tasks in the order they were added -- at most `TASK_RESULTS_LIMIT` (50)
    -- as the JSON object `{"tasks": [{"id", "title", "assignee", "notes"}, ...],
    "more": n}`, `n` being how many more open tasks there are."""

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

    def test_counter_example_a_closed_task_is_not_listed(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"
        store = task_list(path, ("One", "", ""), ("Two", "", ""), ("Three", "", ""))
        close(path, 2)

        result = list_tasks.build(store).invoke({})

        assert ids(result) == [1, 3]
        assert json.loads(result)["more"] == 0


SEARCHED = [
    ("Renew passport", "", ""),
    ("Call the plumber", "", "bring the PASSPORT copy"),
    ("Pay 100% deposit", "", ""),
    ("Pay 1000 deposit", "", ""),
    ("file_tax", "", ""),
    ("file tax", "", ""),
]


class TestSearchTasks:
    """TASKS-SEARCH: The tool `search_tasks(query)` SHALL return the open tasks
    whose title or notes contain the query -- the spaces around it removed,
    ASCII letters matched regardless of case, every other character as itself,
    `%` and `_` included -- in the order they were added, at most
    `TASK_RESULTS_LIMIT`, in `list_tasks`' shape. A blank query SHALL be handed
    back to the model as an error answering its call, the list not read."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("passport", [1, 2]),
            ("  PassPort ", [1, 2]),
            ("100%", [3]),
            ("file_tax", [5]),
            ("plumber", [2]),
            ("holiday", []),
        ],
    )
    def test_what_a_query_matches(self, tmp_path, query, expected):
        store = task_list(tmp_path / "tasks.sqlite3", *SEARCHED)

        result = search_tasks.build(store).invoke({"query": query})

        assert ids(result) == expected
        assert json.loads(result)["more"] == 0

    def test_past_the_limit(self, tmp_path):
        store = task_list(
            tmp_path / "tasks.sqlite3", *[(f"Task {n}", "", "") for n in range(1, 52)]
        )

        result = json.loads(search_tasks.build(store).invoke({"query": "task"}))

        assert [t["id"] for t in result["tasks"]] == list(range(1, 51))
        assert result["more"] == 1

    def test_counter_example_a_blank_query_goes_back_to_the_model_unread(self, tmp_path, fake_llm):
        from starter.infrastructure.agents.factory import build_assistant

        class Unread(TaskStore):
            def search(self, query, limit):  # the list must not be read
                raise AssertionError("the list was read for a blank query")

        store = Unread(tmp_path / "tasks.sqlite3")
        store.open()
        model = fake_llm([propose(("search_tasks", {"query": "   "})), answer()])
        graph = build_assistant(model, [search_tasks.build(store)], transient=lambda failure: False)

        messages = graph.invoke({"messages": [HumanMessage("find it")]})["messages"]

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

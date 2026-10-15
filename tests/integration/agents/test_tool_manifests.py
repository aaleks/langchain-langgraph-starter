"""Every tool the factory composes carries a capability manifest it can honour --
checked before anything is compiled."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, replace

import pytest
from langchain_core.tools import tool

from starter.domain.agents.budgets import TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS, TaskPage
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.tools import list_tasks, search_tasks
from starter.infrastructure.stores.tasks import TaskStore
from tests.fakes import answer

READ = Capability(
    name="add",
    output=int,
    errors=(),
    idempotent=True,
    timeout_seconds=1.0,
    retry="none",
    calls_per_run=TOOL_CALLS_PER_RUN,
    side_effect="read",
    audit_event=None,
)


def plain(name: str = "add", capability: object | None = None):
    """A tool named `name`, carrying `capability` -- or no manifest at all."""

    def body(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    made = tool(name, body)
    if capability is not None:
        made.metadata = {"capability": capability}
    return made


def reader_of(built_tool):
    """The view of the store a task tool reads through, from its closure."""
    cells = [cell.cell_contents for cell in built_tool.func.__closure__ or ()]
    return next(c for c in cells if hasattr(c, "open_tasks"))


class TestToolManifests:
    """TOOLS-MANIFEST: Every tool the factory is given SHALL carry a capability
    manifest -- the tool's name, its output's type, the errors it raises, whether
    it is idempotent, its timeout, its retry class, its rate limit and its
    side-effect level, and its audit event; its input's schema is the tool's own.
    The factory SHALL refuse, before compiling anything and naming the tool, a
    manifest the assistant cannot honour: none, or one that is not a manifest;
    one naming another tool; a side effect other than `read` -- no write has an
    approval route before slice 4; a retry class other than `none` -- a tool's
    failure propagates; a rate limit other than the run's `TOOL_CALLS_PER_RUN`,
    the one limit enforced. A tool declaring `read` SHALL be given only a view
    of its store that refuses a write."""

    def test_the_task_tools_manifests(self, tmp_path, fake_llm):
        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        tools = [list_tasks.build(store), search_tasks.build(store)]

        rows = [
            (
                t.name,
                sorted(t.args),
                {k: v for k, v in asdict(t.metadata["capability"]).items() if k != "output"},
            )
            for t in tools
        ]

        expected = {
            "errors": (sqlite3.Error,),
            "idempotent": True,
            "timeout_seconds": TASK_STORE_TIMEOUT_SECONDS,
            "retry": "none",
            "calls_per_run": TOOL_CALLS_PER_RUN,
            "side_effect": "read",
            "audit_event": None,
        }
        assert rows == [
            ("list_tasks", [], {"name": "list_tasks", **expected}),
            ("search_tasks", ["query"], {"name": "search_tasks", **expected}),
        ]
        assert all(t.metadata["capability"].output is TaskPage for t in tools)
        model = fake_llm([answer()])
        graph = build_assistant(model, tools, transient=lambda failure: False)
        graph.invoke({"messages": [("human", "hello")]})
        assert model.bound == ["list_tasks", "search_tasks"]

    def test_the_task_tools_read_through_a_view_that_refuses_a_write(self, tmp_path):
        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()

        for built in (list_tasks.build(store), search_tasks.build(store)):
            held = [cell.cell_contents for cell in built.func.__closure__ or ()]
            assert not any(isinstance(h, TaskStore) for h in held)
            reader = reader_of(built)
            assert not any(
                isinstance(v, TaskStore) or isinstance(getattr(v, "__self__", None), TaskStore)
                for v in vars(reader).values()
            )
            assert not hasattr(reader, "add")
            assert reader.timeout == built.metadata["capability"].timeout_seconds
            for statement in (
                "INSERT INTO tasks (title) VALUES ('sneaked in')",
                "PRAGMA query_only = OFF",
                f"ATTACH DATABASE '{tmp_path / 'other.sqlite3'}' AS other",
            ):
                with reader.connection() as db, pytest.raises(sqlite3.DatabaseError):
                    db.execute(statement)
            assert not (tmp_path / "other.sqlite3").exists()

    @pytest.mark.parametrize(
        ("tools", "named"),
        [
            ([plain()], ["add"]),
            ([plain(capability={"name": "add", "side_effect": "read"})], ["add"]),
            ([plain(capability=replace(READ, name="sum"))], ["add", "sum"]),
            ([plain(capability=replace(READ, side_effect="write"))], ["add", "write"]),
            ([plain(capability=replace(READ, side_effect="network"))], ["add", "network"]),
            ([plain(capability=replace(READ, retry="transient"))], ["add", "transient"]),
            ([plain(capability=replace(READ, retry="always"))], ["add", "always"]),
            ([plain(capability=replace(READ, calls_per_run=5))], ["add", "5"]),
            ([plain(capability=replace(READ, calls_per_run=21))], ["add", "21"]),
            ([plain(capability=READ), plain("sub")], ["sub"]),
        ],
        ids=[
            "no-manifest",
            "not-a-manifest",
            "another-tools-manifest",
            "a-write",
            "another-side-effect",
            "a-retry",
            "another-retry-class",
            "a-rate-limit-not-enforced",
            "a-rate-limit-over-the-budget",
            "the-second-tool-unmanifested",
        ],
    )
    def test_counter_example_a_tool_the_assistant_cannot_honour_is_refused(
        self, fake_llm, monkeypatch, tools, named
    ):
        from starter.infrastructure.agents import factory

        compiled = []
        monkeypatch.setattr(factory, "assistant_graph", lambda *a, **kw: compiled.append(a))

        with pytest.raises(ValueError) as refused:
            build_assistant(fake_llm([answer()]), tools, transient=lambda failure: False)

        assert all(name in str(refused.value) for name in named), str(refused.value)
        assert compiled == []

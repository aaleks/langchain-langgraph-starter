"""Every tool the factory composes carries a capability manifest it can honour --
checked before anything is compiled."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, replace

import pytest
from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool

from starter.domain.agents.budgets import TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS, TaskPage, WriteOutcome
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.tools import list_tasks, read_tools, search_tasks, write_tools
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
WRITE = replace(READ, side_effect="write", audit_event="task_writes")


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


@pytest.fixture
def store(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    store.open()
    return store


class TestToolManifests:
    """TOOLS-MANIFEST: Every tool the factory is given SHALL carry a capability manifest --
    the tool's name, its output's type, the errors it raises, whether it is
    idempotent, its timeout, its retry class, its rate limit and its side-effect
    level, and its audit event; its input's schema is the tool's own. The factory
    SHALL refuse, before compiling anything and naming the tool, a manifest the
    assistant cannot honour: none, or one that is not a manifest; one naming another
    tool; a side effect other than `read` or `write`; a `write` that is not
    idempotent or names no audit event, or that arrives without the task list's
    writer or without a builder turning its arguments into a write -- each write
    runs only through the approval route (ASSISTANT-WRITE-APPROVAL), applied by that
    writer; a retry class other than `none` -- a tool's failure propagates; a rate
    limit other than the run's `TOOL_CALLS_PER_RUN`, the one limit enforced. A tool
    declaring `read` SHALL be given only a view of its store that refuses a write,
    never the store."""

    def test_the_task_tools_manifests(self, store, fake_llm):
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]

        rows = [
            (
                t.name,
                sorted(t.args),
                {k: v for k, v in asdict(t.metadata["capability"]).items() if k != "output"},
            )
            for t in tools
        ]

        common = {
            "errors": (sqlite3.Error,),
            "idempotent": True,
            "timeout_seconds": TASK_STORE_TIMEOUT_SECONDS,
            "retry": "none",
            "calls_per_run": TOOL_CALLS_PER_RUN,
        }
        read = {**common, "side_effect": "read", "audit_event": None}
        write = {**common, "side_effect": "write", "audit_event": "task_writes"}
        assert rows == [
            ("list_tasks", [], {"name": "list_tasks", **read}),
            ("search_tasks", ["query"], {"name": "search_tasks", **read}),
            ("add_task", ["assignee", "notes", "title"], {"name": "add_task", **write}),
            ("close_task", ["task_id"], {"name": "close_task", **write}),
            ("reassign_task", ["assignee", "task_id"], {"name": "reassign_task", **write}),
        ]
        assert [t.metadata["capability"].output for t in tools] == [TaskPage] * 2 + [
            WriteOutcome
        ] * 3
        model = fake_llm([answer()])
        graph = build_assistant(
            model, tools, transient=lambda failure: False, writer=store.writer()
        )
        graph.invoke({"messages": [("human", "hello")]})
        assert sorted(model.bound) == [
            "add_task",
            "close_task",
            "list_tasks",
            "reassign_task",
            "search_tasks",
        ]

    def test_the_task_reads_read_through_a_view_that_refuses_a_write(self, store, tmp_path):
        given = store.reader(TASK_STORE_TIMEOUT_SECONDS)

        for built in (list_tasks.build(given), search_tasks.build(given)):
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

    def test_counter_example_a_reader_waiting_other_than_its_manifest_is_refused(self, store):
        with pytest.raises(ValueError) as refused:
            list_tasks.build(store.reader(1.0))

        assert TASK_STORE_TIMEOUT_SECONDS == 5.0
        assert "list_tasks" in str(refused.value)

    @pytest.mark.parametrize(
        ("tools", "with_writer", "named"),
        [
            ([plain()], False, ["add"]),
            ([plain(capability={"name": "add", "side_effect": "read"})], False, ["add"]),
            ([plain(capability=replace(READ, name="sum"))], False, ["add", "sum"]),
            ([plain(capability=WRITE)], False, ["add", "writer"]),
            ([plain(capability=replace(WRITE, idempotent=False))], True, ["add", "idempotent"]),
            ([plain(capability=replace(WRITE, audit_event=None))], True, ["add", "audit"]),
            ([plain(capability=WRITE)], True, ["add", "builder"]),
            ([plain(capability=replace(READ, side_effect="network"))], False, ["add", "network"]),
            ([plain(capability=replace(READ, retry="transient"))], False, ["add", "transient"]),
            ([plain(capability=replace(READ, retry="always"))], False, ["add", "always"]),
            ([plain(capability=replace(READ, calls_per_run=5))], False, ["add", "5"]),
            ([plain(capability=replace(READ, calls_per_run=21))], False, ["add", "21"]),
            ([plain(capability=READ), plain("sub")], False, ["sub"]),
        ],
        ids=[
            "no-manifest",
            "not-a-manifest",
            "another-tools-manifest",
            "a-write-without-a-writer",
            "a-write-not-idempotent",
            "a-write-without-an-audit-event",
            "a-write-without-a-builder",
            "another-side-effect",
            "a-retry",
            "another-retry-class",
            "a-rate-limit-not-enforced",
            "a-rate-limit-over-the-budget",
            "the-second-tool-unmanifested",
        ],
    )
    def test_counter_example_a_tool_the_assistant_cannot_honour_is_refused(
        self, fake_llm, monkeypatch, store, tools, with_writer, named
    ):
        from starter.infrastructure.agents import factory

        compiled = []
        monkeypatch.setattr(factory, "assistant_graph", lambda *a, **kw: compiled.append(a))

        with pytest.raises(ValueError) as refused:
            build_assistant(
                fake_llm([answer()]),
                tools,
                transient=lambda failure: False,
                writer=store.writer() if with_writer else None,
            )

        assert all(name in str(refused.value) for name in named), str(refused.value)
        assert compiled == []


class TestTaskWriteTools:
    """TOOLS-TASK-WRITES: The assistant SHALL offer the model three write tools, each with
    its input schema: `add_task(title: str, assignee: str = "", notes: str = "")`,
    `close_task(task_id: int)` and `reassign_task(task_id: int, assignee: str)`.
    Each SHALL be only a proposal: called directly, outside the approval route, it
    SHALL raise `RuntimeError` and write nothing."""

    @staticmethod
    def schema(built) -> tuple[list[str], dict[str, str]]:
        parameters = convert_to_openai_tool(built)["function"]["parameters"]
        types = {name: spec["type"] for name, spec in parameters["properties"].items()}
        return sorted(parameters.get("required", [])), types

    @staticmethod
    def defaults(built) -> dict[str, object]:
        properties = convert_to_openai_tool(built)["function"]["parameters"]["properties"]
        return {name: spec["default"] for name, spec in properties.items() if "default" in spec}

    def test_the_schemas_the_model_sees(self):
        tools = {t.name: t for t in write_tools()}

        assert self.schema(tools["add_task"]) == (
            ["title"],
            {"title": "string", "assignee": "string", "notes": "string"},
        )
        assert self.defaults(tools["add_task"]) == {"assignee": "", "notes": ""}
        assert self.schema(tools["close_task"]) == (["task_id"], {"task_id": "integer"})
        assert self.defaults(tools["close_task"]) == {}
        assert self.defaults(tools["reassign_task"]) == {}
        assert self.schema(tools["reassign_task"]) == (
            ["assignee", "task_id"],
            {"task_id": "integer", "assignee": "string"},
        )

    @pytest.mark.parametrize(
        ("name", "arguments"),
        [
            ("add_task", {"title": "Renew passport"}),
            ("close_task", {"task_id": 1}),
            ("reassign_task", {"task_id": 1, "assignee": "ana"}),
        ],
    )
    def test_counter_example_called_directly_nothing_is_written(self, store, name, arguments):
        called = next(t for t in write_tools() if t.name == name)

        with pytest.raises(RuntimeError):
            called.invoke(arguments)

        assert store.reader(1.0).open_tasks(50) == {"tasks": [], "more": 0}

"""Every tool the factory composes carries a capability manifest it can honour --
checked before anything is compiled."""

from __future__ import annotations

from dataclasses import replace

import pytest
from langchain_core.tools import tool

from starter.domain.agents.budgets import TASK_READ_TIMEOUT_SECONDS, TOOL_CALLS_PER_RUN
from starter.domain.agents.capabilities import Capability
from starter.domain.tasks import TaskPage
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


def plain(name: str = "add", capability: Capability | None = None):
    """A tool named `name`, carrying `capability` -- or no manifest at all."""

    def body(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    made = tool(name, body)
    if capability is not None:
        made.metadata = {"capability": capability}
    return made


class TestToolManifests:
    """TOOLS-MANIFEST: Every tool the factory is given SHALL carry a capability
    manifest -- the tool's name, its output's type, the errors it raises, whether
    it is idempotent, its timeout, its retry class, its rate limit, its
    side-effect level and its audit event; its input's schema is the tool's own.
    The factory SHALL refuse, before compiling anything and naming the tool, a
    tool without a manifest, a manifest naming another tool, and a manifest
    declaring a side effect other than `read`: no write has an approval route
    before slice 4."""

    def test_the_task_tools_manifests(self, tmp_path, fake_llm):
        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        tools = [list_tasks.build(store), search_tasks.build(store)]

        manifests = [t.metadata["capability"] for t in tools]

        assert [
            (m.name, m.side_effect, m.idempotent, m.retry, m.audit_event) for m in manifests
        ] == [
            ("list_tasks", "read", True, "none", None),
            ("search_tasks", "read", True, "none", None),
        ]
        assert all(m.output is TaskPage for m in manifests)
        assert all(m.timeout_seconds == TASK_READ_TIMEOUT_SECONDS for m in manifests)
        assert all(m.calls_per_run == TOOL_CALLS_PER_RUN for m in manifests)
        model = fake_llm([answer()])
        graph = build_assistant(model, tools, transient=lambda failure: False)
        graph.invoke({"messages": [("human", "hello")]})
        assert model.bound == ["list_tasks", "search_tasks"]

    @pytest.mark.parametrize(
        ("tools", "named"),
        [
            ([plain()], ["add"]),
            ([plain(capability=replace(READ, name="sum"))], ["add", "sum"]),
            ([plain(capability=replace(READ, side_effect="write"))], ["add", "write"]),
            ([plain(capability=READ), plain("sub")], ["sub"]),
        ],
        ids=["no-manifest", "another-tools-manifest", "a-write", "the-second-tool-unmanifested"],
    )
    def test_counter_example_a_tool_the_assistant_cannot_honour_is_refused(
        self, fake_llm, monkeypatch, tools, named
    ):
        from starter.infrastructure.agents import factory

        compiled = []
        monkeypatch.setattr(factory, "create_agent", lambda **kw: compiled.append(kw))

        with pytest.raises(ValueError) as refused:
            build_assistant(fake_llm([answer()]), tools, transient=lambda failure: False)

        assert all(name in str(refused.value) for name in named), str(refused.value)
        assert compiled == []

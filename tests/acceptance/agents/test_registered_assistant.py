"""The story test of register-first-graph: the graph the local server would load.

Driven through the real entry point -- `langgraph.json`, resolved the way the
server resolves a file path -- with nothing faked but the network, which is
refused outright.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from langgraph.pregel import Pregel

from tests.fakes import answer
from tests.openwebui_stub import STUB_ANSWER, openwebui_stub, tool_call

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "langgraph.json"


def load_registered(graph_id: str):
    """Load the graph `langgraph.json` names, as a standalone file -- as the server
    does -- under a fresh module name, so it is built again, here."""
    spec = json.loads(CONFIG.read_text(encoding="utf-8"))["graphs"][graph_id]
    path, _, attr = spec.rpartition(":")
    module_spec = importlib.util.spec_from_file_location(
        f"registered_{graph_id}_{uuid.uuid4().hex[:8]}", REPO / path
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return getattr(module, attr), module


@pytest.fixture
def registry():
    """Imported per test, not at collection: a story test that is red must not
    stop the rest of the suite."""
    from starter.infrastructure.agents import registry

    return registry


@pytest.fixture
def build_assistant():
    from starter.infrastructure.agents.factory import build_assistant

    return build_assistant


def offered(graph) -> list[str]:
    """The tools a compiled tool loop offers its model, by name."""
    return sorted(graph.nodes["tools"].bound.tools_by_name)


def types(messages: list) -> list[str]:
    return [m.type for m in messages]


class TestAssistantIsRegistered:
    """ASSISTANT-REGISTERED: `langgraph.json` SHALL register exactly one graph,
    under the id `assistant`, bound to the `assistant` export of
    `src/starter/infrastructure/agents/registry.py`. That export SHALL be the
    graph the factory compiles -- so it carries the budgets and the retry policy
    -- with the model the process's settings choose and the tools `list_tasks`
    and `search_tasks` over the task list they name, both read when it is
    loaded; with no model configured it SHALL complete runs with every outbound
    network connection refused."""

    def test_langgraph_json_registers_the_assistant_and_nothing_else(self):
        graphs = json.loads(CONFIG.read_text(encoding="utf-8"))["graphs"]

        assert graphs == {"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}
        loaded, module = load_registered("assistant")
        assert isinstance(loaded, Pregel)
        bound = {name for name, value in vars(module).items() if isinstance(value, Pregel)}
        assert bound == {"assistant"}

    def test_with_nothing_configured_the_registered_graph_answers_offline(self, registry):
        from starter.config.settings import Settings
        from starter.infrastructure.models import OFFLINE_ANSWER

        graph = registry.registered_assistant(Settings("", "", ""))
        messages = graph.invoke({"messages": [HumanMessage("hello")]})["messages"]

        assert types(messages) == ["human", "ai"]
        assert messages[-1].content == OFFLINE_ANSWER

    def test_with_open_webui_configured_the_registered_graph_asks_it(self, monkeypatch):
        with openwebui_stub() as stub:
            # The process's settings, as the server has them when it loads the file.
            monkeypatch.setenv("OPENWEBUI_URL", stub.url + "/")
            monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-local")
            monkeypatch.setenv("OPENWEBUI_MODEL", "llama3.1:8b")
            registered, _ = load_registered("assistant")
            messages = registered.invoke({"messages": [HumanMessage("hello")]})["messages"]

        assert types(messages) == ["human", "ai"]
        assert messages[-1].content == STUB_ANSWER
        assert [(r["path"], r["authorization"]) for r in stub.requests] == [
            ("/api/chat/completions", "Bearer sk-local")
        ]
        assert stub.requests[0]["body"]["model"] == "llama3.1:8b"

    def test_partly_configured_is_refused_at_start_naming_what_is_missing(self, monkeypatch):
        # The key stays as the suite set it -- empty, and so not read from .env.
        monkeypatch.setenv("OPENWEBUI_URL", "http://localhost:3000")
        monkeypatch.setenv("OPENWEBUI_MODEL", "llama3.1:8b")

        with pytest.raises(ValueError) as refused:
            load_registered("assistant")

        assert str(refused.value).endswith("missing: OPENWEBUI_API_KEY")

    def test_a_task_list_this_version_cannot_read_is_refused_at_start(self, monkeypatch, tmp_path):
        import sqlite3

        path = tmp_path / "tasks.sqlite3"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE t (x)")
        db.execute("PRAGMA user_version = 2")
        db.commit()
        db.close()
        monkeypatch.setenv("TASKS_DB", str(path))

        with pytest.raises(ValueError) as refused:
            load_registered("assistant")

        assert str(path) in str(refused.value)

    def test_a_task_the_owner_added_is_read_through_the_registered_graph(
        self, monkeypatch, tmp_path
    ):
        from starter.cli.main import main

        monkeypatch.setenv("TASKS_DB", str(tmp_path / "tasks.sqlite3"))
        assert main(["tasks", "add", "Renew passport"]) == 0
        with openwebui_stub(replies=[tool_call("list_tasks"), "done"]) as stub:
            monkeypatch.setenv("OPENWEBUI_URL", stub.url)
            monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-local")
            monkeypatch.setenv("OPENWEBUI_MODEL", "llama3.1:8b")
            registered, _ = load_registered("assistant")
            messages = registered.invoke({"messages": [HumanMessage("what is open?")]})["messages"]

        listed = {
            "tasks": [{"id": 1, "title": "Renew passport", "assignee": "", "notes": ""}],
            "more": 0,
        }
        assert types(messages) == ["human", "ai", "tool", "ai"]
        assert json.loads(messages[2].content) == listed
        assert len(stub.requests) == 2
        sent = stub.requests[1]["body"]["messages"][-1]
        assert sent["role"] == "tool" and json.loads(sent["content"]) == listed

    def test_its_retry_policy_is_the_domains_a_503_from_open_webui_is_retried(self, monkeypatch):
        # The export itself, as the server loads it: a graph composed there with
        # another predicate would pass a test of `registered_assistant()`. It
        # waits the domain's first delay, about a second -- the export's own.
        with openwebui_stub(failures=[503]) as stub:
            monkeypatch.setenv("OPENWEBUI_URL", stub.url)
            monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-local")
            monkeypatch.setenv("OPENWEBUI_MODEL", "llama3.1:8b")
            registered, _ = load_registered("assistant")
            messages = registered.invoke({"messages": [HumanMessage("hello")]})["messages"]

        assert types(messages) == ["human", "ai"]
        assert [r["path"] for r in stub.requests] == ["/api/chat/completions"] * 2

    def test_counter_example_a_401_from_open_webui_is_raised_not_retried(self, monkeypatch):
        import openai

        with openwebui_stub(failures=[401]) as stub:
            monkeypatch.setenv("OPENWEBUI_URL", stub.url)
            monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-local")
            monkeypatch.setenv("OPENWEBUI_MODEL", "llama3.1:8b")
            registered, _ = load_registered("assistant")
            with pytest.raises(openai.APIStatusError) as raised:
                registered.invoke({"messages": [HumanMessage("hello")]})

        assert raised.value.status_code == 401
        assert [r["path"] for r in stub.requests] == ["/api/chat/completions"]

    def test_the_registered_graph_is_the_factorys_with_its_budget(
        self, registry, build_assistant, fake_llm, tmp_path
    ):
        from starter.infrastructure.agents.tools import list_tasks, search_tasks
        from starter.infrastructure.stores.tasks import TaskStore

        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        tools = [list_tasks.build(store), search_tasks.build(store)]
        built = build_assistant(fake_llm([answer()]), tools, transient=lambda failure: False)

        assert set(registry.assistant.nodes) == set(built.nodes)
        assert any(node.startswith("ModelCallLimitMiddleware") for node in built.nodes)
        assert any(node.startswith("ToolCallLimitMiddleware") for node in built.nodes)
        # The budget needs 51 supersteps: an export with its own lower ceiling
        # would end a runaway loop there first.
        assert registry.assistant.config["recursion_limit"] == built.config["recursion_limit"]

    def test_the_registered_graph_completes_a_run_with_the_network_refused(
        self, no_network, monkeypatch
    ):
        # Built from scratch under the guard: modules earlier tests imported
        # would otherwise come from the cache, their import-time code unguarded.
        for name in [m for m in sys.modules if m.startswith("starter.infrastructure")]:
            monkeypatch.delitem(sys.modules, name)
        registered, _ = load_registered("assistant")

        messages = registered.invoke({"messages": [HumanMessage("hello")]})["messages"]

        assert types(messages) == ["human", "ai"]
        assert messages[-1].tool_calls == []
        assert no_network == []

    def test_a_second_turn_follows_the_first_instead_of_replacing_it(self, registry):
        first = registry.assistant.invoke({"messages": [HumanMessage("hello")]})["messages"]
        second = registry.assistant.invoke({"messages": [*first, HumanMessage("hello again")]})[
            "messages"
        ]

        assert types(second) == ["human", "ai", "human", "ai"]
        assert second[1].id != second[3].id

    def test_counter_example_the_factorys_graph_offers_a_tool_the_registered_one_offers_none(
        self, registry, build_assistant, fake_llm, add_tool
    ):
        built = build_assistant(
            fake_llm([answer()]), [add_tool.tool], transient=lambda failure: False
        )

        assert offered(built) == ["add"]
        assert offered(registry.assistant) == ["list_tasks", "search_tasks"]

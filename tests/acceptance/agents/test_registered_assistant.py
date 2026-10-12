"""The story test of register-first-graph: the graph the local server would load.

Driven through the real entry point -- `langgraph.json`, resolved the way the
server resolves a file path -- with nothing faked but the network, which is
refused outright.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import uuid
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from langgraph.pregel import Pregel

from tests.fakes import answer

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


@pytest.fixture
def no_network(monkeypatch):
    """Refuse every outbound connection, and record each attempt."""
    attempts: list[object] = []

    def refuse(*args, **kwargs):
        attempts.append(args[1:] or kwargs)
        raise ConnectionRefusedError("the network is refused in this test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: refuse(None, *a))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: refuse(None, *a))
    return attempts


def types(messages: list) -> list[str]:
    return [m.type for m in messages]


class TestAssistantIsRegistered:
    """ASSISTANT-REGISTERED: `langgraph.json` SHALL register exactly one graph,
    under the id `assistant`, bound to the `assistant` export of
    `src/starter/infrastructure/agents/registry.py`. That export SHALL be the
    graph the factory compiles -- so it carries the budget -- with the offline
    model and no tools, and it SHALL complete runs with every outbound network
    connection refused."""

    def test_langgraph_json_registers_the_assistant_and_nothing_else(self):
        graphs = json.loads(CONFIG.read_text(encoding="utf-8"))["graphs"]

        assert graphs == {"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}
        loaded, module = load_registered("assistant")
        assert isinstance(loaded, Pregel)
        bound = {name for name, value in vars(module).items() if isinstance(value, Pregel)}
        assert bound == {"assistant"}

    def test_the_registered_graph_is_the_factorys_with_its_budget(
        self, registry, build_assistant, fake_llm
    ):
        built = build_assistant(fake_llm([answer()]), [])

        assert set(registry.assistant.nodes) == set(built.nodes)
        assert any(node.startswith("ModelCallLimitMiddleware") for node in built.nodes)

    def test_the_registered_graph_completes_a_run_with_the_network_refused(
        self, no_network, clean_env
    ):
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
        built = build_assistant(fake_llm([answer()]), [add_tool.tool])

        assert "tools" in built.nodes
        assert "tools" not in registry.assistant.nodes

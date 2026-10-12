"""The story test of register-first-graph: the graph the local server would load.

Driven through the real entry point -- `langgraph.json`, resolved the way the
server resolves a file path -- with nothing faked but the network, which is
refused outright.
"""

from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from tests.conftest import answer

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "langgraph.json"


def load_graph_spec(spec: str, name: str):
    """Load `./path/to/file.py:attr` as a standalone file, as the server does."""
    path, _, attr = spec.rpartition(":")
    module_spec = importlib.util.spec_from_file_location(name, REPO / path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return getattr(module, attr)


@pytest.fixture
def registry():
    """Imported per test, not at collection: this story test stays red across
    every cycle of the change, and must not stop the rest of the suite."""
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


class TestAssistantIsRegistered:
    """ASSISTANT-REGISTERED: `langgraph.json` SHALL register exactly one graph,
    under the id `assistant`, bound to the `assistant` export of
    `src/starter/infrastructure/agents/registry.py`. That export SHALL be a
    compiled graph that completes a run with every outbound network connection
    refused, because until a requirement names a provider its model is offline."""

    def test_langgraph_json_registers_the_assistant_and_nothing_else(self):
        graphs = json.loads(CONFIG.read_text(encoding="utf-8"))["graphs"]

        assert graphs == {"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}
        loaded = load_graph_spec(graphs["assistant"], "registered_assistant_under_test")
        assert isinstance(loaded, CompiledStateGraph)

    def test_the_registered_graph_completes_a_run_with_the_network_refused(
        self, registry, clean_env, no_network
    ):
        result = registry.assistant.invoke({"messages": [HumanMessage("hello")]})

        messages = result["messages"]
        assert [m.type for m in messages] == ["human", "ai"]
        assert messages[-1].tool_calls == []
        assert no_network == []

    def test_counter_example_a_graph_the_factory_compiles_for_a_test_is_not_registered(
        self, registry, build_assistant, fake_llm, add_tool
    ):
        built = build_assistant(fake_llm([answer()]), [add_tool.tool])

        exported = {
            name for name, value in vars(registry).items() if isinstance(value, CompiledStateGraph)
        }
        assert exported == {"assistant"}
        assert built is not registry.assistant

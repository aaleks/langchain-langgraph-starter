"""The langgraph pack's rules a machine can check -- each proved able to fail.

On this package each check skips, visibly and with its reason, until the first
graph exists: a check over a directory that is not there would pass while
checking nothing, and a pass is believed. The fixtures below prove each one
fails when it should, so the day a graph arrives the checks are already true.
"""

from __future__ import annotations

import json
import uuid

import pytest

from .contract import (
    AGENTS_ALLOWED_EXTERNALS,
    AGENTS_SUBPACKAGE,
    REGISTRY,
    REPO,
    agents_dir,
    build_package,
    imports_outside,
    langgraph_validate,
    models_built_inline,
    registration_problems,
    root_package,
    uncompiled_registrations,
)

SOURCE = REPO / "src" / root_package()
CONFIG = REPO / "langgraph.json"


def test_langgraph_json_registers_only_what_the_registry_exports():
    if not CONFIG.is_file():
        pytest.skip("no langgraph.json yet -- the foundation slice registers the first graph")
    assert registration_problems(CONFIG, SOURCE, root_package()) == []


def test_every_registered_graph_is_a_compiled_graph():
    if not CONFIG.is_file():
        pytest.skip("no langgraph.json yet -- the foundation slice registers the first graph")
    assert uncompiled_registrations(CONFIG) == []


def test_langgraph_validate_accepts_the_config():
    if not CONFIG.is_file():
        pytest.skip("no langgraph.json yet -- the foundation slice registers the first graph")
    result = langgraph_validate(CONFIG)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_agents_adapter_builds_no_client_of_its_own():
    if not agents_dir(SOURCE).is_dir():
        pytest.skip("no infrastructure/agents/ yet -- the first graph creates it")
    offenders = imports_outside(root_package(), AGENTS_SUBPACKAGE, AGENTS_ALLOWED_EXTERNALS)
    assert not offenders, "the agents adapter imports beyond its allowlist:\n" + "\n".join(
        f"  {module} imports {imported}" for module, imported in offenders
    )


def test_no_model_is_built_inline_in_the_agents_adapter():
    if not agents_dir(SOURCE).is_dir():
        pytest.skip("no infrastructure/agents/ yet -- the first graph creates it")
    assert models_built_inline(SOURCE) == []


# -- the same rules, on fixtures built to break them ---------------------------


def registry_project(tmp_path, registry: str, config: dict):
    agents = tmp_path / "src" / "pkg" / "infrastructure" / "agents"
    agents.mkdir(parents=True)
    (agents / "registry.py").write_text(registry, encoding="utf-8")
    (tmp_path / "langgraph.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path / "langgraph.json", tmp_path / "src" / "pkg"


def test_each_way_of_registering_a_graph_wrongly_is_caught(tmp_path):
    here = f"./src/pkg/{REGISTRY}"
    config, source = registry_project(
        tmp_path,
        "chat = object()\n",
        {
            "graphs": {
                "bypass": "./src/pkg/infrastructure/agents/graphs/chat.py:graph",
                "missing": f"{here}:nope",
                "Chat Bot": f"{here}:chat",
            },
            "env": ".env",
        },
    )
    problems = registration_problems(config, source, "pkg")
    assert len(problems) == 4, problems
    assert problems[0].startswith('"env"')
    assert "'bypass'" in problems[1] and "is not in" in problems[1]
    assert "'missing'" in problems[2] and "binds no 'nope'" in problems[2]
    assert "'Chat Bot'" in problems[3] and "lowercase" in problems[3]


def test_counter_example_every_form_of_a_registry_export_is_accepted(tmp_path):
    here = f"./src/pkg/{REGISTRY}"
    config, source = registry_project(
        tmp_path,
        "from .chat.graph import graph as chat\n"
        "research = object()\n"
        "def planner(config):\n    return config\n"
        "reviewer: object = None\n",
        {
            "graphs": {
                "chat": f"{here}:chat",
                "research": {"path": f"{here}:research", "description": "cited answers"},
                "planner": "pkg.infrastructure.agents.registry:planner",
                "reviewer-v2": f"{here}:reviewer",
            }
        },
    )
    assert registration_problems(config, source, "pkg") == []


COMPILED_GRAPH = (
    "from langgraph.graph import END, START, MessagesState, StateGraph\n"
    "builder = StateGraph(MessagesState)\n"
    "builder.add_node('noop', lambda state: {})\n"
    "builder.add_edge(START, 'noop')\n"
    "builder.add_edge('noop', END)\n"
    "ok = builder.compile()\n"
)


def test_each_registration_that_is_not_a_compiled_graph_is_caught(tmp_path):
    here = f"./src/pkg/{REGISTRY}"
    config, _ = registry_project(
        tmp_path,
        COMPILED_GRAPH + "raw = builder\ndef factory(config):\n    return ok\nother = None\n",
        {
            "graphs": {
                "ok": f"{here}:ok",
                "raw": f"{here}:raw",
                "factory": {"path": f"{here}:factory"},
                "other": f"{here}:other",
            }
        },
    )
    problems = uncompiled_registrations(config)
    assert len(problems) == 3, problems
    assert "'raw'" in problems[0] and "StateGraph" in problems[0]
    assert "'factory'" in problems[1] and "function" in problems[1]
    assert "'other'" in problems[2] and "NoneType" in problems[2]


def test_langgraph_validate_refuses_a_config_with_no_graphs(tmp_path):
    config = tmp_path / "langgraph.json"
    config.write_text(json.dumps({"dependencies": ["."], "graphs": {}}), encoding="utf-8")
    result = langgraph_validate(config)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "No graphs found" in result.stdout + result.stderr


@pytest.fixture
def fixture_package(tmp_path, monkeypatch):
    def build(files: dict[str, str]) -> str:
        name = f"graphs_{uuid.uuid4().hex[:8]}"
        build_package(tmp_path, name, files)
        monkeypatch.syspath_prepend(str(tmp_path))
        return name

    return build


def test_a_provider_sdk_or_client_in_the_agents_adapter_is_refused(fixture_package):
    name = fixture_package(
        {
            "infrastructure/agents/graph.py": (
                "import langgraph\nimport langchain\nimport langchain_core\n"
                "import langchain_openai\nimport httpx\n"
            ),
            "infrastructure/models.py": "import langchain_openai\n",
        }
    )
    found = {
        imported
        for _, imported in imports_outside(name, AGENTS_SUBPACKAGE, AGENTS_ALLOWED_EXTERNALS)
    }
    assert found == {"langchain_openai", "httpx"}


def test_every_way_of_building_a_model_inline_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "inlinefix",
        {
            "infrastructure/agents/a.py": (
                "from langchain.chat_models import init_chat_model\n"
                "model = init_chat_model('openai:gpt-5')\n"
            ),
            "infrastructure/agents/b.py": (
                "from langchain.agents import create_agent\n"
                "agent = create_agent('anthropic:claude-x', tools=[])\n"
            ),
            "infrastructure/agents/c.py": (
                "import deepagents\nagent = deepagents.create_deep_agent(model='openai:gpt-5')\n"
            ),
            "infrastructure/models.py": (
                "from langchain.chat_models import init_chat_model\n"
                "def build():\n    return init_chat_model('ollama:qwen3')\n"
            ),
        },
    )
    assert sorted(f.split(":")[0] for f in models_built_inline(source)) == ["a.py", "b.py", "c.py"]


def test_counter_example_a_model_passed_in_is_not_built_inline(tmp_path):
    source = build_package(
        tmp_path,
        "injectfix",
        {
            "infrastructure/agents/graph.py": (
                "from langchain.agents import create_agent\n"
                "NOTE = 'init_chat_model is never called here'\n"
                "def build(model, tools):\n"
                "    return create_agent(model=model, tools=tools)\n"
            )
        },
    )
    assert models_built_inline(source) == []


def test_counter_example_a_compiled_graph_is_accepted_by_file_or_by_module(
    tmp_path, fixture_package
):
    name = fixture_package({"infrastructure/agents/registry.py": COMPILED_GRAPH})
    config = tmp_path / "langgraph.json"
    config.write_text(
        json.dumps(
            {
                "graphs": {
                    "by-file": f"./{name}/infrastructure/agents/registry.py:ok",
                    "by_module": f"{name}.infrastructure.agents.registry:ok",
                }
            }
        ),
        encoding="utf-8",
    )
    assert uncompiled_registrations(config) == []

"""The langgraph pack's rules a machine can check -- each proved able to fail.

On this package each check skips, visibly and with its reason, until the first
graph exists: a check over a directory that is not there would pass while
checking nothing, and a pass is believed. The fixtures below prove each one
fails when it should, so the day a graph arrives the checks are already true.
"""

from __future__ import annotations

import json
import subprocess
import uuid

import pytest

from . import contract
from .contract import (
    AGENTS_ALLOWED_EXTERNALS,
    AGENTS_SUBPACKAGE,
    REGISTRY,
    REPO,
    agent_runtime_imports_outside_agents,
    agents_dir,
    build_package,
    graphs_compiled_outside_factory,
    imports_outside,
    langgraph_validate,
    models_built_inline,
    models_built_outside_models,
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


def test_graphs_are_compiled_only_by_the_factory():
    if not agents_dir(SOURCE).is_dir():
        pytest.skip("no infrastructure/agents/ yet -- the first graph creates it")
    assert graphs_compiled_outside_factory(SOURCE) == []
    assert agent_runtime_imports_outside_agents(SOURCE) == []


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


def test_each_graph_compiled_outside_the_factory_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "compilefix",
        {
            "infrastructure/agents/factory.py": (
                "from langchain.agents import create_agent\n"
                "def build(model):\n    return create_agent(model=model)\n"
            ),
            # the factory under another name
            "infrastructure/agents/registry.py": (
                "from langchain.agents import create_agent as make\n"
                "assistant = make(model=object(), tools=[])\n"
            ),
            "infrastructure/agents/graphs/chat.py": (
                "from langgraph.graph import StateGraph\n"
                "builder = StateGraph(dict)\n"
                "graph = builder.compile()\n"
            ),
            # a builder that arrived by import: no runtime imported here
            "infrastructure/agents/graphs/review.py": (
                "from .chat import builder\nreview = builder.compile()\n"
            ),
            # counter-examples: a regex, beside a runtime and outside the adapter
            "infrastructure/agents/tools.py": (
                "import re\nfrom langgraph.types import Command\nPATTERN = re.compile('x')\n"
            ),
            "cli/main.py": "import re\npattern = re.compile('x')\n",
        },
    )
    found = graphs_compiled_outside_factory(source)
    assert [f.split(":")[0] for f in found] == [
        "infrastructure/agents/graphs/chat.py",
        "infrastructure/agents/graphs/review.py",
        "infrastructure/agents/registry.py",
    ], found


def test_langchain_agents_imported_outside_the_agents_adapter_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "agentsimportfix",
        {
            "infrastructure/agents/factory.py": "from langchain.agents import create_agent\n",
            "infrastructure/models.py": (
                "import langchain.agents\nfrom langchain.chat_models import init_chat_model\n"
            ),
            "cli/main.py": "from langchain.agents.middleware import ModelCallLimitMiddleware\n",
            "cli/other.py": "from langchain import agents\n",
            "config/settings.py": "import langchain_agents_lookalike\n",
        },
    )
    assert agent_runtime_imports_outside_agents(source) == [
        "cli/main.py imports langchain.agents.middleware",
        "cli/other.py imports langchain.agents",
        "infrastructure/models.py imports langchain.agents",
    ]


def test_langgraph_validate_is_run_with_cli_analytics_off(tmp_path, monkeypatch):
    """The CLI POSTs analytics unless LANGGRAPH_CLI_NO_ANALYTICS is exactly "1"
    -- "true" does not count. A shell may set neither."""
    monkeypatch.delenv("LANGGRAPH_CLI_NO_ANALYTICS", raising=False)
    handed: dict = {}

    def run(args, **kwargs):
        handed.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(contract.subprocess, "run", run)
    contract.langgraph_validate(tmp_path / "langgraph.json")
    assert handed["env"]["LANGGRAPH_CLI_NO_ANALYTICS"] == "1"


def test_models_are_built_only_in_infrastructure_models():
    assert models_built_outside_models(SOURCE) == []


def test_each_model_built_outside_infrastructure_models_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "modelsfix",
        {
            "infrastructure/models.py": (
                "from langchain_openai import ChatOpenAI\n"
                "def build():\n    return ChatOpenAI(model='m')\n"
            ),
            "infrastructure/agents/registry.py": (
                "from langchain_core.language_models import fake_chat_models as f\n"
                "model = f.GenericFakeChatModel(messages=iter([]))\n"
            ),
            "cli/main.py": (
                "from langchain.chat_models import init_chat_model\n"
                "model = init_chat_model('ollama:qwen3')\n"
            ),
            "config/settings.py": "from langchain_ollama import ChatOllama\nm = ChatOllama()\n",
            # the same class under another name, and a name the pattern misses
            "infrastructure/agents/alias.py": (
                "from langchain_openai import ChatOpenAI as Model\nm = Model(model='m')\n"
            ),
            "infrastructure/agents/azure.py": (
                "import langchain_openai\nm = langchain_openai.AzureChatOpenAI()\n"
            ),
            "infrastructure/agents/make.py": (
                "from langchain.chat_models import init_chat_model as make\n"
                "m = make('ollama:qwen3')\n"
            ),
            # a provider's own SDK: every client it makes is a model client,
            # imported from it or called through it -- names the class pattern
            # does not match, so only the SDK rule can catch them
            "infrastructure/agents/sdk.py": "from ollama import Client as C\nc = C()\n",
            "infrastructure/tracing/client.py": "import anthropic\nc = anthropic.Anthropic()\n",
            # a completion model and embeddings are models too
            "infrastructure/stores/llm.py": "from langchain_ollama import OllamaLLM\nm = OllamaLLM()\n",
            "cli/embed.py": "import langchain_openai as lo\ne = lo.OpenAIEmbeddings()\n",
            # the builder reached through its module
            "cli/chat.py": ("import langchain.chat_models as cm\nm = cm.init_chat_model('x')\n"),
            # counter-examples: names that merely look alike, langchain_core's
            # chat data, and a partner package's class that is not a model
            "application/chat.py": "def chat_turn():\n    return Chatter()\nclass Chatter: ...\n",
            "application/prompts.py": (
                "from langchain_core.prompts import ChatPromptTemplate as T\n"
                "from langchain_core.messages import ChatMessage\n"
                "P = T([('system', 'x')])\nM = ChatMessage(role='system', content='x')\n"
            ),
            "infrastructure/stores/tasks.py": "from langchain_chroma import Chroma\ns = Chroma()\n",
            # more of langchain_core's chat data, an error named like a model,
            # and an SDK's errors and functions: none of them builds a model
            "application/outputs.py": (
                "r = ChatResult(generations=[])\ng = ChatGenerationChunk()\n"
                "s = ChatSession()\nl = BaseChatLoader()\nm = ChatModelStream()\n"
                "e = SomeChatError()\n"
            ),
            "infrastructure/stores/failures.py": (
                "import openai\nfrom openai import APIStatusError\n"
                "e = APIStatusError('x')\nt = openai.APITimeoutError(request=None)\n"
                "u = openai.base_url_for('x')\n"
            ),
        },
    )
    found = models_built_outside_models(source)
    assert [f.split(":")[0] for f in found] == [
        "cli/chat.py",
        "cli/embed.py",
        "cli/main.py",
        "config/settings.py",
        "infrastructure/agents/alias.py",
        "infrastructure/agents/azure.py",
        "infrastructure/agents/make.py",
        "infrastructure/agents/registry.py",
        "infrastructure/agents/sdk.py",
        "infrastructure/stores/llm.py",
        "infrastructure/tracing/client.py",
    ], found

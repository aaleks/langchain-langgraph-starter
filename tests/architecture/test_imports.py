"""What each layer may import from outside the package -- allowlists, proved able to fail."""

from __future__ import annotations

import uuid

import pytest

from .contract import (
    ALLOWED_EXTERNALS,
    build_package,
    imports_outside,
    root_package,
    runtimes_outside_agents,
)


@pytest.mark.parametrize("layer", sorted(ALLOWED_EXTERNALS))
def test_each_layer_imports_only_what_it_is_allowed(layer):
    offenders = imports_outside(root_package(), layer, ALLOWED_EXTERNALS[layer])
    assert not offenders, f"{layer}/ imports beyond its allowlist:\n" + "\n".join(
        f"  {module} imports {imported}" for module, imported in offenders
    )


def test_langgraph_and_deepagents_live_only_in_the_agents_adapter():
    offenders = runtimes_outside_agents(root_package())
    assert not offenders, "a runtime escaped infrastructure/agents/:\n" + "\n".join(
        f"  {module} imports {imported}" for module, imported in offenders
    )


@pytest.fixture
def fixture_package(tmp_path, monkeypatch):
    def build(files: dict[str, str]) -> str:
        name = f"imports_{uuid.uuid4().hex[:8]}"
        build_package(tmp_path, name, files)
        monkeypatch.syspath_prepend(str(tmp_path))
        return name

    return build


def test_the_domain_allowlist_refuses_any_third_party_package(fixture_package):
    name = fixture_package({"domain/routing.py": "import json\nimport pydantic\nimport httpx\n"})
    found = {
        imported for _, imported in imports_outside(name, "domain", ALLOWED_EXTERNALS["domain"])
    }
    assert found == {"pydantic", "httpx"}


def test_the_application_allowlist_refuses_a_runtime_but_not_its_abstractions(fixture_package):
    name = fixture_package(
        {
            "application/answer.py": "import langchain_core\nimport pydantic\nimport langchain\nimport langgraph\n"
        }
    )
    found = {
        imported
        for _, imported in imports_outside(name, "application", ALLOWED_EXTERNALS["application"])
    }
    assert found == {"langchain", "langgraph"}


def test_the_config_allowlist_refuses_anything_but_the_dotenv_reader(fixture_package):
    name = fixture_package(
        {"config/settings.py": "import os\nimport dotenv\nimport httpx\nimport langchain_openai\n"}
    )
    found = {
        imported for _, imported in imports_outside(name, "config", ALLOWED_EXTERNALS["config"])
    }
    assert found == {"httpx", "langchain_openai"}


def test_a_runtime_outside_the_agents_adapter_is_refused(fixture_package):
    name = fixture_package(
        {
            "infrastructure/agents/graph.py": "import langgraph\n",
            "infrastructure/models.py": "import langgraph\n",
            "cli/main.py": "import deepagents\n",
        }
    )
    offenders = {module.split(".", 1)[1] for module, _ in runtimes_outside_agents(name)}
    assert offenders == {"infrastructure.models", "cli.main"}


def test_counter_example_an_empty_layer_is_refused_not_passed(fixture_package):
    """An allowlist over a layer that does not exist would pass while checking nothing."""
    name = fixture_package({"domain/x.py": "import json\n"})
    with pytest.raises(AssertionError, match="vacuously"):
        imports_outside(name, "application", ALLOWED_EXTERNALS["application"])

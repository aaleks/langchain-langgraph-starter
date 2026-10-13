"""Shared fixtures, and the environment every test runs in.

Deliberately small. Domain functions take the environment as an explicit
argument, so most tests need no fixture at all -- hiding that behind one would
obscure the point of the layering.

No test may call a real model (.claude/rules/sdd/tests.md): `fake_llm` scripts
one, and `add_tool` records what a tool loop asked of its only tool. Both live
in tests/fakes.py, imported only by the tests that use them.
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import pytest

# The suite is local-only, whatever the shell that starts it exports
# (docs/decisions/0004). langsmith reads these on first use and caches them, so
# they are set here, before any test module imports langchain_core; the
# langsmith pytest plugin, which loads before this file, is off in addopts.
# Held equal to .claude/settings.json's env by tests/architecture/test_local_only.py.
# Without it, a shell with LANGSMITH_TRACING=true uploads every graph run --
# measured in register-first-graph (verify.md, finding 1).
LOCAL_ONLY = {
    "LANGSMITH_TRACING": "false",
    "LANGSMITH_TRACING_V2": "false",
    "LANGCHAIN_TRACING_V2": "false",
    "LANGCHAIN_TRACING": "false",
    "LANGSMITH_API_KEY": "",
    "LANGCHAIN_API_KEY": "",
    "LANGSMITH_CONTROL_PLANE_API_KEY": "",
    "LANGGRAPH_CLOUD_LICENSE_KEY": "",
    "LANGSMITH_ENDPOINT": "http://127.0.0.1:9",
    "LANGCHAIN_ENDPOINT": "http://127.0.0.1:9",
    "LANGGRAPH_CLI_NO_ANALYTICS": "1",
    "LANGGRAPH_NO_VERSION_CHECK": "true",
}
os.environ.update(LOCAL_ONLY)

# The owner's .env may configure a real model. The environment wins over .env
# (SETTINGS-ENVIRONMENT-WINS), so these empty values keep every default test --
# and the live server tests, which inherit them -- on the offline model.
MODEL_UNSET = {"OPENWEBUI_URL": "", "OPENWEBUI_API_KEY": "", "OPENWEBUI_MODEL": ""}
os.environ.update(MODEL_UNSET)

# The model client reads more of the environment than it is given: a proxy, an
# organisation, extra headers. None of the owner's reaches a default test, and
# nothing bound for 127.0.0.1 -- the Open WebUI stub -- is sent to a proxy.
for _name in [
    n
    for n in os.environ
    if n.upper().startswith("OPENAI_") or n.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
]:
    del os.environ[_name]
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

# `NAME=value` or `# NAME=value`: a documented variable, set or not.
_DOCUMENTED = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)


def documented_variables() -> list[str]:
    """Every variable .env.example documents -- the single list of what is read."""
    return sorted(set(_DOCUMENTED.findall(ENV_EXAMPLE.read_text(encoding="utf-8"))))


def pytest_collection_modifyitems(config, items):
    """Skip `live` tests unless the command line explicitly asked for them.

    addopts carries -m 'not live', but a command-line -m REPLACES that
    expression rather than ANDing with it. So `pytest -m "not slow"` silently
    re-selects every live test and makes real calls -- measured in the project
    this method came from, three of them. This closes that hole without
    breaking the documented `pytest -m live`.
    """
    markexpr = config.getoption("markexpr", "") or ""
    asked_for_live = bool(re.search(r"(^|[\s(])live\b", markexpr)) and not re.search(
        r"\bnot\s+live\b", markexpr
    )
    if asked_for_live:
        return
    skip = pytest.mark.skip(reason="live test: run it with -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def clean_env(monkeypatch):
    """A process environment with every documented variable set empty.

    Without this, whatever is in the developer's real .env leaks into a test,
    and it passes or fails depending on whose machine runs it. Empty, not
    removed: the environment wins over .env (SETTINGS-ENVIRONMENT-WINS), so a
    removed variable would be filled from the developer's .env again.
    """
    for name in documented_variables():
        monkeypatch.setenv(name, "")
    return monkeypatch


# -- models and tools ----------------------------------------------------------


@pytest.fixture
def fake_llm():
    """Build a scripted model: `fake_llm([propose(...), answer()])`."""
    from tests.fakes import scripted_model

    return scripted_model


@pytest.fixture
def add_tool():
    """A fake `add(a, b)` tool that records each call's arguments."""
    from tests.fakes import recording_add

    return recording_add()


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

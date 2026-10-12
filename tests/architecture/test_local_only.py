"""The default suite runs local-only, whatever the shell that starts it exports.

A person's shell or CI does not carry .claude/settings.json's env, so before
register-first-graph's fix a shell with LANGSMITH_TRACING=true uploaded every
graph run the suite made (docs/decisions/0004; verify.md, finding 1).
"""

from __future__ import annotations

import json
import os

from tests.conftest import LOCAL_ONLY

from .contract import REPO, local_only_drift

SETTINGS = REPO / ".claude" / "settings.json"


def test_the_suite_sets_the_same_local_only_environment_as_the_settings():
    settings_env = json.loads(SETTINGS.read_text(encoding="utf-8"))["env"]
    assert local_only_drift(LOCAL_ONLY, settings_env) == []


def test_the_suite_runs_with_that_environment_and_tracing_off(pytestconfig):
    from langsmith.utils import tracing_is_enabled

    assert {name: os.environ.get(name) for name in LOCAL_ONLY} == LOCAL_ONLY
    assert not tracing_is_enabled()
    assert not pytestconfig.pluginmanager.has_plugin("langsmith_plugin")


def test_drift_between_the_suite_and_the_settings_is_caught():
    problems = local_only_drift(
        {"LANGSMITH_TRACING": "true", "LANGGRAPH_EXTRA": "1"},
        {"LANGSMITH_TRACING": "false", "LANGSMITH_ENDPOINT": "http://127.0.0.1:9", "OTHER": "x"},
    )
    assert problems == [
        "LANGSMITH_ENDPOINT: the suite sets None, the settings 'http://127.0.0.1:9'",
        "LANGSMITH_TRACING: the suite sets 'true', the settings 'false'",
        "LANGGRAPH_EXTRA: set by the suite, not by the settings",
    ]

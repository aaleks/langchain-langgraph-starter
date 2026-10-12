"""The default suite runs local-only, whatever the shell that starts it exports.

A person's shell or CI does not carry .claude/settings.json's env, so before
register-first-graph's fix a shell with LANGSMITH_TRACING=true uploaded every
graph run the suite made (docs/decisions/0004; verify.md, finding 1).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from tests.conftest import LOCAL_ONLY

from .contract import REPO, local_only_drift, shell_exports

SETTINGS = REPO / ".claude" / "settings.json"
SERVE = REPO / "scripts" / "serve.sh"

# What a person's shell might export -- the environment the seal must beat.
HOSTILE = {
    "LANGSMITH_TRACING": "true",
    "LANGSMITH_TRACING_V2": "true",
    "LANGCHAIN_TRACING_V2": "true",
    "LANGSMITH_API_KEY": "lsv2_pt_not_a_real_key",
}
# Imports conftest the way pytest does -- before any test module -- then asks
# langsmith what it would do. Exits 1 if it would trace.
PROBE = (
    "import tests.conftest\n"
    "from langsmith.utils import tracing_is_enabled\n"
    "raise SystemExit(1 if tracing_is_enabled() else 0)\n"
)


def test_the_suite_sets_the_same_local_only_environment_as_the_settings():
    settings_env = json.loads(SETTINGS.read_text(encoding="utf-8"))["env"]
    assert local_only_drift(LOCAL_ONLY, settings_env) == []


def test_serve_sh_exports_the_same_local_only_environment():
    """This project's own scripts/serve.sh -- the method's tests check the seed it
    came from, not the copy the project owns. The live tests catch a serve.sh
    that stops overriding LangSmith; this catches, without starting anything,
    the two switches whose regression would reach a real third party (the CLI's
    analytics, the version check), and credentials an asyncio client would use
    unseen on Windows (serve-first-graph-locally, verify.md 14 and 16)."""
    assert local_only_drift(shell_exports(SERVE.read_text(encoding="utf-8")), LOCAL_ONLY) == []


def test_a_serve_sh_that_drops_an_export_is_caught():
    script = (
        "export LANGSMITH_TRACING=false\n"
        "export LANGSMITH_API_KEY='' LANGGRAPH_CLI_NO_ANALYTICS=true\n"
        "exec uv run langgraph-cli-stand-in\n"
    )
    problems = local_only_drift(shell_exports(script), LOCAL_ONLY)

    assert "LANGGRAPH_CLI_NO_ANALYTICS: the suite sets 'true', the settings '1'" in problems
    assert "LANGGRAPH_NO_VERSION_CHECK: the suite sets None, the settings 'true'" in problems
    assert not any(p.startswith(("LANGSMITH_TRACING:", "LANGSMITH_API_KEY:")) for p in problems)


def test_the_seal_holds_in_a_shell_that_switches_tracing_on():
    """In a fresh process, from a hostile environment: an agent session already
    carries every local-only variable, so an in-process check could not fail
    there (verify.md, finding 25)."""
    control = subprocess.run(
        [sys.executable, "-c", PROBE.replace("import tests.conftest\n", "")],
        cwd=REPO,
        env={**os.environ, **HOSTILE},
        timeout=120,
    )
    sealed = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=REPO, env={**os.environ, **HOSTILE}, timeout=120
    )

    assert control.returncode == 1, "the hostile environment did not switch tracing on"
    assert sealed.returncode == 0, "tests/conftest.py did not switch tracing off"


def test_the_langsmith_pytest_plugin_is_not_loaded(pytestconfig):
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

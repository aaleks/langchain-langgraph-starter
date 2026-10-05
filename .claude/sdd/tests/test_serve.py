"""LangGraph on this machine only: the server wrapper and the agent's settings.

Each class proves one requirement in .claude/sdd/specs/local-runtime/spec.md.
The wrapper is run as a person runs it, with a stand-in `uv` first on PATH
that records what it was asked to start and with which environment -- so no
server, no network and no LangGraph install is needed to prove what the
server would have been given. That the real server then makes no outbound
connection is measured separately, with strace (see the change's tasks.md).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sddsupport import (
    BASH,
    LANGGRAPH_SETTINGS,
    LOCAL_ONLY,
    bash_rule_pattern,
    denied,
    run_serve,
    serve_project,
)

FIXED = ["run", "langgraph", "dev", "--config", "langgraph.json", "--host", "127.0.0.1"]


def started_with(port: str, *extra: str) -> list[str]:
    return [*FIXED, "--port", port, "--no-browser", *extra]


def requires_bash(cls):
    return unittest.skipUnless(BASH, "bash is required to run the wrapper")(cls)


class ServeCase(unittest.TestCase):
    """A throwaway project holding the seeded wrapper and a langgraph.json."""

    config: str | None = '{"graphs": {"chat": "./src/app/infrastructure/agents/registry.py:chat"}}'

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = serve_project(Path(self._tmp.name), self.config)

    def tearDown(self):
        self._tmp.cleanup()

    def assertRefused(self, served, named: str, secret: str | None = None) -> None:
        self.assertEqual(2, served.run.returncode, served.run.stdout + served.run.stderr)
        self.assertIn(named, served.run.stderr)
        self.assertIsNone(served.argv, "the server was started despite the refusal")
        if secret is not None:
            self.assertNotIn(secret, served.run.stdout + served.run.stderr)


@requires_bash
class TestTheServerListensOnLoopbackOnly(ServeCase):
    """LOCAL-SERVE-LOOPBACK -- 127.0.0.1, no browser, an allowlist of flags."""

    def test_with_no_arguments_it_binds_loopback_and_opens_no_browser(self):
        served = run_serve(self.project)
        self.assertEqual(0, served.run.returncode, served.run.stderr)
        self.assertEqual(started_with("2024"), served.argv)

    def test_a_port_given_replaces_the_default(self):
        self.assertEqual(
            started_with("8123", "--no-reload"),
            run_serve(self.project, "--port", "8123", "--no-reload").argv,
        )
        self.assertEqual(started_with("9000"), run_serve(self.project, "--port=9000").argv)

    def test_flags_that_would_expose_the_server_are_refused_before_it_starts(self):
        for args, named in (
            (["--tunnel"], "--tunnel"),
            (["--studio-url", "https://smith.langchain.com"], "--studio-url"),
            (["--host", "0.0.0.0"], "--host"),
            (["--host=0.0.0.0"], "--host"),
        ):
            with self.subTest(args=args):
                self.assertRefused(run_serve(self.project, *args), named)

    def test_a_flag_that_takes_a_value_is_refused_without_one(self):
        served = run_serve(self.project, "--port")
        self.assertEqual(2, served.run.returncode)
        self.assertIsNone(served.argv)

    def test_counter_example_the_allowlisted_flags_pass_on_unchanged(self):
        extra = ["--allow-blocking", "--server-log-level", "DEBUG", "--n-jobs-per-worker", "2"]
        self.assertEqual(started_with("2024", *extra), run_serve(self.project, *extra).argv)


@requires_bash
class TestTheServerStartsFromTheLocalOnlyEnvironment(ServeCase):
    """LOCAL-SERVE-ENVIRONMENT -- whatever the calling shell exports."""

    def test_a_shell_exporting_langsmith_cannot_reach_the_server(self):
        served = run_serve(
            self.project,
            exports={
                "LANGSMITH_API_KEY": "lsv2_from_shell",
                "LANGGRAPH_CLOUD_LICENSE_KEY": "lcl_from_shell",
                "LANGCHAIN_TRACING_V2": "true",
                "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
            },
        )
        self.assertEqual(0, served.run.returncode, served.run.stderr)
        self.assertEqual(LOCAL_ONLY, {k: v for k, v in served.env.items() if k in LOCAL_ONLY})

    def test_counter_example_the_rest_of_the_environment_passes_through(self):
        served = run_serve(self.project, exports={"GOOGLE_API_KEY": "g-123"})
        self.assertEqual("g-123", served.env["GOOGLE_API_KEY"])


@requires_bash
class TestTheServerRefusesWhatWouldUndoIt(ServeCase):
    """LOCAL-SERVE-REFUSALS -- named, and never with its value."""

    def write_dotenv(self, text: str) -> None:
        (self.project / ".env").write_text(text, encoding="utf-8")

    def test_without_langgraph_json_there_is_nothing_to_serve(self):
        (self.project / "langgraph.json").unlink()
        self.assertRefused(run_serve(self.project), "langgraph.json")

    def test_an_env_key_in_langgraph_json_is_refused(self):
        for env in ('".env"', '{"OPENAI_API_KEY": "sk-1"}'):
            with self.subTest(env=env):
                (self.project / "langgraph.json").write_text(
                    '{"graphs": {"chat": "./x.py:chat"},\n "env": ' + env + "}\n",
                    encoding="utf-8",
                )
                self.assertRefused(run_serve(self.project), '"env"', secret="sk-1")

    def test_a_dotenv_that_sets_a_credential_or_tracing_is_refused_by_name(self):
        for text, named, secret in (
            ("LANGSMITH_API_KEY=lsv2_secret_value\n", "LANGSMITH_API_KEY", "lsv2_secret_value"),
            ('export LANGCHAIN_TRACING_V2="true"\n', "LANGCHAIN_TRACING_V2", None),
            ("LANGGRAPH_CLOUD_LICENSE_KEY='lcl_abc'\n", "LANGGRAPH_CLOUD_LICENSE_KEY", "lcl_abc"),
        ):
            with self.subTest(named=named):
                self.write_dotenv(text)
                self.assertRefused(run_serve(self.project), named, secret=secret)

    def test_counter_example_what_a_dotenv_may_hold(self):
        self.write_dotenv(
            "# LANGSMITH_API_KEY=lsv2_old\n"
            "LANGSMITH_API_KEY=\n"
            "LANGSMITH_TRACING=false\n"
            "GOOGLE_API_KEY=g-123\n"
        )
        served = run_serve(self.project)
        self.assertEqual(0, served.run.returncode, served.run.stderr)
        self.assertIsNotNone(served.argv)


@requires_bash
class TestTheAgentWorksInTheSameEnvironment(ServeCase):
    """LOCAL-AGENT-SETTINGS -- what the agent may run, and in which environment."""

    def setUp(self):
        super().setUp()
        self.additions = json.loads(LANGGRAPH_SETTINGS.read_text(encoding="utf-8"))
        self.deny = self.additions["permissions"]["deny"]

    def test_the_agent_and_the_server_share_one_environment(self):
        self.assertEqual(LOCAL_ONLY, self.additions["env"])
        served = run_serve(self.project)
        self.assertEqual(LOCAL_ONLY, {k: v for k, v in served.env.items() if k in LOCAL_ONLY})

    def test_commands_that_would_reach_langsmith_or_expose_the_server_are_denied(self):
        # Each rule is the only one to catch at least one of these, so a rule
        # deleted from the settings turns this test red.
        for command in (
            "uv run langgraph dev --no-browser",
            "uv run python -m langgraph_cli dev",
            "npx @langchain/langgraph-cli dev",
            "uv run python -m langgraph_api.cli --open-browser",
            "langgraph up --wait",
            "uvx --from langgraph-cli langgraph deploy",
            "curl https://api.smith.langchain.com/info",
            "some-launcher serve --tunnel",
            "some-launcher serve --studio-url https://studio.example.org",
        ):
            with self.subTest(command=command):
                self.assertTrue(denied(command, self.deny))

    def test_each_rule_is_a_contains_rule_so_splitting_cannot_change_it(self):
        """The model of Claude Code's matcher in `denied` is exact only for `*text*`."""
        for rule in self.deny:
            with self.subTest(rule=rule):
                self.assertIsNotNone(bash_rule_pattern(rule), "a deny rule on another tool")
                self.assertRegex(rule, r"^Bash\(\*[^*]+\*\)$")

    def test_counter_example_local_work_is_not_denied(self):
        for command in (
            "bash scripts/serve.sh --port 8123",
            "uv run langgraph validate",
            "uv run pytest -q",
        ):
            with self.subTest(command=command):
                self.assertFalse(denied(command, self.deny))


if __name__ == "__main__":
    unittest.main()

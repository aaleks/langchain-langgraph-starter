"""The hooks, driven exactly as Claude Code drives them: JSON on stdin.

Each class proves one requirement in .claude/sdd/specs/edit-guards/spec.md or
.claude/sdd/specs/session-hooks/spec.md. A guard nobody watched refuse is a
guard nobody has.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from sddsupport import SDD

HOOKS = SDD.parent / "hooks"
BASH = shutil.which("bash")
GIT = shutil.which("git")


def requires_bash(cls):
    return unittest.skipUnless(BASH, "bash is required to run the hooks")(cls)


class GuardCase(unittest.TestCase):
    """A throwaway project root, and the guard run against it."""

    sdd_toml = ""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        if self.sdd_toml:
            (self.root / "sdd.toml").write_text(textwrap.dedent(self.sdd_toml), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def guard(self, tool_input: dict, root: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [BASH, str(HOOKS / "guard-edits.sh")],
            input=json.dumps({"tool_name": "Write", "tool_input": tool_input}),
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": root or str(self.root)},
            check=False,
        )

    def write(self, rel: str, content: str = "x") -> subprocess.CompletedProcess:
        return self.guard({"file_path": str(self.root / rel), "content": content})

    def assertRefused(self, run: subprocess.CompletedProcess, reason: str) -> None:
        self.assertEqual(2, run.returncode, run.stdout + run.stderr)
        self.assertIn(reason, run.stderr)

    def assertAllowed(self, run: subprocess.CompletedProcess) -> None:
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual("", run.stdout.strip())

    def decision(self, run: subprocess.CompletedProcess) -> dict:
        self.assertEqual(0, run.returncode, run.stderr)
        return json.loads(run.stdout)["hookSpecificOutput"]


@requires_bash
class TestSecretsAreWrittenByAHumanOnly(GuardCase):
    """GUARD-SECRETS"""

    def test_env_files_and_keys_are_refused(self):
        for rel in (".env", ".env.local", "deploy/.env.production", "certs/server.pem"):
            with self.subTest(rel=rel):
                self.assertRefused(self.write(rel), "credentials")

    def test_counter_example_the_committed_example_file_is_editable(self):
        self.assertAllowed(self.write(".env.example", "API_KEY=\n"))


@requires_bash
class TestGroundTruthIsWrittenByAHumanOnly(GuardCase):
    """GUARD-GROUND-TRUTH"""

    def test_the_default_golden_directory_is_refused(self):
        self.assertRefused(self.write("tests/evals/golden/answers.jsonl"), "ground truth")

    def test_counter_example_a_file_beside_it_is_not(self):
        self.assertAllowed(self.write("tests/evals/test_answers.py"))


@requires_bash
class TestGroundTruthGlobsComeFromTheAdapter(GuardCase):
    """GUARD-GROUND-TRUTH -- the project says where its ground truth lives."""

    sdd_toml = """\
        [guards]
        ground_truth = ["data/labelled/*", "evals/expected/*"]
        """

    def test_each_configured_glob_is_refused(self):
        self.assertRefused(self.write("data/labelled/set.jsonl"), "ground truth")
        self.assertRefused(self.write("evals/expected/x.json"), "ground truth")

    def test_counter_example_the_default_no_longer_applies_once_configured(self):
        self.assertAllowed(self.write("tests/evals/golden/answers.jsonl"))


@requires_bash
class TestGeneratedFilesAndCiAreRefused(GuardCase):
    """GUARD-GENERATED-AND-CI"""

    def test_lockfiles_and_workflows_are_refused(self):
        self.assertRefused(self.write("uv.lock"), "generated")
        self.assertRefused(self.write("web/package-lock.json"), "generated")
        self.assertRefused(self.write(".github/workflows/checks.yml"), "CI")

    def test_counter_example_the_manifest_that_generates_a_lockfile_is_editable(self):
        self.assertAllowed(self.write("pyproject.toml", "[project]\n"))
        self.assertAllowed(self.write("docs/ci/ci.yml", "name: checks\n"))


@requires_bash
class TestDomainImportsAreRefusedAtWriteTime(GuardCase):
    """GUARD-DOMAIN-IMPORTS"""

    def test_an_sdk_import_into_the_decision_layer_is_refused(self):
        run = self.write(
            "src/app/domain/routing.py", '"""Doc."""\nfrom langgraph.graph import StateGraph\n'
        )
        self.assertRefused(run, "standard library only")

    def test_counter_example_removing_the_import_is_allowed(self):
        run = self.guard(
            {
                "file_path": str(self.root / "src/app/domain/routing.py"),
                "old_string": "import langchain\n",
                "new_string": "",
            }
        )
        self.assertAllowed(run)

    def test_counter_example_the_standard_library_and_other_layers_are_allowed(self):
        self.assertAllowed(
            self.write("src/app/domain/routing.py", "import re\nfrom enum import Enum\n")
        )
        self.assertAllowed(
            self.write(
                "src/app/infrastructure/agents/g.py", "from langgraph.graph import StateGraph\n"
            )
        )


@requires_bash
class TestRuntimeDataIsWrittenByTheRuntimeOnly(GuardCase):
    """GUARD-RUNTIME-DATA"""

    def test_the_local_servers_state_is_refused(self):
        self.assertRefused(self.write(".langgraph_api/.langgraph_checkpoint.1.pckl"), "runtime")

    def test_data_stores_are_refused_wherever_they_sit(self):
        for rel in ("checkpoints.sqlite", "data/threads.db", "var/store.sqlite3"):
            with self.subTest(rel=rel):
                self.assertRefused(self.write(rel), "store")

    def test_counter_example_names_that_only_resemble_a_store_are_written_freely(self):
        self.assertAllowed(self.write("docs/database.md"))
        self.assertAllowed(self.write("src/app/infrastructure/agents/checkpointers.py"))


@requires_bash
class TestTheServerConfigCarriesNoEnvironment(GuardCase):
    """GUARD-SERVER-CONFIG"""

    def test_an_env_key_written_to_langgraph_json_is_refused(self):
        for rel, content in (
            ("langgraph.json", '{"graphs": {"chat": "./x.py:chat"}, "env": ".env"}'),
            ("deploy/langgraph.json", '{"env": {"OPENAI_API_KEY": "sk-1"}}'),
        ):
            with self.subTest(rel=rel):
                self.assertRefused(self.write(rel, content), "env")

    def test_counter_example_removing_the_key_is_not_refused_for_containing_it(self):
        run = self.guard(
            {
                "file_path": str(self.root / "langgraph.json"),
                "old_string": '"env": ".env",',
                "new_string": "",
            }
        )
        self.assertAllowed(run)

    def test_counter_example_a_config_without_it_and_other_files_are_written_freely(self):
        self.assertAllowed(self.write("langgraph.json", '{"graphs": {"chat": "./x.py:chat"}}'))
        self.assertAllowed(self.write("config/server.json", '{"env": ".env"}'))


@requires_bash
class TestTheLivingSpecAndTheEnforcementAsk(GuardCase):
    """GUARD-ASK"""

    def test_the_living_spec_asks(self):
        decision = self.decision(self.write("openspec/specs/routing/spec.md"))
        self.assertEqual("ask", decision["permissionDecision"])
        self.assertIn("archive writes it", decision["permissionDecisionReason"])

    def test_the_enforcement_asks(self):
        for rel in (
            ".claude/settings.json",
            ".claude/hooks/guard-edits.sh",
            ".claude/sdd/sddlib/check.py",
            "scripts/check.sh",
        ):
            with self.subTest(rel=rel):
                self.assertEqual("ask", self.decision(self.write(rel))["permissionDecision"])

    def test_the_local_only_runtime_asks(self):
        for rel in (
            "scripts/serve.sh",
            ".claude/sdd/seeds/serve.sh",
            ".claude/sdd/seeds/settings.langgraph.json",
        ):
            with self.subTest(rel=rel):
                self.assertEqual("ask", self.decision(self.write(rel))["permissionDecision"])

    def test_counter_example_a_change_delta_a_skill_and_another_script_are_written_freely(self):
        self.assertAllowed(self.write("openspec/changes/add-x/specs/routing/spec.md"))
        self.assertAllowed(self.write(".claude/skills/intake/SKILL.md"))
        self.assertAllowed(self.write("scripts/release.sh"))


@requires_bash
class TestPromptEditsAreNoted(GuardCase):
    """GUARD-PROMPT-NOTE"""

    def test_a_prompt_constant_adds_context_and_still_allows(self):
        decision = self.decision(
            self.write("src/app/application/answer.py", 'SYSTEM_PROMPT = "Answer."\n')
        )
        self.assertNotIn("permissionDecision", decision)
        self.assertIn("/eval", decision["additionalContext"])

    def test_counter_example_a_use_case_without_a_prompt_is_silent(self):
        self.assertAllowed(
            self.write("src/app/application/answer.py", "def answer(model):\n    return model\n")
        )


@requires_bash
class TestPathsAreNormalised(GuardCase):
    """GUARD-PATHS -- the same rule whatever shape the path arrives in."""

    def test_windows_separators_and_drive_case_still_match(self):
        windows_root = "C:\\Users\\dev\\project"
        run = self.guard(
            {"file_path": "c:\\Users\\dev\\project\\.env", "content": "x"}, root=windows_root
        )
        self.assertRefused(run, "credentials")

    def test_a_relative_path_still_matches(self):
        self.assertRefused(self.guard({"file_path": "tests/evals/golden/a.jsonl"}), "ground truth")

    def test_counter_example_a_payload_with_no_path_is_allowed(self):
        self.assertAllowed(self.guard({"content": "x"}))


@requires_bash
@unittest.skipUnless(GIT, "git is required for the Stop hook")
class TestTheStopHookReportsDriftToTheUser(unittest.TestCase):
    """HOOKS-STOP-DRIFT"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(
            SDD, self.root / ".claude" / "sdd", ignore=shutil.ignore_patterns("__pycache__")
        )
        (self.root / "openspec" / "specs").mkdir(parents=True)
        (self.root / "openspec" / "changes").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "sdd.toml").write_text(
            '[specs]\nliving = "openspec/specs"\nchanges = "openspec/changes"\n'
            '[tests]\nroots = ["tests"]\npatterns = ["test_*.py"]\n',
            encoding="utf-8",
        )
        for args in (
            ["init", "-q"],
            ["add", "-A"],
            ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
        ):
            subprocess.run([GIT, *args], cwd=self.root, check=True, capture_output=True)

    def tearDown(self):
        self._tmp.cleanup()

    def stop(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [BASH, str(HOOKS / "check-alignment.sh")],
            input=json.dumps({"hook_event_name": "Stop", "stop_hook_active": False}),
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
            check=False,
        )

    def test_drift_after_a_turn_reaches_the_user_as_a_system_message(self):
        (self.root / "tests" / "test_orphan.py").write_text(
            "def test_x():\n    pass\n", encoding="utf-8"
        )
        run = self.stop()
        self.assertEqual(0, run.returncode, run.stderr)
        message = json.loads(run.stdout)["systemMessage"]
        self.assertIn("SDD drift", message)
        self.assertIn("SDD006", message)

    def test_counter_example_a_turn_that_changed_nothing_is_silent(self):
        self.assertEqual("", self.stop().stdout)

    def test_counter_example_changes_that_still_agree_are_silent(self):
        (self.root / "README.md").write_text("notes\n", encoding="utf-8")
        self.assertEqual("", self.stop().stdout)


@requires_bash
class TestTheSessionHookSaysWhereChangesStand(unittest.TestCase):
    """HOOKS-SESSION-STATUS"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(
            SDD, self.root / ".claude" / "sdd", ignore=shutil.ignore_patterns("__pycache__")
        )
        (self.root / "openspec" / "changes" / "archive").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def session(self) -> str:
        run = subprocess.run(
            [BASH, str(HOOKS / "session-context.sh")],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
            check=False,
        )
        self.assertEqual(0, run.returncode, run.stderr)
        return run.stdout

    def test_an_in_flight_change_is_reported_with_its_next_stage(self):
        change = self.root / "openspec" / "changes" / "add-routing"
        change.mkdir()
        (change / "intake.md").write_text("- **Class:** bounded\n", encoding="utf-8")
        out = self.session()
        self.assertIn("add-routing [bounded]", out)
        self.assertIn("next: frame", out)

    def test_counter_example_nothing_in_flight_prints_nothing(self):
        self.assertEqual("", self.session())


if __name__ == "__main__":
    unittest.main()

"""Install and update: a method that travels without overwriting a project's decisions.

Each class proves one requirement in .claude/sdd/specs/distribution/spec.md.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sddsupport import BASH, DEFAULT_CONFIG, LOCAL_ONLY, SDD, denied, run_serve

from sddlib import OPENSPEC_VERSION, VERSION
from sddlib.distribute import (
    MANIFEST,
    SEEDS,
    build_manifest,
    check_manifest,
    has_changelog_entry,
    install,
    pack_of,
    read_manifest,
    update,
    write_manifest,
)
from sddlib.stats import collect

REPO = SDD.parents[1]


class SourceAndTarget(unittest.TestCase):
    """A throwaway copy of the method as a source, and an empty project as a target."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.source, self.target = tmp / "source", tmp / "target"
        self.target.mkdir()
        for path in REPO.rglob("*"):
            rel = path.relative_to(REPO).as_posix()
            if path.is_file() and (pack_of(rel) or rel in SEEDS.values()):
                destination = self.source / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        self.release()

    def tearDown(self):
        self._tmp.cleanup()

    def release(self) -> None:
        """What a maintainer does after changing a shipped file: regenerate the manifest."""
        write_manifest(self.source, build_manifest(self.source))

    def edit_source(self, rel: str, extra: str) -> None:
        path = self.source / rel
        path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")


class TestInstallCopiesTheMethodAndSeedsOnce(SourceAndTarget):
    """DIST-INSTALL"""

    def test_a_fresh_project_gets_core_its_packs_and_its_seeds(self):
        report = install(self.source, self.target, ["python"])
        self.assertTrue((self.target / ".claude/skills/intake/SKILL.md").is_file())
        self.assertTrue((self.target / ".claude/rules/python/domain.md").is_file())
        self.assertFalse((self.target / ".claude/rules/langgraph/graphs.md").exists())
        for seed in (
            "sdd.toml",
            ".claude/settings.json",
            "openspec/config.yaml",
            "openspec/specs/.gitkeep",
        ):
            self.assertTrue((self.target / seed).is_file(), seed)
        self.assertEqual(["core", "python"], read_manifest(self.target)["packs"])
        self.assertIn(".claude/skills/intake/SKILL.md", report.written)

    def test_counter_example_files_the_project_owns_are_never_written(self):
        install(self.source, self.target, ["python", "langgraph"])
        for never in ("CLAUDE.md", "pyproject.toml", ".env", "src", "tests"):
            self.assertFalse((self.target / never).exists(), never)

    def test_an_existing_file_is_left_alone_and_reported(self):
        guard = self.target / ".claude/hooks/guard-edits.sh"
        guard.parent.mkdir(parents=True)
        guard.write_text("# the project's own guard\n", encoding="utf-8")
        report = install(self.source, self.target, [])
        self.assertEqual("# the project's own guard\n", guard.read_text(encoding="utf-8"))
        self.assertIn(".claude/hooks/guard-edits.sh", report.kept)

    def test_running_it_twice_writes_nothing_the_second_time(self):
        install(self.source, self.target, [])
        again = install(self.source, self.target, [])
        self.assertEqual(([], []), (again.written, again.seeded))

    def test_an_unknown_pack_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown pack"):
            install(self.source, self.target, ["rust"])


class TestUpdateReplacesOnlyWhatTheProjectNeverTouched(SourceAndTarget):
    """DIST-UPDATE"""

    def setUp(self):
        super().setUp()
        install(self.source, self.target, ["python"])

    def test_a_pristine_file_is_replaced_and_a_modified_one_is_left_alone(self):
        self.target.joinpath(".claude/skills/tdd/SKILL.md").write_text(
            "local edit\n", encoding="utf-8"
        )
        self.edit_source(".claude/skills/tdd/SKILL.md", "\nupstream edit\n")
        self.edit_source(".claude/skills/accept/SKILL.md", "\nupstream edit\n")
        self.release()
        report = update(self.source, self.target)
        self.assertIn(".claude/skills/accept/SKILL.md", report.replaced)
        self.assertIn(
            "upstream edit", self.target.joinpath(".claude/skills/accept/SKILL.md").read_text()
        )
        self.assertIn(".claude/skills/tdd/SKILL.md", report.kept)
        self.assertEqual(
            "local edit\n", self.target.joinpath(".claude/skills/tdd/SKILL.md").read_text()
        )

    def test_a_file_retired_upstream_is_removed_only_if_untouched(self):
        self.target.joinpath(".claude/agents/observability-auditor.md").write_text(
            "local\n", encoding="utf-8"
        )
        for rel in (
            ".claude/agents/mutation-analyst.md",
            ".claude/agents/observability-auditor.md",
        ):
            (self.source / rel).unlink()
        self.release()
        report = update(self.source, self.target)
        self.assertIn(".claude/agents/mutation-analyst.md", report.removed)
        self.assertFalse((self.target / ".claude/agents/mutation-analyst.md").exists())
        self.assertIn(".claude/agents/observability-auditor.md", report.kept)

    def test_counter_example_a_file_the_project_deleted_is_not_restored(self):
        (self.target / ".claude/agents/mutation-analyst.md").unlink()
        report = update(self.source, self.target)
        self.assertIn(".claude/agents/mutation-analyst.md", report.not_restored)
        self.assertFalse((self.target / ".claude/agents/mutation-analyst.md").exists())

    def test_counter_example_seeds_are_never_updated(self):
        self.target.joinpath("sdd.toml").write_text("# mine\n", encoding="utf-8")
        self.edit_source(".claude/sdd/seeds/sdd.toml", "\n# upstream\n")
        self.release()
        update(self.source, self.target)
        self.assertEqual("# mine\n", self.target.joinpath("sdd.toml").read_text())

    def test_a_dry_run_writes_nothing(self):
        self.edit_source(".claude/skills/accept/SKILL.md", "\nupstream edit\n")
        self.release()
        report = update(self.source, self.target, dry_run=True)
        self.assertIn(".claude/skills/accept/SKILL.md", report.replaced)
        self.assertNotIn(
            "upstream edit", self.target.joinpath(".claude/skills/accept/SKILL.md").read_text()
        )

    def test_a_project_without_the_method_is_told_to_install(self):
        with (
            tempfile.TemporaryDirectory() as empty,
            self.assertRaisesRegex(ValueError, "not installed"),
        ):
            update(self.source, Path(empty))


class TestAPackSeedsItsOwnFiles(SourceAndTarget):
    """DIST-PACK-SEEDS"""

    SETTINGS = ".claude/settings.json"
    CORE = ".claude/sdd/seeds/settings.json"
    ADDITIONS = ".claude/sdd/seeds/settings.langgraph.json"

    def source_json(self, rel: str) -> dict:
        return json.loads((self.source / rel).read_text(encoding="utf-8"))

    def test_the_langgraph_pack_seeds_its_wrapper_and_adds_to_the_settings(self):
        report = install(self.source, self.target, ["langgraph"])
        self.assertTrue((self.target / "scripts/serve.sh").is_file())
        self.assertIn("scripts/serve.sh", report.seeded)
        core, additions = self.source_json(self.CORE), self.source_json(self.ADDITIONS)
        settings = json.loads((self.target / self.SETTINGS).read_text(encoding="utf-8"))
        self.assertEqual(core["hooks"], settings["hooks"])
        self.assertEqual(core["permissions"]["allow"], settings["permissions"]["allow"])
        self.assertEqual(
            core["permissions"]["deny"] + additions["permissions"]["deny"],
            settings["permissions"]["deny"],
        )
        self.assertEqual({**core["env"], **additions["env"]}, settings["env"])

    def test_without_the_pack_neither_is_seeded(self):
        install(self.source, self.target, ["python"])
        self.assertFalse((self.target / "scripts/serve.sh").exists())
        self.assertEqual(
            (self.source / self.CORE).read_bytes(), (self.target / self.SETTINGS).read_bytes()
        )

    def test_settings_a_project_has_are_left_alone_and_the_merge_reported(self):
        existing = self.target / self.SETTINGS
        existing.parent.mkdir(parents=True)
        existing.write_text('{"permissions": {"deny": []}}\n', encoding="utf-8")
        report = install(self.source, self.target, ["langgraph"])
        self.assertEqual('{"permissions": {"deny": []}}\n', existing.read_text(encoding="utf-8"))
        self.assertIn(self.ADDITIONS, report.merge_by_hand)
        self.assertIn("by hand", report.describe())

    def test_malformed_settings_are_left_alone_and_reported_not_crashed_on(self):
        existing = self.target / self.SETTINGS
        existing.parent.mkdir(parents=True)
        existing.write_text('{"env": [], "permissions": []}\n', encoding="utf-8")
        report = install(self.source, self.target, ["langgraph"])
        self.assertEqual('{"env": [], "permissions": []}\n', existing.read_text(encoding="utf-8"))
        self.assertIn(self.ADDITIONS, report.merge_by_hand)

    def test_update_reports_a_pack_seed_the_project_lacks_and_writes_nothing(self):
        install(self.source, self.target, ["langgraph"])
        (self.target / "scripts/serve.sh").unlink()
        report = update(self.source, self.target)
        self.assertIn("scripts/serve.sh", report.unseeded)
        self.assertFalse((self.target / "scripts/serve.sh").exists())

    def test_counter_example_settings_that_already_hold_the_additions_are_not_reported(self):
        install(self.source, self.target, ["langgraph"])
        again = install(self.source, self.target, ["langgraph"])
        self.assertEqual(([], []), (again.seeded, again.merge_by_hand))

    def test_counter_example_a_merge_never_drops_or_overrides_a_key(self):
        original = (self.source / self.ADDITIONS).read_text(encoding="utf-8")
        for named in ("hooks", "OPENSPEC_TELEMETRY"):
            with self.subTest(named=named):
                additions = json.loads(original)
                if named == "hooks":
                    additions["hooks"] = {}
                else:
                    additions["env"]["OPENSPEC_TELEMETRY"] = "1"
                (self.source / self.ADDITIONS).write_text(json.dumps(additions), encoding="utf-8")
                self.release()
                with self.assertRaisesRegex(ValueError, named):
                    install(self.source, self.target, ["langgraph"])
                self.assertEqual([], list(self.target.iterdir()))


@unittest.skipUnless(BASH, "bash is required to run the wrapper")
class TestALangGraphInstallIsLocalOnly(SourceAndTarget):
    """DIST-PACK-SEEDS, end to end -- the story test of the change that made the
    langgraph pack local-only: a fresh install is local-only, with no edit by hand."""

    def test_a_fresh_install_serves_on_loopback_and_denies_hosted_commands(self):
        install(self.source, self.target, ["python", "langgraph"])
        (self.target / "langgraph.json").write_text(DEFAULT_CONFIG, encoding="utf-8")
        served = run_serve(self.target, exports={"LANGSMITH_API_KEY": "lsv2_from_shell"})
        self.assertEqual(0, served.run.returncode, served.run.stderr)
        self.assertIn("127.0.0.1", served.argv)
        self.assertIn("--no-browser", served.argv)
        self.assertEqual(LOCAL_ONLY, {k: v for k, v in served.env.items() if k in LOCAL_ONLY})
        settings = json.loads((self.target / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(LOCAL_ONLY, {k: v for k, v in settings["env"].items() if k in LOCAL_ONLY})
        self.assertTrue(denied("uv run langgraph dev --tunnel", settings["permissions"]["deny"]))
        self.assertFalse(denied("bash scripts/serve.sh", settings["permissions"]["deny"]))


class TestTheManifestMovesWithWhatShips(SourceAndTarget):
    """DIST-MANIFEST"""

    def test_a_current_manifest_passes(self):
        self.assertEqual([], check_manifest(self.source))

    def test_a_shipped_file_changed_without_the_manifest_fails(self):
        self.edit_source(".claude/skills/intake/SKILL.md", "\nsilent change\n")
        self.assertTrue(any("changed since" in p for p in check_manifest(self.source)))

    def test_a_stale_source_is_refused_before_anything_is_copied(self):
        self.edit_source(".claude/skills/intake/SKILL.md", "\nsilent change\n")
        with self.assertRaisesRegex(ValueError, "does not match"):
            install(self.source, self.target, [])
        self.assertEqual([], list(self.target.iterdir()))

    def test_counter_example_a_project_file_is_not_part_of_the_method(self):
        self.assertIsNone(pack_of(".claude/rules/project/lessons.md"))
        self.assertIsNone(pack_of(".claude/skills/deploy/SKILL.md"))
        self.assertIsNone(pack_of(MANIFEST))
        self.assertEqual(
            "langgraph", pack_of(".claude/skills/discover/references/orchestration-ladder.md")
        )
        self.assertEqual("langgraph", pack_of(".claude/skills/accept/references/graph-routes.md"))
        self.assertEqual("core", pack_of(".claude/skills/discover/references/splitting-rules.md"))


class TestOneVersionOfEachFact(unittest.TestCase):
    """DIST-ONE-VERSION -- the pinned OpenSpec release is stated once, checked twice."""

    def test_sdd_sh_pins_the_same_openspec_as_the_library(self):
        pinned = re.search(r'^OPENSPEC_VERSION="([^"]+)"', (SDD / "sdd.sh").read_text(), re.M)
        self.assertEqual(OPENSPEC_VERSION, pinned.group(1))

    def test_the_changelog_has_an_entry_for_this_version(self):
        self.assertTrue(
            has_changelog_entry((SDD / "CHANGELOG.md").read_text(encoding="utf-8"), VERSION)
        )

    def test_counter_example_a_version_mentioned_in_prose_is_not_an_entry(self):
        self.assertFalse(has_changelog_entry("## 0.1.0\nSee 0.2.0 for what comes next.\n", "0.2.0"))
        self.assertTrue(has_changelog_entry("## 0.2.0 -- 2026-10-04\n", "0.2.0"))


class TestMethodHealthIsReadFromFiles(unittest.TestCase):
    """HEALTH-FROM-FILES"""

    def test_classes_skips_amendments_and_defects_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "openspec" / "changes" / "archive"
            spec = "## MODIFIED Requirements\n\n### Requirement: CAP-A\n- **Kind:** deterministic\n"
            for name, klass, files in (
                (
                    "2026-01-01-fix",
                    "defect",
                    {"frame.md": "x", "tasks.md": "x", "verify.md": "x", "specs/c/spec.md": spec},
                ),
                (
                    "2026-01-02-tweak",
                    "bounded",
                    {"frame.md": "x", "tasks.md": "x", "specs/c/spec.md": spec},
                ),
            ):
                for rel, text in {"intake.md": f"- **Class:** {klass}\n", **files}.items():
                    path = archive / name / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
            numbers = collect(root)
        self.assertEqual(
            2, numbers["requirements amended after implementation (MODIFIED deltas archived)"]
        )
        self.assertEqual({"modified an existing requirement": 1}, numbers["defects"])
        skipped = numbers["stages skipped, by intake class"]
        self.assertEqual(
            {"changes": 1, "skipped design": 1, "skipped verify": 1}, skipped["bounded"]
        )
        self.assertEqual(
            "not collected -- needs session data, which files do not hold",
            numbers["cycles per requirement"],
        )


if __name__ == "__main__":
    unittest.main()

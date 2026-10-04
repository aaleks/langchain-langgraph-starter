"""The proof checker, proved against fixtures it must fail on -- and one it must pass.

Each class proves one requirement in .claude/sdd/specs/traceability/spec.md.
The fixtures live in ../fixtures/check/, one readable file per failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import date
from pathlib import Path

from sddsupport import SDD, all_fixtures, load_fixture, materialize, run_fixture

from sddlib.adapter import AdapterError, load
from sddlib.specs import parse


def flagged(result, code: str) -> list[str]:
    """The requirement ids (first word of each message) a code was raised for."""
    return sorted(d.message.split()[0] for d in result.diagnostics if d.code == code)


class TestEveryFixtureHoldsItsExpectation(unittest.TestCase):
    """The net under every rule: each fixture produces EXACTLY the codes it declares."""

    def test_each_fixture_produces_exactly_its_declared_diagnostics(self):
        fixtures = all_fixtures("check")
        # Guard against a vacuous pass if the fixtures move or vanish.
        self.assertGreaterEqual(len(fixtures), 20, "check fixtures are missing")
        for path in fixtures:
            with self.subTest(fixture=path.name):
                fixture, result = run_fixture(path)
                for severity in ("error", "warning", "info"):
                    self.assertEqual(
                        fixture.expect[severity],
                        result.codes(severity),
                        f"{path.name}: {severity} codes differ",
                    )

    def test_a_misspelled_fixture_header_is_refused_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "typo.txtar"
            bad.write_text("expect-error: SDD001\n-- sdd.toml --\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_fixture(bad)


class TestKindIsDeclared(unittest.TestCase):
    """TRACE-KIND -- every requirement is deterministic or evaluated."""

    def test_a_missing_kind_and_a_misspelled_kind_are_both_refused(self):
        _, result = run_fixture("kind")
        self.assertEqual(["CAP-NO-KIND", "CAP-TYPO-KIND"], flagged(result, "SDD001"))
        self.assertFalse(result.ok)

    def test_counter_example_either_kind_passes_this_rule(self):
        _, result = run_fixture("valid-project")
        self.assertNotIn("SDD001", result.codes("error"))  # one deterministic, one evaluated


class TestProofIsNamed(unittest.TestCase):
    """TRACE-PROOF-NAMED -- a requirement that must be proved names its test."""

    def test_silence_and_prose_are_not_proof(self):
        _, result = run_fixture("deterministic-without-proof")
        self.assertEqual(["CAP-PROSE-PROOF", "CAP-SILENT"], flagged(result, "SDD002"))
        prose = next(d for d in result.diagnostics if "CAP-PROSE-PROOF" in d.message)
        self.assertIn("prose", prose.message)

    def test_an_agreed_threshold_must_name_the_check_that_measures_it(self):
        _, result = run_fixture("agreed-threshold-without-check")
        self.assertEqual(["CAP-AGREED-UNMEASURED"], flagged(result, "SDD002"))

    def test_not_met_is_the_one_honest_exemption(self):
        _, result = run_fixture("overdue-exception")
        self.assertNotIn("SDD002", result.codes("error"))


class TestNamedTestsExist(unittest.TestCase):
    """TRACE-PROOF-RESOLVES -- every named test file and name exists, and is a test."""

    def test_a_missing_file_is_refused_living_or_in_flight_and_says_which(self):
        _, result = run_fixture("dangling-reference")
        self.assertEqual(["CAP-MOVED", "CAP2-NOT-WRITTEN-YET"], flagged(result, "SDD003"))
        messages = " ".join(d.message for d in result.diagnostics)
        self.assertIn("named by the living spec", messages)
        self.assertIn("named by change 'add-x'", messages)

    def test_a_renamed_test_is_refused(self):
        _, result = run_fixture("renamed-test")
        self.assertEqual(["CAP-RENAMED"], flagged(result, "SDD004"))
        self.assertIn("TestOldName", result.diagnostics[0].message)

    def test_naming_the_implementation_as_its_own_proof_is_refused(self):
        _, result = run_fixture("reference-outside-tests")
        self.assertEqual(["CAP-SELF-PROVED"], flagged(result, "SDD003"))
        self.assertIn("not a test file", result.diagnostics[0].message)

    def test_counter_example_a_file_level_reference_is_enough(self):
        _, result = run_fixture("unclaimed-test")  # CAP-ONE names tests/test_cap.py, no ::Name
        self.assertEqual([], flagged(result, "SDD003") + flagged(result, "SDD004"))


class TestEvaluatedCarriesThresholdAndN(unittest.TestCase):
    """TRACE-EVALUATED-THRESHOLD -- threshold, N and who agreed; OPEN legal, silence not."""

    def test_silence_and_vagueness_are_both_refused(self):
        _, result = run_fixture("evaluated-without-threshold")
        self.assertEqual(["CAP-SILENT-JUDGE", "CAP-VAGUE-JUDGE"], flagged(result, "SDD005"))
        vague = next(d for d in result.diagnostics if "CAP-VAGUE-JUDGE" in d.message)
        self.assertIn("neither a number nor OPEN", vague.message)
        self.assertIn("neither a whole number nor OPEN", vague.message)

    def test_fewer_than_twenty_cases_warns_and_does_not_fail(self):
        _, result = run_fixture("small-n")
        self.assertEqual(["CAP-THIN-EVIDENCE"], flagged(result, "SDD012"))
        self.assertTrue(result.ok)

    def test_open_with_an_owner_and_a_date_is_legal(self):
        _, result = run_fixture("valid-project")
        self.assertTrue(result.ok)
        self.assertEqual(set(), result.codes("warning"))


class TestEveryTestFileIsClaimed(unittest.TestCase):
    """TRACE-TESTS-CLAIMED -- a test no requirement claims is behaviour nobody agreed to."""

    def test_the_orphan_is_named_and_the_claimed_file_is_not(self):
        _, result = run_fixture("unclaimed-test")
        targets = [d.target for d in result.diagnostics if d.code == "SDD006"]
        self.assertEqual(["tests/test_orphan.py"], targets)

    def test_a_claim_from_an_in_flight_change_counts_and_exempt_roots_are_skipped(self):
        _, result = run_fixture("valid-project")
        self.assertEqual(2, result.summary.test_files)  # tests/architecture is exempt
        self.assertEqual(2, result.summary.claimed)  # farewell is claimed by add-farewell


class TestCounterExampleIsPresent(unittest.TestCase):
    """TRACE-COUNTER-EXAMPLE -- every requirement shows where it does not apply."""

    def test_only_positive_scenarios_and_no_scenarios_are_both_refused(self):
        _, result = run_fixture("no-counter-example")
        self.assertEqual(["CAP-NO-SCENARIOS", "CAP-ONLY-HAPPY"], flagged(result, "SDD007"))
        none = next(d for d in result.diagnostics if "CAP-NO-SCENARIOS" in d.message)
        self.assertIn("no scenarios at all", none.message)

    def test_the_counter_example_title_is_matched_however_it_is_spelled(self):
        text = textwrap.dedent(
            """\
            ### Requirement: CAP-A
            - **Kind:** deterministic
            #### Scenario: counterexample: lower case, no hyphen
            ### Requirement: CAP-B
            - **Kind:** deterministic
            #### Scenario: Counter-examples -- plural
            ### Requirement: CAP-C
            - **Kind:** deterministic
            #### Scenario: A counter-example in the middle does not count
            """
        )
        found = {
            r.id: r.has_counter_example for r in parse(text, file="x", capability="c", change=None)
        }
        self.assertEqual({"CAP-A": True, "CAP-B": True, "CAP-C": False}, found)


class TestExceptionsHaveOwners(unittest.TestCase):
    """TRACE-EXCEPTION-OWNED -- NOT MET and OPEN carry an owner and a review date."""

    def test_missing_owner_missing_date_and_a_non_date_are_refused(self):
        _, result = run_fixture("exception-without-owner")
        self.assertEqual(["CAP-OPEN-THRESHOLD", "CAP-UNMET"], flagged(result, "SDD008"))

    def test_a_date_in_the_past_warns(self):
        _, result = run_fixture("overdue-exception")
        self.assertEqual(["CAP-STALE"], flagged(result, "SDD009"))
        self.assertTrue(result.ok)

    def test_due_today_is_not_overdue(self):
        """The counter-example: the off-by-one on the review boundary."""
        _, result = run_fixture("due-today-is-not-overdue")
        self.assertEqual([], result.diagnostics)


class TestIdsAreStableAndUnique(unittest.TestCase):
    """CHECKER-STABLE-IDS -- ids are upper-kebab and unique; a change MODIFIES, never re-ADDS."""

    def test_duplicates_across_capabilities_and_re_added_ids_are_refused(self):
        _, result = run_fixture("duplicate-id")
        duplicates = [d for d in result.diagnostics if d.code == "SDD010"]
        self.assertEqual(2, len(duplicates))
        self.assertTrue(any("MODIFIED" in d.fix for d in duplicates))

    def test_a_sentence_is_not_an_id(self):
        _, result = run_fixture("prose-id")
        self.assertEqual(["SDD011"], [d.code for d in result.diagnostics])

    def test_counter_example_a_modified_delta_repeats_the_id_on_purpose(self):
        _, result = run_fixture("modified-keeps-its-id")
        self.assertEqual([], result.diagnostics)


class TestDeltasArchiveCleanly(unittest.TestCase):
    """CHECKER-DELTA-STRUCTURE -- a change modifies what exists, under a delta section."""

    def test_an_unknown_modified_id_and_a_stray_requirement_are_refused(self):
        _, result = run_fixture("delta-structure")
        self.assertEqual(["CAP-STRAY", "MODIFIED"], flagged(result, "SDD013"))

    def test_an_archived_change_is_history_and_is_never_checked(self):
        _, result = run_fixture("valid-project")
        self.assertTrue(result.ok)
        self.assertEqual(1, result.summary.changes)  # archive/ is not a change in flight


class TestAdapterIsStrict(unittest.TestCase):
    """CHECKER-ADAPTER-STRICT -- the adapter refuses what it does not understand."""

    def test_a_missing_directory_is_a_misconfiguration_not_an_empty_project(self):
        _, result = run_fixture("missing-specs-dir")
        self.assertEqual(["SDD000"], [d.code for d in result.diagnostics])
        self.assertIn("docs/specs-moved-away", result.diagnostics[0].message)

    def test_an_unknown_key_is_refused_by_name(self):
        _, result = run_fixture("unknown-adapter-key")
        self.assertIn("livng_typo", result.diagnostics[0].message)

    def _load(self, toml: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "specs").mkdir()
            (root / "tests").mkdir()
            (root / "sdd.toml").write_text(textwrap.dedent(toml), encoding="utf-8")
            return load(root / "sdd.toml", root)

    def test_a_guards_array_split_across_lines_is_refused(self):
        with self.assertRaisesRegex(AdapterError, "one line"):
            self._load(
                """\
                [specs]
                living = "specs"
                [tests]
                roots = ["tests"]
                patterns = ["test_*.py"]
                [guards]
                ground_truth = [
                  "tests/evals/golden/*",
                ]
                """
            )

    def test_a_symbol_regex_without_a_capture_group_is_refused(self):
        with self.assertRaisesRegex(AdapterError, "group"):
            self._load(
                """\
                [specs]
                living = "specs"
                [tests]
                roots = ["tests"]
                patterns = ["*.test.ts"]
                symbols = "regex:it\\\\("
                """
            )

    def test_a_minimal_adapter_takes_the_defaults(self):
        adapter = self._load(
            """\
            [specs]
            living = "specs"
            [tests]
            roots = ["tests"]
            patterns = ["test_*.py"]
            """
        )
        self.assertEqual(("python", None, ()), (adapter.symbols, adapter.changes, adapter.exempt))


class TestNothingPassesVacuously(unittest.TestCase):
    """CHECKER-HONEST-EMPTY -- an empty project says so; it neither fails nor passes silently."""

    def test_an_empty_project_is_ok_with_an_info_line(self):
        _, result = run_fixture("empty-project")
        self.assertTrue(result.ok)
        self.assertEqual(["SDD100"], [d.code for d in result.diagnostics])

    def test_counter_example_one_test_file_makes_the_project_not_empty(self):
        from sddlib.check import run

        fixture = load_fixture(SDD / "fixtures" / "check" / "empty-project.txtar")
        with tempfile.TemporaryDirectory() as tmp:
            root = materialize(fixture, Path(tmp))
            (root / "tests" / "test_new.py").write_text(
                "def test_x():\n    pass\n", encoding="utf-8"
            )
            result = run(root, today=fixture.today)
        self.assertEqual(["SDD006"], [d.code for d in result.diagnostics])


class TestTheParserReadsOnlyWhatIsReal(unittest.TestCase):
    """CHECKER-PARSER -- fences, comments and scenario bodies are never read as fields."""

    def test_fences_comments_continuations_and_scenario_bullets(self):
        text = textwrap.dedent(
            """\
            ## Requirements
            <!-- ### Requirement: COMMENTED-OUT
                 spanning lines -->
            ### Requirement: CAP-REAL
            The system SHALL do it.

            - **Kind:** deterministic
            - **Proved by:** `tests/test_a.py`,
              `tests/test_b.py`
            - **Owner:** <!-- inline comment --> ada

            #### Scenario: Normal
            - **Kind:** evaluated

            ```markdown
            ### Requirement: FENCED-OUT
            ```
            """
        )
        [requirement] = parse(text, file="x", capability="c", change=None)
        self.assertEqual("CAP-REAL", requirement.id)
        self.assertEqual("deterministic", requirement.value("kind"))  # not the scenario bullet
        self.assertEqual("`tests/test_a.py`, `tests/test_b.py`", requirement.value("proved by"))
        self.assertEqual("ada", requirement.value("owner"))


class TestTheCommandLine(unittest.TestCase):
    """CHECKER-ENVELOPE -- one shape for hook, terminal, CI and agent; exit 1 on error."""

    def _cli(self, fixture: str, *args: str) -> subprocess.CompletedProcess:
        loaded = load_fixture(SDD / "fixtures" / "check" / f"{fixture}.txtar")
        with tempfile.TemporaryDirectory() as tmp:
            root = materialize(loaded, Path(tmp))
            return subprocess.run(
                [sys.executable, str(SDD / "sdd.py"), "--root", str(root), "check", *args],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_errors_exit_one_with_the_envelope(self):
        run = self._cli("no-counter-example", "--json")
        self.assertEqual(1, run.returncode, run.stderr)
        payload = json.loads(run.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(
            {"severity", "code", "message", "target", "fix"}, set(payload["diagnostics"][0])
        )

    def test_a_clean_project_exits_zero(self):
        run = self._cli("valid-project")
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertTrue(run.stdout.startswith("sdd check: OK"))

    def test_warnings_alone_do_not_fail_the_build(self):
        run = self._cli("overdue-exception", "--today", date(2026, 10, 4).isoformat())
        self.assertEqual(0, run.returncode, run.stdout)
        self.assertIn("SDD009", run.stdout)


if __name__ == "__main__":
    unittest.main()

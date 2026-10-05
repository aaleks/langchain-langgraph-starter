"""Where a change stands, read from its files -- what the SessionStart hook reports."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sddlib.status import read


def change(root: Path, name: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / "openspec" / "changes" / name / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class TestResumeAtTheEarliestIncompleteStage(unittest.TestCase):
    """HOOKS-NEXT-STAGE -- a session resumes where the change actually stands."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "openspec" / "changes" / "archive" / "old").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def next_of(self, name: str) -> str | None:
        return {c.id: c.next_stage for c in read(self.root)}[name]

    def test_a_bounded_change_skips_design_and_waits_on_its_tasks(self):
        change(
            self.root,
            "fix-x",
            {
                "intake.md": "- **Class:** bounded\n",
                "frame.md": "x",
                "specs/cap/spec.md": "x",
                "tasks.md": "- [x] 1.1 a\n- [ ] 1.2 b\n",
            },
        )
        self.assertEqual("apply (1/2 tasks done)", self.next_of("fix-x"))

    def test_a_structural_change_cannot_skip_design(self):
        change(
            self.root,
            "big",
            {"intake.md": "- **Class:** structural\n", "frame.md": "x", "specs/c/spec.md": "x"},
        )
        self.assertEqual("design", self.next_of("big"))

    def test_verified_ship_means_land_and_do_not_ship_means_verify_again(self):
        done = {"intake.md": "- **Class:** bounded\n", "frame.md": "x", "specs/c/spec.md": "x"}
        done["tasks.md"] = "- [x] 1.1 a\n"
        change(self.root, "ready", {**done, "verify.md": "- **Verdict:** SHIP\n"})
        change(self.root, "blocked", {**done, "verify.md": "- **Verdict:** DO NOT SHIP\n"})
        self.assertEqual("land", self.next_of("ready"))
        self.assertEqual("verify (verdict is not SHIP)", self.next_of("blocked"))

    def test_a_spike_is_done_when_its_verdict_is_recorded(self):
        change(
            self.root, "probe", {"intake.md": "- **Class:** spike\n- **Verdict:** kill -- slower\n"}
        )
        self.assertIsNone(self.next_of("probe"))

    def test_a_declared_skip_specs_moves_past_specs_as_openspec_does(self):
        change(
            self.root,
            "method",
            {
                ".openspec.yaml": "schema: sdd-proof\ncreated: 2026-10-05\nskip_specs: true\n",
                "intake.md": "- **Class:** structural\n",
                "frame.md": "x",
            },
        )
        self.assertEqual("design", self.next_of("method"))
        (status,) = read(self.root)
        self.assertIn("specs~", status.line())

    def test_counter_example_without_the_declaration_a_missing_spec_is_a_missing_stage(self):
        for name, declaration in (("silent", ""), ("declined", "skip_specs: false\n")):
            with self.subTest(declaration=declaration):
                change(
                    self.root,
                    name,
                    {
                        ".openspec.yaml": "schema: sdd-proof\n" + declaration,
                        "intake.md": "- **Class:** bounded\n",
                        "frame.md": "x",
                    },
                )
                self.assertEqual("specs", self.next_of(name))

    def test_counter_example_archived_changes_are_not_in_flight(self):
        self.assertEqual([], read(self.root))


if __name__ == "__main__":
    unittest.main()

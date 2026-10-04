"""The proof checker: does every requirement name a proof, and is every test claimed?

The rule list is closed. Six rules, each failing the build:

    1. every requirement has a Kind                                   SDD001
    2. every requirement that must be proved names a test that exists  SDD002-004
    3. every evaluated requirement has a Threshold, an N, an Agreed by SDD005
    4. every test file is claimed by some requirement                  SDD006
    5. every requirement has a counter-example scenario                SDD007
    6. every exception (NOT MET, OPEN) has an Owner and a Review by    SDD008

plus the structure they depend on (unique, stable ids; deltas that archive
cleanly) and two warnings (an overdue review; N below twenty). Anything else is
a template slot or a reader's judgement -- /verify, not this file.

What it cannot do, and says so in the method README: verify that a named test
actually PROVES its requirement. A requirement with four scenarios whose test
asserts two passes every rule here.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .adapter import Adapter, AdapterError, load
from .report import Result
from .specs import CHECKED, REQUIREMENT_ID, Requirement, load_changes, load_living
from .testfiles import SymbolIndex, discover, is_test_name, under_roots

KINDS = ("deterministic", "evaluated")
REFERENCE = re.compile(r"`([^`]+)`")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Below this a threshold measures the sampler, not the system.
MIN_CASES = 20


def run(root: Path, config: Path | None = None, today: date | None = None) -> Result:
    """Check a project. `today` is a parameter so the overdue boundary is testable."""
    root = root.resolve()
    today = today or date.today()
    result = Result()
    try:
        adapter = load(config or root / "sdd.toml", root)
    except AdapterError as exc:
        result.add(
            "error", "SDD000", str(exc), "sdd.toml", "fix the adapter; see .claude/sdd/README.md"
        )
        return result

    living, capabilities = load_living(root, adapter.living)
    deltas, changes = load_changes(root, adapter.changes)
    tests = discover(root, adapter)
    symbols = SymbolIndex(root, adapter.symbol_pattern)

    summary = result.summary
    summary.capabilities, summary.changes, summary.test_files = capabilities, changes, len(tests)
    summary.requirements = len(living)
    summary.deterministic = sum(1 for r in living if r.value("kind") == "deterministic")
    summary.evaluated = sum(1 for r in living if r.value("kind") == "evaluated")
    summary.change_requirements = sum(1 for r in deltas if r.section in ("added", "modified"))

    _structure(living, deltas, result)
    claimed: set[str] = set()
    for requirement in living + deltas:
        if requirement.section not in CHECKED:
            continue
        _kind(requirement, result)
        _proof(requirement, root, adapter, symbols, claimed, result)
        _evaluated(requirement, result)
        _counter_example(requirement, result)
        _exceptions(requirement, today, result)

    for rel in tests:
        if rel not in claimed:
            result.add(
                "error",
                "SDD006",
                f"{rel} is claimed by no requirement -- behaviour nobody agreed to",
                rel,
                "name it in the Proved by line of the requirement it proves, or write that "
                "requirement first (/discover)",
            )
    summary.claimed = sum(1 for rel in tests if rel in claimed)

    if not living and not deltas and not tests:
        result.add(
            "info",
            "SDD100",
            "nothing specified yet: no requirements and no test files to hold to them",
            adapter.living,
            "start a change with /intake",
        )
    return result


def _structure(living: list[Requirement], deltas: list[Requirement], result: Result) -> None:
    """Unique stable ids, and deltas that archive cleanly."""
    for requirement in living + deltas:
        if requirement.section in CHECKED and not REQUIREMENT_ID.match(requirement.id):
            result.add(
                "error",
                "SDD011",
                f"'{requirement.id}' is not a stable requirement id",
                requirement.target,
                "use <CAPABILITY>-<RULE> in upper kebab, e.g. PROVIDER-PRECEDENCE; the "
                "sentence belongs on the line below the heading",
            )

    first: dict[str, Requirement] = {}
    for requirement in living:
        if requirement.id in first:
            result.add(
                "error",
                "SDD010",
                f"{requirement.id} is also defined at {first[requirement.id].target}",
                requirement.target,
                "requirement ids are unique across all capabilities; rename one",
            )
        else:
            first[requirement.id] = requirement

    added: dict[str, Requirement] = {}
    living_by_capability = {(r.capability, r.id) for r in living}
    for requirement in deltas:
        if requirement.section == "added":
            if requirement.id in first:
                result.add(
                    "error",
                    "SDD010",
                    f"{requirement.id} is ADDED by change '{requirement.change}' but the living "
                    f"spec already has it at {first[requirement.id].target}",
                    requirement.target,
                    "put it under '## MODIFIED Requirements' with its full new text",
                )
            elif requirement.id in added:
                result.add(
                    "error",
                    "SDD010",
                    f"{requirement.id} is ADDED by two changes (also {added[requirement.id].target})",
                    requirement.target,
                    "one change owns a new requirement; rename or merge",
                )
            else:
                added[requirement.id] = requirement
        elif requirement.section in ("modified", "removed"):
            if (requirement.capability, requirement.id) not in living_by_capability:
                result.add(
                    "error",
                    "SDD013",
                    f"{requirement.section.upper()} {requirement.id} does not exist in the living "
                    f"spec for capability '{requirement.capability}'",
                    requirement.target,
                    "check the id and the capability path; a new requirement belongs under ADDED",
                )
        elif requirement.section == "stray":
            result.add(
                "error",
                "SDD013",
                f"{requirement.id} sits outside an ADDED/MODIFIED/REMOVED/RENAMED section, "
                "so archive would drop it",
                requirement.target,
                "move it under the delta section that says what the change does to it",
            )


def _kind(requirement: Requirement, result: Result) -> None:
    kind = requirement.value("kind")
    if kind is None:
        result.add(
            "error",
            "SDD001",
            f"{requirement.id} has no Kind",
            requirement.target,
            "add '- **Kind:** deterministic' (asserted with ==) or 'evaluated' (scored "
            "against an agreed threshold)",
        )
    elif kind not in KINDS:
        result.add(
            "error",
            "SDD001",
            f"{requirement.id} has Kind '{kind}', which is neither deterministic nor evaluated",
            requirement.target,
            "a typo must not read as a third kind",
        )


def _proof(
    requirement: Requirement,
    root: Path,
    adapter: Adapter,
    symbols: SymbolIndex,
    claimed: set[str],
    result: Result,
) -> None:
    proved_by = requirement.value("proved by") or ""
    references = [r.strip() for r in REFERENCE.findall(proved_by) if r.strip()]
    kind = requirement.value("kind")
    threshold = requirement.value("threshold") or ""
    must_be_proved = not _not_met(requirement) and (
        kind == "deterministic"
        or (kind == "evaluated" and threshold and not _is_open(threshold) and _has_digit(threshold))
    )
    if must_be_proved and not references:
        if kind == "deterministic":
            message = f"{requirement.id} is deterministic and names no test"
        else:
            message = (
                f"{requirement.id} has an agreed threshold and names no check that measures it"
            )
        if proved_by:
            message += " (its Proved by line holds prose, not a `path` reference)"
        result.add(
            "error",
            "SDD002",
            message,
            requirement.target,
            "name the test in backticks: '- **Proved by:** `tests/unit/test_x.py::TestY`'; "
            "or mark '- **Status:** NOT MET' with an Owner and a Review by",
        )

    for reference in references:
        file_part, *nodes = reference.split("::")
        rel = file_part.strip().replace("\\", "/").removeprefix("./")
        nodes = [re.sub(r"\[.*\]$", "", n).strip() for n in nodes if n.strip()]
        where = (
            f"named by change '{requirement.change}'"
            if requirement.change
            else "named by the living spec"
        )
        if not under_roots(rel, adapter) or not is_test_name(Path(rel).name, adapter):
            result.add(
                "error",
                "SDD003",
                f"{requirement.id} names {rel}, which is not a test file "
                f"(roots: {', '.join(adapter.test_roots)}; patterns: {', '.join(adapter.test_patterns)})",
                requirement.target,
                "proof is a test; name the test that exercises this, not the code under test",
            )
            continue
        if not (root / rel).is_file():
            if requirement.change:
                fix = "expected mid-loop: /accept writes it next. A change cannot land until it exists"
            else:
                fix = "the living spec claims a test that is gone: restore it, or correct the reference"
            result.add(
                "error",
                "SDD003",
                f"{requirement.id} names {rel}, which does not exist ({where})",
                requirement.target,
                fix,
            )
            continue
        claimed.add(rel)
        if not nodes:
            continue
        if not symbols.enabled:
            result.add(
                "error",
                "SDD004",
                f"{requirement.id} names {reference}, but this project resolves file references only",
                requirement.target,
                "drop the ::Name parts, or set tests.symbols in sdd.toml",
            )
            continue
        missing = [n for n in nodes if n not in symbols.names(rel)]
        if missing:
            result.add(
                "error",
                "SDD004",
                f"{requirement.id} names {reference}, but {rel} defines no {', '.join(missing)} "
                "-- a renamed test?",
                requirement.target,
                "correct the reference to the test's current name",
            )


def _evaluated(requirement: Requirement, result: Result) -> None:
    if requirement.value("kind") != "evaluated":
        return
    threshold = requirement.value("threshold")
    cases = requirement.value("n")
    agreed = requirement.value("agreed by")
    problems = []
    if not threshold:
        problems.append("no Threshold")
    elif not _is_open(threshold) and not _has_digit(threshold):
        problems.append(f"Threshold '{threshold}' is neither a number nor OPEN")
    if not cases:
        problems.append("no N (how many cases the score is computed over)")
    elif not _is_open(cases) and not cases.split()[0].isdigit():
        problems.append(f"N '{cases}' is neither a whole number nor OPEN")
    if not agreed:
        problems.append("no Agreed by")
    if problems:
        result.add(
            "error",
            "SDD005",
            f"{requirement.id} is evaluated with {'; '.join(problems)}",
            requirement.target,
            "OPEN is legal, silence is not: never invent a threshold -- ask, or record OPEN",
        )
    if cases and cases.split()[0].isdigit() and int(cases.split()[0]) < MIN_CASES:
        result.add(
            "warning",
            "SDD012",
            f"{requirement.id} computes its score over {cases.split()[0]} cases; below "
            f"{MIN_CASES} a threshold measures the sampler, not the system",
            requirement.target,
            "grow the golden set, or say in the requirement why this N is enough",
        )


def _counter_example(requirement: Requirement, result: Result) -> None:
    if requirement.has_counter_example:
        return
    detail = (
        "has no scenarios at all"
        if not requirement.scenarios
        else "has no counter-example scenario"
    )
    result.add(
        "error",
        "SDD007",
        f"{requirement.id} {detail}",
        requirement.target,
        "add '#### Scenario: Counter-example -- <the case where the rule deliberately does "
        "not apply>'; on a threshold rule it is the off-by-one",
    )


def _exceptions(requirement: Requirement, today: date, result: Result) -> None:
    reasons = []
    if _not_met(requirement):
        reasons.append("NOT MET")
    for name, label in (("threshold", "Threshold"), ("n", "N"), ("agreed by", "Agreed by")):
        value = requirement.value(name)
        if value and _is_open(value):
            reasons.append(f"{label} OPEN")
    if not reasons:
        return
    problems = []
    if not requirement.value("owner"):
        problems.append("no Owner")
    review = requirement.value("review by")
    review_date = None
    if not review:
        problems.append("no Review by")
    elif not ISO_DATE.match(review.split()[0]):
        problems.append(f"Review by '{review}' is not a date (YYYY-MM-DD)")
    else:
        try:
            review_date = date.fromisoformat(review.split()[0])
        except ValueError:
            problems.append(f"Review by '{review}' is not a real date")
    if problems:
        result.add(
            "error",
            "SDD008",
            f"{requirement.id} is an exception ({', '.join(reasons)}) with {'; '.join(problems)}",
            requirement.target,
            "an exception without an owner and a date becomes furniture; add "
            "'- **Owner:** <name>' and '- **Review by:** YYYY-MM-DD'",
        )
    elif review_date and review_date < today:
        result.add(
            "warning",
            "SDD009",
            f"{requirement.id} was due for review on {review_date.isoformat()} "
            f"({', '.join(reasons)})",
            requirement.target,
            "is it still unmet, still wanted, still correctly scoped? Decide, then move the date",
        )


def _not_met(requirement: Requirement) -> bool:
    status = requirement.value("status") or ""
    return "NOT MET" in status.upper()


def _is_open(value: str) -> bool:
    return value.strip().upper().startswith("OPEN")


def _has_digit(value: str) -> bool:
    return any(ch.isdigit() for ch in value)

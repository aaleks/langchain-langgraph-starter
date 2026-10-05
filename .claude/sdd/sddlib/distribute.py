"""Taking the method into another project, and taking an update -- without
overwriting a single decision that project made.

A method distributed by copying, with no version and no diff, always ends in
the same state: the installed copy drifts from the source in the direction of
whichever was edited last, and nothing says so. In the project this method came
from, the copy that ran was weaker than the copy that shipped -- one guard
blocked four SDK imports where the other blocked twenty -- and nobody noticed.

So every shipped file is listed in manifest.json with its pack and its hash:

    install   copies what is absent; an existing file is left alone and reported.
    update    replaces a file only if it is still exactly what was installed;
              a file the project modified is reported and left alone; never merged.
    manifest  regenerates the list -- `--check` fails when a shipped file changed
              without the manifest (and so the version) moving with it.

Project-owned files -- sdd.toml, settings, lessons, openspec/config.yaml,
scripts/check.sh -- are SEEDED once from .claude/sdd/seeds/ and never touched
again. A pack seeds its own files too (the langgraph pack: scripts/serve.sh), and
may add rules to the settings install seeds -- merged once, into settings being
seeded, never into settings a project already has. CLAUDE.md, .env,
pyproject.toml, lockfiles, src/ and tests/ are never written at all.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import OPENSPEC_VERSION, VERSION

MANIFEST = ".claude/sdd/manifest.json"

CORE_SKILLS = (
    "intake",
    "discover",
    "accept",
    "tdd",
    "eval",
    "debug",
    "verify",
    "quality",
    "land",
    "learn",
)
CORE_AGENTS = (
    "spec-compliance",
    "code-reviewer",
    "architecture-guardian",
    "determinism-auditor",
    "mutation-analyst",
    "observability-auditor",
)
LANGGRAPH_AGENTS = (
    "graph-architecture-guardian",
    "durability-auditor",
    "agent-capability-auditor",
    "graph-eval-auditor",
)

# Which pack a shipped file belongs to. Ordered: the first matching rule wins,
# so a pack's file inside a core directory is claimed by its pack first.
PACK_RULES: tuple[tuple[str, str], ...] = (
    ("langgraph", ".claude/rules/langgraph/*"),
    *(("langgraph", f".claude/agents/{a}.md") for a in LANGGRAPH_AGENTS),
    ("langgraph", ".claude/skills/discover/references/orchestration-ladder.md"),
    ("langgraph", ".claude/skills/accept/references/graph-routes.md"),
    ("langgraph", ".claude/sdd/packs/langgraph.md"),
    ("python", ".claude/rules/python/*"),
    ("python", ".claude/sdd/packs/python.md"),
    ("core", ".claude/sdd/*"),
    *(("core", f".claude/skills/{s}/*") for s in CORE_SKILLS),
    *(("core", f".claude/agents/{a}.md") for a in CORE_AGENTS),
    ("core", ".claude/rules/sdd/*"),
    ("core", ".claude/hooks/lib.sh"),
    ("core", ".claude/hooks/guard-edits.sh"),
    ("core", ".claude/hooks/check-alignment.sh"),
    ("core", ".claude/hooks/session-context.sh"),
    ("core", "openspec/schemas/sdd-proof/*"),
)
PACKS = ("core", "python", "langgraph")
SKIP = ("__pycache__", ".pyc", MANIFEST)

# Project-owned: written once if absent, never updated. target -> seed file.
SEEDS = {
    "sdd.toml": ".claude/sdd/seeds/sdd.toml",
    ".claude/settings.json": ".claude/sdd/seeds/settings.json",
    ".claude/rules/project/lessons.md": ".claude/sdd/seeds/lessons.md",
    "openspec/config.yaml": ".claude/sdd/seeds/openspec-config.yaml",
    "scripts/check.sh": ".claude/sdd/seeds/check.sh",
    "docs/learnings.md": ".claude/sdd/seeds/learnings.md",
    "openspec/specs/.gitkeep": None,
    "openspec/changes/archive/.gitkeep": None,
}
# A pack's own project-owned files: seeded only when the pack is installed.
PACK_SEEDS = {
    "langgraph": {"scripts/serve.sh": ".claude/sdd/seeds/serve.sh"},
}
# A pack's additions to the settings install seeds: env and permission rules.
SETTINGS = ".claude/settings.json"
PACK_SETTINGS = {"langgraph": ".claude/sdd/seeds/settings.langgraph.json"}
NEVER = ("CLAUDE.md", ".env", "pyproject.toml", "lockfiles", "src/", "tests/")


def pack_of(rel: str) -> str | None:
    if any(part in rel for part in SKIP):
        return None
    for pack, pattern in PACK_RULES:
        if fnmatch.fnmatchcase(rel, pattern):
            return pack
    return None


def sha256(path: Path) -> str:
    # Line endings normalised: a checkout with autocrlf must not read as modified.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_manifest(source: Path) -> dict:
    files = {}
    for base in (source / ".claude", source / "openspec" / "schemas"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(source).as_posix()
                if pack := pack_of(rel):
                    files[rel] = {"pack": pack, "sha256": sha256(path)}
    return {"method": "sdd", "version": VERSION, "openspec": OPENSPEC_VERSION, "files": files}


def read_manifest(root: Path) -> dict | None:
    path = root / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def write_manifest(root: Path, manifest: dict) -> None:
    path = root / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)  # modified locally: left alone
    not_restored: list[str] = field(default_factory=list)  # deleted locally: left deleted
    seeded: list[str] = field(default_factory=list)
    merge_by_hand: list[str] = field(default_factory=list)  # pack settings, settings present
    unseeded: list[str] = field(default_factory=list)  # pack seeds update will not write
    dry_run: bool = False

    def describe(self) -> str:
        sections = (
            ("written", self.written, "+"),
            ("replaced (unchanged since install, so safe to update)", self.replaced, "~"),
            ("removed (retired upstream, unchanged locally)", self.removed, "-"),
            (
                "left alone: modified in this project -- diff against the source and merge by hand",
                self.kept,
                "!",
            ),
            ("left alone: deleted in this project, not restored", self.not_restored, "!"),
            ("seeded (project-owned from now on; never updated)", self.seeded, "+"),
            (
                f"left alone: {SETTINGS} exists -- merge these pack additions into it by hand",
                self.merge_by_hand,
                "!",
            ),
            (
                "not seeded: update never writes a project-owned file -- run install "
                "with the same packs to seed",
                self.unseeded,
                "!",
            ),
        )
        lines = ["dry run -- nothing was written" if self.dry_run else ""]
        for title, items, mark in sections:
            if items:
                lines.append(f"{title} ({len(items)}):")
                lines += [f"  {mark} {item}" for item in sorted(items)]
        if self.current:
            lines.append(f"already current: {len(self.current)} files")
        lines.append("never written by this tool: " + ", ".join(NEVER))
        return "\n".join(line for line in lines if line)


def install(source: Path, target: Path, packs: list[str], dry_run: bool = False) -> Report:
    """Copy the method into a project. An existing file is never overwritten."""
    manifest = _source_manifest(source)
    selected = _select(manifest, ["core", *packs])
    settings = seeded_settings(source, packs)  # a bad merge is refused before any write
    report = Report(dry_run=dry_run)
    for rel, entry in sorted(selected.items()):
        destination = target / rel
        if destination.exists():
            same = sha256(destination) == entry["sha256"]
            (report.current if same else report.kept).append(rel)
        else:
            report.written.append(rel)
            _copy(source / rel, destination, dry_run)
    _seed(source, target, packs, settings, report, dry_run)
    if not dry_run:
        write_manifest(target, {**manifest, "files": selected, "packs": ["core", *packs]})
    return report


def update(source: Path, target: Path, dry_run: bool = False) -> Report:
    """Take a newer method. Replace only what the project never touched."""
    old = read_manifest(target)
    if old is None:
        raise ValueError(
            f"{target} has no {MANIFEST}: the method is not installed there. Use install."
        )
    new_manifest = _source_manifest(source)
    packs = old.get("packs", ["core"])
    new = _select(new_manifest, packs)
    report = Report(dry_run=dry_run)

    for rel, entry in sorted(new.items()):
        destination = target / rel
        installed = old["files"].get(rel)
        if not destination.exists():
            if installed:
                report.not_restored.append(rel)
            else:
                report.written.append(rel)
                _copy(source / rel, destination, dry_run)
            continue
        local = sha256(destination)
        if local == entry["sha256"]:
            report.current.append(rel)
        elif installed and local == installed["sha256"]:
            report.replaced.append(rel)
            _copy(source / rel, destination, dry_run)
        else:
            report.kept.append(rel)

    for rel, installed in sorted(old["files"].items()):
        if rel in new:
            continue
        destination = target / rel
        if destination.exists() and sha256(destination) == installed["sha256"]:
            report.removed.append(rel)
            if not dry_run:
                destination.unlink()
        elif destination.exists():
            report.kept.append(rel)

    report.unseeded += [
        rel for pack in packs for rel in PACK_SEEDS.get(pack, {}) if not (target / rel).exists()
    ]
    if not dry_run:
        write_manifest(target, {**new_manifest, "files": new, "packs": packs})
    return report


def check_manifest(source: Path) -> list[str]:
    """Shipped files that changed without the manifest moving with them."""
    recorded = read_manifest(source)
    if recorded is None:
        return [f"{MANIFEST} is missing -- run: bash .claude/sdd/sdd.sh manifest"]
    actual = build_manifest(source)
    problems = []
    for rel in sorted(set(recorded["files"]) | set(actual["files"])):
        before, after = recorded["files"].get(rel), actual["files"].get(rel)
        if before is None:
            problems.append(f"new shipped file, not in the manifest: {rel}")
        elif after is None:
            problems.append(f"in the manifest, no longer shipped: {rel}")
        elif before != after:
            problems.append(f"changed since the manifest was generated: {rel}")
    if recorded.get("version") != VERSION:
        problems.append(
            f"manifest version {recorded.get('version')} is not the method version {VERSION}"
        )
    changelog = source / ".claude/sdd/CHANGELOG.md"
    if not changelog.is_file() or not has_changelog_entry(
        changelog.read_text(encoding="utf-8"), VERSION
    ):
        problems.append(f"CHANGELOG.md has no '## {VERSION}' entry")
    return problems


def has_changelog_entry(text: str, version: str) -> bool:
    """A `## <version>` heading -- a version mentioned in prose is not an entry."""
    return any(
        line.startswith("## ") and line[3:].split()[:1] == [version] for line in text.splitlines()
    )


def _source_manifest(source: Path) -> dict:
    """The source's manifest, refused if it no longer describes the source."""
    problems = check_manifest(source)
    if problems:
        raise ValueError(
            "the source's manifest does not match its files -- regenerate it before "
            "distributing:\n  " + "\n  ".join(problems)
        )
    return read_manifest(source)


def _select(manifest: dict, packs: list[str]) -> dict:
    unknown = sorted(set(packs) - set(PACKS))
    if unknown:
        raise ValueError(f"unknown pack(s): {', '.join(unknown)} (known: {', '.join(PACKS)})")
    return {rel: e for rel, e in manifest["files"].items() if e["pack"] in packs}


def seeded_settings(source: Path, packs: list[str]) -> str | None:
    """The settings a fresh install seeds: the core seed plus each pack's additions.

    None when no installed pack adds anything, so the core seed is copied byte for
    byte. Raises before install writes anything when an addition cannot merge.
    """
    additions = [PACK_SETTINGS[pack] for pack in packs if pack in PACK_SETTINGS]
    if not additions:
        return None
    settings = json.loads((source / SEEDS[SETTINGS]).read_text(encoding="utf-8"))
    for rel in additions:
        merge_settings(settings, json.loads((source / rel).read_text(encoding="utf-8")), rel)
    return json.dumps(settings, indent=2) + "\n"


def merge_settings(settings: dict, additions: dict, origin: str) -> None:
    """Add a pack's env and permission rules to settings, in place.

    Anything else, and an env value that would change one already there, is
    refused: a merge that dropped or overrode a key silently would make a pack
    look installed when it was not.
    """
    unknown = sorted(set(additions) - {"env", "permissions"})
    if unknown:
        raise ValueError(
            f"{origin}: a pack adds env and permissions only, not {', '.join(unknown)}"
        )
    env = settings.setdefault("env", {})
    for key, value in additions.get("env", {}).items():
        if key in env and env[key] != value:
            raise ValueError(f"{origin}: env {key} would change {env[key]!r} to {value!r}")
        env[key] = value
    permissions = settings.setdefault("permissions", {})
    for kind, rules in additions.get("permissions", {}).items():
        if kind not in ("allow", "ask", "deny"):
            raise ValueError(f"{origin}: a pack adds permissions allow, ask or deny, not {kind}")
        current = permissions.setdefault(kind, [])
        current += [rule for rule in rules if rule not in current]


def _seed(
    source: Path,
    target: Path,
    packs: list[str],
    settings: str | None,
    report: Report,
    dry_run: bool,
) -> None:
    seeds = dict(SEEDS)
    for pack in packs:
        seeds.update(PACK_SEEDS.get(pack, {}))
    for rel, seed in seeds.items():
        destination = target / rel
        if destination.exists():
            if rel == SETTINGS and settings is not None:
                report.merge_by_hand += _unmerged(destination, source, packs)
            continue
        report.seeded.append(rel)
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if seed is None:
            destination.touch()
        elif rel == SETTINGS and settings is not None:
            destination.write_text(settings, encoding="utf-8")
        else:
            shutil.copyfile(source / seed, destination)


def _unmerged(existing: Path, source: Path, packs: list[str]) -> list[str]:
    """The packs' settings additions that settings a project already has lack."""
    try:
        current = json.loads(existing.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = {}
    lacking = []
    for pack in packs:
        rel = PACK_SETTINGS.get(pack)
        if rel is None:
            continue
        wanted = json.loads((source / rel).read_text(encoding="utf-8"))
        env = current.get("env", {}) if isinstance(current, dict) else {}
        permissions = current.get("permissions", {}) if isinstance(current, dict) else {}
        if any(env.get(k) != v for k, v in wanted.get("env", {}).items()) or any(
            rule not in permissions.get(kind, [])
            for kind, rules in wanted.get("permissions", {}).items()
            for rule in rules
        ):
            lacking.append(rel)
    return lacking


def _copy(origin: Path, destination: Path, dry_run: bool) -> None:
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origin, destination)


# -- command line ------------------------------------------------------------


def register(sub: argparse._SubParsersAction) -> None:
    install_cmd = sub.add_parser("install", help="copy the method into another project")
    install_cmd.add_argument("target", type=Path)
    install_cmd.add_argument(
        "--packs", default="", help=f"comma-separated extra packs: {', '.join(PACKS[1:])}"
    )
    install_cmd.add_argument("--dry-run", action="store_true")
    install_cmd.set_defaults(handler=_install)

    update_cmd = sub.add_parser(
        "update", help="bring a project's copy of the method up to this one"
    )
    update_cmd.add_argument("target", type=Path)
    update_cmd.add_argument("--dry-run", action="store_true")
    update_cmd.set_defaults(handler=_update)

    manifest_cmd = sub.add_parser(
        "manifest", help="regenerate, or --check, the shipped-files manifest"
    )
    manifest_cmd.add_argument("--check", action="store_true")
    manifest_cmd.set_defaults(handler=_manifest)


def _source_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _install(root: Path, args: argparse.Namespace) -> int:
    packs = [p.strip() for p in args.packs.split(",") if p.strip()]
    try:
        report = install(_source_root(), args.target.resolve(), packs, args.dry_run)
    except ValueError as exc:
        print(f"sdd install: {exc}")
        return 1
    print(report.describe())
    print("next: edit sdd.toml for this project's layout, then: bash .claude/sdd/sdd.sh check")
    return 0


def _update(root: Path, args: argparse.Namespace) -> int:
    try:
        report = update(_source_root(), args.target.resolve(), args.dry_run)
    except ValueError as exc:
        print(f"sdd update: {exc}")
        return 1
    print(report.describe())
    return 0


def _manifest(root: Path, args: argparse.Namespace) -> int:
    if args.check:
        problems = check_manifest(root)
        for problem in problems:
            print(f"sdd manifest: {problem}")
        if problems:
            print(
                "a shipped file changed: bump VERSION, add a CHANGELOG entry, then run: bash .claude/sdd/sdd.sh manifest"
            )
        return 1 if problems else 0
    manifest = build_manifest(root)
    write_manifest(root, manifest)
    print(f"wrote {MANIFEST}: {len(manifest['files'])} files, version {VERSION}")
    return 0

# distribution Specification

## Purpose

Lets the method travel to another project and take updates there, without ever overwriting a decision that project made.

## Requirements

### Requirement: DIST-INSTALL
Install SHALL copy the core and each requested pack, seed the project-owned files once, record a manifest, and never overwrite an existing file or write CLAUDE.md, pyproject.toml, .env, src or tests.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_distribution.py::TestInstallCopiesTheMethodAndSeedsOnce`

#### Scenario: A fresh project
| Given | Then |
|---|---|
| an empty project, packs `python` | core and python files, seeds, manifest packs `core, python`; no langgraph rules |
| a project with its own `guard-edits.sh` | left alone and reported |
| install run twice | the second run writes and seeds nothing |
| pack `rust` | refused |

#### Scenario: Counter-example -- project-owned files are never written
- **GIVEN** install with every pack
- **THEN** CLAUDE.md, pyproject.toml, .env, src and tests do not exist afterwards

### Requirement: DIST-UPDATE
Update SHALL replace a shipped file only if it is unchanged since install, remove a retired file only if unchanged, and report -- never merge, never overwrite -- a file the project modified or deleted.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_distribution.py::TestUpdateReplacesOnlyWhatTheProjectNeverTouched`

#### Scenario: Pristine, modified, retired
| Given | Then |
|---|---|
| upstream edit, file untouched locally | replaced |
| upstream edit, file edited locally | left alone, reported |
| retired upstream, untouched locally | removed |
| retired upstream, edited locally | left alone, reported |
| `--dry-run` | reported, nothing written |
| no manifest in the target | refused: install first |

#### Scenario: Counter-example -- deleted files and seeds stay as the project left them
| Given | Then |
|---|---|
| a shipped file the project deleted | not restored |
| an upstream change to the sdd.toml seed | the project's sdd.toml untouched |

### Requirement: DIST-PACK-SEEDS
Install SHALL seed a pack's own project-owned files only when that pack is installed, and SHALL merge the pack's settings additions into the settings it seeds. Settings a project already has SHALL be left alone, with the additions reported for a merge by hand. Update SHALL report a pack seed the project lacks, and write nothing.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_distribution.py::TestAPackSeedsItsOwnFiles`,
  `.claude/sdd/tests/test_distribution.py::TestALangGraphInstallIsLocalOnly`

#### Scenario: Seeded with the pack, and only with it
| Given | Then |
|---|---|
| an empty project, packs `langgraph` | `scripts/serve.sh` seeded; `.claude/settings.json` holds the core seed's hooks, permissions and env, plus the pack's deny rules and env |
| an empty project, packs `python` | no `scripts/serve.sh`; `.claude/settings.json` byte for byte the core seed |
| a project with its own `.claude/settings.json`, packs `langgraph` | its settings untouched; `seeds/settings.langgraph.json` reported for a merge by hand |
| the same, its settings malformed (`"env": []`) | the same: untouched and reported, never a crash |
| update of a langgraph project without `scripts/serve.sh` | reported as not seeded; nothing written |

#### Scenario: Counter-example -- a merge never drops or overrides a key silently
| Given | Then |
|---|---|
| additions with a top-level `hooks` key | install refused before anything is written, naming the key |
| additions whose `env` gives `OPENSPEC_TELEMETRY` another value | install refused, naming the variable |
| install run twice, packs `langgraph` | nothing reported to merge the second time: the settings already hold the additions |

### Requirement: DIST-MANIFEST
`manifest --check` SHALL fail when a shipped file changed, appeared or disappeared since the manifest was generated, and install and update SHALL refuse a source whose manifest is stale.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_distribution.py::TestTheManifestMovesWithWhatShips`

#### Scenario: A silent change to a shipped file
- **GIVEN** an edit to `.claude/skills/intake/SKILL.md` without regenerating the manifest
- **THEN** the check names it, and install copies nothing

#### Scenario: Counter-example -- project files are not the method
| Given | Then |
|---|---|
| `.claude/rules/project/lessons.md`, `.claude/skills/deploy/SKILL.md` | in no pack |
| `discover/references/orchestration-ladder.md`, `accept/references/graph-routes.md` | the langgraph pack, inside a core skill |

### Requirement: DIST-ONE-VERSION
The pinned OpenSpec release SHALL be stated in sdd.sh and the library alike, and the changelog SHALL have a `## <version>` heading for the current method version.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_distribution.py::TestOneVersionOfEachFact`

#### Scenario: Versions agree
- **GIVEN** `OPENSPEC_VERSION="1.14.0"` in sdd.sh
- **THEN** the library's OPENSPEC_VERSION is 1.14.0, and CHANGELOG.md has `## <VERSION>`

#### Scenario: Counter-example -- a version mentioned in prose is not an entry
| Given | Then |
|---|---|
| `## 0.1.0` then "See 0.2.0 for what comes next." | no entry for 0.2.0 |
| `## 0.2.0 -- 2026-10-04` | an entry for 0.2.0 |

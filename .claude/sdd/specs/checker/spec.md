# checker Specification

## Purpose

Keeps the proof checker itself honest: stable ids, deltas that archive cleanly, an adapter that refuses what it does not understand, and an output every consumer reads the same way.

## Requirements

### Requirement: CHECKER-STABLE-IDS
A requirement heading SHALL be an upper-kebab id of at least two segments, unique across every living capability, and a change SHALL NOT add an id the living spec already holds.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestIdsAreStableAndUnique`

#### Scenario: Duplicates and sentences
| Given | Then |
|---|---|
| `SHARED-ID` in two living capabilities | SDD010 |
| a change ADDING `SHARED-ID` | SDD010, fix: MODIFIED |
| `### Requirement: User can export data` | SDD011 |

#### Scenario: Counter-example -- a MODIFIED delta repeats the id on purpose
- **GIVEN** a change MODIFYING a living requirement with the same id
- **THEN** no SDD010

### Requirement: CHECKER-DELTA-STRUCTURE
A change SHALL only MODIFY or REMOVE requirements that exist in the living spec of the same capability, and every requirement in a change SHALL sit under a delta section.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestDeltasArchiveCleanly`

#### Scenario: An imagined target and a stray requirement
| Given | Then |
|---|---|
| MODIFIED `CAP-IMAGINED`, absent from the living spec | SDD013 |
| a requirement under `## Notes` in a delta | SDD013, archive would drop it |

#### Scenario: Counter-example -- the archive is history
- **GIVEN** a broken requirement inside `changes/archive/`
- **THEN** it is never checked, and is not counted as in flight

### Requirement: CHECKER-ADAPTER-STRICT
The checker SHALL refuse an adapter with an unknown key, a configured directory that does not exist, a `[guards]` array split across lines, or a symbol regex without a capture group.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestAdapterIsStrict`

#### Scenario: Four refusals
| Given | Then |
|---|---|
| `livng_typo = ...` | SDD000, naming the key |
| `living = "docs/specs-moved-away"`, absent | SDD000, naming the path |
| `ground_truth = [` on its own line | refused: the bash guard reads one line |
| `symbols = "regex:it\\("` | refused: no group |

#### Scenario: Counter-example -- a minimal adapter takes the defaults
- **GIVEN** only `[specs] living` and `[tests] roots, patterns`
- **THEN** symbols is `python`, changes is unset, exempt is empty

### Requirement: CHECKER-HONEST-EMPTY
A project with no requirements and no test files SHALL pass with an info line saying nothing is specified yet -- neither an error nor a silent pass.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestNothingPassesVacuously`

#### Scenario: The day-one project
- **GIVEN** empty `openspec/specs`, an empty archive, and only exempt tests
- **THEN** exit 0 and exactly SDD100

#### Scenario: Counter-example -- a test file makes the project not empty
- **GIVEN** the same project plus one unclaimed test file
- **THEN** SDD006 instead of SDD100

### Requirement: CHECKER-PARSER
The parser SHALL read fields only between a requirement heading and its first scenario, SHALL join indented continuation lines, and SHALL ignore fenced code and HTML comments.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestTheParserReadsOnlyWhatIsReal`

#### Scenario: What is read
| Given | Then |
|---|---|
| `Proved by:` continued on an indented line | both references, joined |
| `- **Owner:** <!-- note --> ada` | `ada` |
| a requirement inside a fenced block or a comment | not a requirement |

#### Scenario: Counter-example -- a bullet inside a scenario is not a field
- **GIVEN** `- **Kind:** evaluated` written under a scenario
- **THEN** the requirement's kind stays `deterministic`

### Requirement: CHECKER-ENVELOPE
`sdd check` SHALL exit 1 when any error is found and 0 otherwise, and `--json` SHALL print every finding as severity, code, message, target and fix.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestTheCommandLine`

#### Scenario: Errors and a clean project
| Given | Then |
|---|---|
| a requirement with no counter-example, `--json` | exit 1, the envelope's five keys |
| the valid project | exit 0, "sdd check: OK" |

#### Scenario: Counter-example -- warnings alone do not fail the build
- **GIVEN** only an overdue review date
- **THEN** exit 0, with SDD009 printed

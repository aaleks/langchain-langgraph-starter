# traceability Specification

## Purpose

Holds every requirement to the test that proves it and every test to the requirement it proves, in both directions, so a spec can never describe a system nobody checks.

## Requirements

### Requirement: TRACE-KIND
The checker SHALL refuse any requirement that does not declare its Kind as exactly `deterministic` or `evaluated`.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestKindIsDeclared`

#### Scenario: A missing kind and a misspelled kind
| Given | Then |
|---|---|
| no `- **Kind:**` line | SDD001 |
| `- **Kind:** determinstic` | SDD001, naming the value |

#### Scenario: Counter-example -- either kind passes this rule
- **GIVEN** `- **Kind:** evaluated` with its threshold, N and agreement
- **THEN** no SDD001 is raised

### Requirement: TRACE-PROOF-NAMED
The checker SHALL refuse a deterministic requirement, or an evaluated one whose threshold was agreed, that names no test in backticks -- unless it is marked NOT MET.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestProofIsNamed`

#### Scenario: Silence, prose and an unmeasured agreed threshold
| Given | Then |
|---|---|
| no Proved by line | SDD002 |
| `Proved by: the template construction itself` | SDD002, saying the line holds prose |
| evaluated, `Threshold: 0.9`, no Proved by | SDD002 |

#### Scenario: Counter-example -- NOT MET is the one honest exemption
- **GIVEN** `- **Status:** NOT MET` with an Owner and a Review by
- **THEN** no SDD002 is raised

### Requirement: TRACE-PROOF-RESOLVES
Every test a requirement names SHALL be a file under the configured test roots that matches a test pattern, exists, and defines every `::Name` the reference gives.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestNamedTestsExist`

#### Scenario: Missing, renamed, and not a test
| Given | Then |
|---|---|
| the living spec names `tests/test_moved.py`, which is gone | SDD003, "named by the living spec" |
| a change names `tests/test_new.py`, not written yet | SDD003, "named by change", expected mid-loop |
| `tests/test_cap.py::TestOldName`, the class renamed | SDD004 |
| `src/app/cap.py` named as its own proof | SDD003, "not a test file" |

#### Scenario: Counter-example -- a file-level reference is enough
- **GIVEN** `Proved by: tests/test_cap.py` with no `::Name`
- **THEN** the reference resolves once the file exists

### Requirement: TRACE-EVALUATED-THRESHOLD
An evaluated requirement SHALL carry a Threshold that is a number or OPEN, an N that is a whole number or OPEN, and an Agreed by; an N below 20 SHALL be warned about, not refused.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestEvaluatedCarriesThresholdAndN`

#### Scenario: Silence and vagueness
| Given | Then |
|---|---|
| none of the three fields | SDD005 |
| `Threshold: good enough`, `N: some` | SDD005, neither a number nor OPEN |
| `N: 5` with a numeric threshold | SDD012 warning; the build passes |

#### Scenario: Counter-example -- OPEN with an owner and a date is legal
- **GIVEN** Threshold OPEN, N 20, Agreed by OPEN, an Owner and a future Review by
- **THEN** no error and no warning

### Requirement: TRACE-TESTS-CLAIMED
Every file under the test roots that matches a test pattern, outside the exempt globs, SHALL be named by at least one living or in-flight requirement.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestEveryTestFileIsClaimed`

#### Scenario: The orphan is named
- **GIVEN** `tests/test_orphan.py`, which no requirement names
- **THEN** SDD006 on that file, and on no other

#### Scenario: Counter-example -- in-flight claims count and exempt roots are skipped
- **GIVEN** a test claimed only by an in-flight change, and `tests/architecture/test_layers.py` under an exempt glob
- **THEN** neither is reported

### Requirement: TRACE-COUNTER-EXAMPLE
Every requirement SHALL have at least one scenario whose title begins with "Counter-example", in any capitalisation, hyphenated or not, singular or plural.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestCounterExampleIsPresent`

#### Scenario: Only happy paths, or no scenarios
| Given | Then |
|---|---|
| two positive scenarios | SDD007 |
| no scenario at all | SDD007, "no scenarios at all" |

#### Scenario: Counter-example -- the word mid-title does not count
- **GIVEN** a scenario titled "A counter-example in the middle does not count"
- **THEN** the requirement still has no counter-example

### Requirement: TRACE-EXCEPTION-OWNED
A requirement marked NOT MET, or with any field OPEN, SHALL carry an Owner and a Review by date in YYYY-MM-DD; a date before today SHALL raise a warning.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_check.py::TestExceptionsHaveOwners`

#### Scenario: Unowned, undated, overdue
| Given | Then |
|---|---|
| NOT MET, no Owner, no Review by | SDD008 |
| OPEN threshold, `Review by: next spring` | SDD008, not a date |
| NOT MET, Review by 2026-10-03, today 2026-10-04 | SDD009 warning |

#### Scenario: Counter-example -- due today is not overdue
- **GIVEN** Review by 2026-10-04 and today 2026-10-04
- **THEN** no diagnostic at all

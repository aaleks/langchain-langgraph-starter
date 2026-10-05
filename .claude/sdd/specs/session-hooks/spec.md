# session-hooks Specification

## Purpose

Keeps a session honest about where its work stands: drift is reported to the user at the end of a turn, and a new session starts knowing which stage each change is at.

## Requirements

### Requirement: HOOKS-STOP-DRIFT
When a turn ends with the working tree changed and `sdd check` failing, the Stop hook SHALL report the drift to the user as a systemMessage, and SHALL never block or force another turn.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestTheStopHookReportsDriftToTheUser`

#### Scenario: Drift after a turn
- **GIVEN** an unclaimed test file added during the turn
- **THEN** exit 0 and a systemMessage containing "SDD drift" and SDD006

#### Scenario: Counter-example -- silence when nothing is wrong
| Given | Then |
|---|---|
| a turn that changed nothing | no output |
| a turn whose changes still agree | no output |

### Requirement: HOOKS-SESSION-STATUS
At session start, the hook SHALL print one line per in-flight change, with its class and its next stage, and nothing when no change is in flight.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestTheSessionHookSaysWhereChangesStand`

#### Scenario: A change in flight
- **GIVEN** `openspec/changes/add-routing/intake.md` with class bounded
- **THEN** a line containing `add-routing [bounded]` and `next: frame`

#### Scenario: Counter-example -- nothing in flight
- **GIVEN** only the archive
- **THEN** no output at all

### Requirement: HOOKS-NEXT-STAGE
The next stage of a change SHALL be the earliest one its class requires that has not happened: design only for structural changes, specs only when the change does not declare `skip_specs: true` in its `.openspec.yaml`, apply until every task is checked, verify until the verdict is SHIP, and a spike is done once its verdict is recorded.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_status.py::TestResumeAtTheEarliestIncompleteStage`

#### Scenario: Next stages
| Given | Then |
|---|---|
| bounded, frame and specs, 1 of 2 tasks checked | `apply (1/2 tasks done)` |
| structural, frame and specs, no design | `design` |
| structural, frame, `skip_specs: true`, no specs, no design | `design`, and the line marks `specs~` |
| all tasks checked, verdict SHIP | `land` |
| all tasks checked, verdict DO NOT SHIP | `verify (verdict is not SHIP)` |
| spike with verdict kill | done |

#### Scenario: Counter-example -- an archived change is not in flight
- **GIVEN** a directory under `changes/archive/`
- **THEN** it is not reported

#### Scenario: Counter-example -- without the declaration, a missing spec is a missing stage
| Given | Then |
|---|---|
| bounded, frame, no specs, `.openspec.yaml` without `skip_specs` | `specs` |
| bounded, frame, no specs, `skip_specs: false` | `specs` |

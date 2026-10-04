# method-health Specification

## Purpose

Measures whether the method is working from the files it already keeps, so a method change is argued from evidence rather than anecdote.

## Requirements

### Requirement: HEALTH-FROM-FILES
`sdd stats` SHALL report the deterministic share of living requirements, the MODIFIED and REMOVED deltas archived, defects by whether they amended or added a requirement, and the stages each intake class skipped -- and SHALL report what files cannot give as not collected.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_distribution.py::TestMethodHealthIsReadFromFiles`

#### Scenario: Two archived changes
| Given | Then |
|---|---|
| a defect with a MODIFIED delta and every artifact but design | defects: modified an existing requirement, 1 |
| a bounded change with frame, specs and tasks | bounded: 1 change, skipped design 1, skipped verify 1 |
| two MODIFIED deltas in all | amended after implementation: 2 |

#### Scenario: Counter-example -- cycles per requirement are not estimated
- **GIVEN** any project
- **THEN** cycles per requirement reads "not collected"

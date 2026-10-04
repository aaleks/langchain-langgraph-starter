<!-- One file per capability: specs/<capability>/spec.md.
     A NEW capability opens with ## Purpose. An existing one has no Purpose
     section -- only the delta sections it uses. Delete unused sections. -->

## Purpose

<!-- New capability only: what it is for, one or two sentences, 50+ characters. -->

## ADDED Requirements

### Requirement: <CAPABILITY>-<RULE>
<!-- One behaviour as an invariant, with SHALL or MUST -- something that can be
     false. 500 characters at most. -->

- **Kind:** <!-- deterministic | evaluated -->
- **Proved by:** <!-- `tests/<tier>/test_<x>.py::<Class>` -- named now; /accept writes it -->

#### Scenario: <the normal case>
- **GIVEN** <!-- real values, never placeholders -->
- **WHEN** <!-- optional when the requirement already names the action -->
- **THEN** <!-- the exact observable outcome -->

#### Scenario: Counter-example -- <where the rule deliberately does not apply>
- **GIVEN**
- **THEN**

<!-- Several rows of one case read better as a table inside one scenario:
| Given | Then |
|---|---|
| ... | ... |

An evaluated requirement carries, instead of a bare Proved by:
- **Threshold:** <number, or OPEN>
- **N:** <cases the score is computed over, or OPEN>
- **Agreed by:** <who, or OPEN>
- **Proved by:** `<the live check>` -- once the threshold is agreed

Anything OPEN, or - **Status:** NOT MET, also carries:
- **Owner:** <name>
- **Review by:** YYYY-MM-DD -->

## MODIFIED Requirements

<!-- Copy the WHOLE existing block from openspec/specs/<capability>/spec.md,
     then edit it. A partial block loses detail at archive. -->

## REMOVED Requirements

<!-- ### Requirement: <ID>
     **Reason**: why it no longer holds
     **Migration**: what replaces it, and what happens to its test -->

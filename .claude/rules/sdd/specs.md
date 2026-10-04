---
paths:
  - "openspec/**/*.md"
---

# Writing a requirement

The checker reads these files and the build fails on a sloppy edit, so the
shape below is not a style preference.

A requirement is a stable id, one falsifiable statement, its kind, its proof,
and scenarios with real values -- one of them a counter-example:

```markdown
### Requirement: PROVIDER-PRECEDENCE
The system SHALL choose the provider by explicit override, then the environment,
then the built-in default.

- **Kind:** deterministic
- **Proved by:** `tests/unit/test_providers.py::TestProviderPrecedence`

#### Scenario: Override beats the environment
| Given | Then |
|---|---|
| environment `ollama`, override `openai` | `openai` |
| nothing set | `ollama` |

#### Scenario: Counter-example -- an unknown name is refused, not defaulted
- **GIVEN** the override `claude-x`
- **THEN** the call is rejected, listing the valid names
```

- **The id** is `<CAPABILITY>-<RULE>` in upper kebab and never changes: tests
  and reviews cite it. The sentence below it can be reworded freely.
- **The statement** is an invariant with SHALL or MUST -- it can be false. "The
  provider is resolved" cannot; the statement above can.
- **Evaluated** requirements carry `Threshold`, `N` and `Agreed by` instead of a
  bare `Proved by`; OPEN is legal, silence is not, and a number is never invented.
- **Anything OPEN or NOT MET** carries `Owner` and `Review by: YYYY-MM-DD`.
- **Scenarios** use real values. The counter-example is the case where the rule
  deliberately does not apply -- on a threshold rule, the off-by-one.
- A capability with established tooling has an **Existing options considered**
  decision in its change's `frame.md`.

**Changes write deltas; `openspec/specs/` is written by archive.** A wrong
requirement is amended by a MODIFIED delta -- the whole block copied, then
edited -- or a REMOVED one with Reason and Migration. When the code and a
requirement disagree, the disagreement is the finding: say which you think is
wrong and why, and let the user decide.

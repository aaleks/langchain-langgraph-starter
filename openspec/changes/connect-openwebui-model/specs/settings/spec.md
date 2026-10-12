## Purpose

Settings are how the owner configures the assistant without touching code: read by `config/` from the process environment and from `.env`, the environment always winning, and handed inward as plain values.

## ADDED Requirements

### Requirement: SETTINGS-ENVIRONMENT-WINS
A setting SHALL be read from the process environment when the environment holds it -- an empty value included -- and from `.env` only when the environment does not. A missing `.env` SHALL read as empty, and reading SHALL change neither the environment nor the file.

- **Kind:** deterministic
- **Proved by:** `tests/integration/config/test_settings.py::TestEnvironmentWins`

#### Scenario: The environment, then .env
| Environment | `.env` | `OPENWEBUI_MODEL` read |
|---|---|---|
| `OPENWEBUI_MODEL=qwen3:8b` | `OPENWEBUI_MODEL=llama3.1:8b` | `qwen3:8b` |
| not set | `OPENWEBUI_MODEL=llama3.1:8b` | `llama3.1:8b` |
| `OPENWEBUI_MODEL=` (empty) | `OPENWEBUI_MODEL=llama3.1:8b` | empty |

#### Scenario: No .env at all
- **GIVEN** no `.env` file and an environment holding none of the settings
- **THEN** every setting reads as empty, and no error is raised

#### Scenario: Counter-example -- reading leaves the process environment as it was
- **GIVEN** a `.env` holding `OPENWEBUI_URL=http://localhost:3000` and an environment without it
- **WHEN** the settings are read
- **THEN** `OPENWEBUI_URL` reads as `http://localhost:3000`, and the process environment still does not hold it

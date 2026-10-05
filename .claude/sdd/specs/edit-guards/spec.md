# edit-guards Specification

## Purpose

Refuses, at the moment of writing, the edits that are cheap to catch then and expensive to discover later -- and says why. A habit guard on the Edit and Write tools, not a security boundary.

## Requirements

### Requirement: GUARD-SECRETS
The edit guard SHALL refuse an agent's write to `.env`, any `.env.*` file, and `*.pem` or `*.key` files, wherever they sit.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestSecretsAreWrittenByAHumanOnly`

#### Scenario: Credentials anywhere
| Given | Then |
|---|---|
| `.env`, `.env.local`, `deploy/.env.production` | exit 2, "credentials" |
| `certs/server.pem` | exit 2 |

#### Scenario: Counter-example -- the committed example file is editable
- **GIVEN** a write to `.env.example`
- **THEN** allowed, with no output

### Requirement: GUARD-GROUND-TRUTH
The edit guard SHALL refuse writes to evaluation ground truth: the globs in `sdd.toml` `[guards] ground_truth`, or `tests/evals/golden/*` when none are configured.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestGroundTruthIsWrittenByAHumanOnly`,
  `.claude/sdd/tests/test_hooks.py::TestGroundTruthGlobsComeFromTheAdapter`

#### Scenario: Default and configured
| Given | Then |
|---|---|
| no `[guards]`, `tests/evals/golden/answers.jsonl` | exit 2, "ground truth" |
| `ground_truth = ["data/labelled/*"]`, `data/labelled/set.jsonl` | exit 2 |

#### Scenario: Counter-example -- configured globs replace the default
- **GIVEN** `ground_truth = ["data/labelled/*"]` and a write to `tests/evals/golden/answers.jsonl`
- **THEN** allowed

### Requirement: GUARD-GENERATED-AND-CI
The edit guard SHALL refuse writes to lockfiles a tool generates and to `.github/workflows/`, where enforcement is decided.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestGeneratedFilesAndCiAreRefused`

#### Scenario: Generated and enforcement files
| Given | Then |
|---|---|
| `uv.lock`, `web/package-lock.json` | exit 2, "generated" |
| `.github/workflows/checks.yml` | exit 2, "CI" |

#### Scenario: Counter-example -- the manifest and the CI proposal are editable
- **GIVEN** a write to `pyproject.toml`, or to `docs/ci/ci.yml`
- **THEN** allowed

### Requirement: GUARD-RUNTIME-DATA
The edit guard SHALL refuse an agent's write to the LangGraph server's local state, `.langgraph_api/`, and to data stores -- `*.sqlite`, `*.sqlite3`, `*.db` -- wherever they sit. A server or a checkpointer writes them; a hand-edited store corrupts the threads in it.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestRuntimeDataIsWrittenByTheRuntimeOnly`

#### Scenario: Data a runtime writes
| Given | Then |
|---|---|
| `.langgraph_api/.langgraph_checkpoint.1.pckl` | exit 2, "runtime" |
| `checkpoints.sqlite`, `data/threads.db`, `var/store.sqlite3` | exit 2, "store" |

#### Scenario: Counter-example -- names that only resemble one
| Given | Then |
|---|---|
| `docs/database.md`, `src/app/infrastructure/agents/checkpointers.py` | allowed, with no output |

### Requirement: GUARD-SERVER-CONFIG
The edit guard SHALL refuse new text in `langgraph.json` that sets an `env` key, which the server would load over the local-only environment. It SHALL judge only the text being written, never the text being replaced.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestTheServerConfigCarriesNoEnvironment`

#### Scenario: An env key written
| Given | Then |
|---|---|
| `{"graphs": {"chat": "./x.py:chat"}, "env": ".env"}` written to `langgraph.json` | exit 2, "env" |
| `"env": {"OPENAI_API_KEY": "sk-1"}` added to `deploy/langgraph.json` | exit 2 |

#### Scenario: Counter-example -- removing it, and other files
| Given | Then |
|---|---|
| an edit whose old text holds `"env": ".env",` and whose new text is empty | allowed |
| `{"graphs": {"chat": "./x.py:chat"}}` written to `langgraph.json` | allowed, with no output |
| `{"env": ".env"}` written to `config/server.json` | allowed |

### Requirement: GUARD-DOMAIN-IMPORTS
The edit guard SHALL refuse new text that imports a common SDK into `src/*/domain/`, judging only the text being written -- never the text being replaced.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestDomainImportsAreRefusedAtWriteTime`

#### Scenario: An SDK into the decision layer
- **GIVEN** `from langgraph.graph import StateGraph` written to `src/app/domain/routing.py`
- **THEN** exit 2, "standard library only"

#### Scenario: Counter-example -- removing the import, stdlib, and other layers
| Given | Then |
|---|---|
| an edit whose old text holds `import langchain` and new text is empty | allowed |
| `import re` in the domain | allowed |
| `from langgraph.graph import StateGraph` in `infrastructure/agents/` | allowed |

### Requirement: GUARD-ASK
The edit guard SHALL ask the user before a write to the living spec, `openspec/specs/`, or to the method's enforcement: settings, hooks, the checker, its tests and fixtures, the seeds, the schema, `scripts/check.sh` and `scripts/serve.sh`.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestTheLivingSpecAndTheEnforcementAsk`

#### Scenario: The living spec and the enforcement
| Given | Then |
|---|---|
| `openspec/specs/routing/spec.md` | `ask`, "archive writes it" |
| `.claude/settings.json`, `.claude/hooks/guard-edits.sh`, `scripts/check.sh` | `ask` |
| `scripts/serve.sh`, `.claude/sdd/seeds/serve.sh`, `.claude/sdd/seeds/settings.langgraph.json` | `ask` -- the local-only runtime |

#### Scenario: Counter-example -- deltas, skills and other scripts are written freely
- **GIVEN** a write to `openspec/changes/add-x/specs/routing/spec.md`, `.claude/skills/intake/SKILL.md` or `scripts/release.sh`
- **THEN** allowed, with no output

### Requirement: GUARD-PROMPT-NOTE
A write that assigns a prompt or template constant in `src/*/application/` SHALL be allowed with context telling Claude that the dependent evaluated requirements need `/eval`.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestPromptEditsAreNoted`

#### Scenario: A prompt constant
- **GIVEN** `SYSTEM_PROMPT = "Answer."` written to `src/app/application/answer.py`
- **THEN** additionalContext mentioning `/eval`, and no permission decision

#### Scenario: Counter-example -- a use case without a prompt is silent
- **GIVEN** `def answer(model): return model`
- **THEN** allowed, with no output

### Requirement: GUARD-PATHS
The edit guard SHALL apply the same rules to a path given relative, absolute, with Windows separators, or with a differently cased drive letter.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_hooks.py::TestPathsAreNormalised`

#### Scenario: Shapes of one path
| Given | Then |
|---|---|
| root `C:\Users\dev\project`, file `c:\Users\dev\project\.env` | exit 2 |
| relative `tests/evals/golden/a.jsonl` | exit 2 |

#### Scenario: Counter-example -- no path at all
- **GIVEN** a payload without `file_path` or `notebook_path`
- **THEN** allowed

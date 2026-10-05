# local-runtime Specification

## Purpose

Runs LangGraph on the developer's machine only. The development server, and every command the agent runs, start from an environment in which nothing reaches LangSmith, and the server listens on loopback alone. The langgraph pack's runtime guarantee; the measurements behind it are in the project's ADR on running LangGraph locally.

## Requirements

### Requirement: LOCAL-SERVE-LOOPBACK
`scripts/serve.sh` SHALL start the LangGraph development server bound to 127.0.0.1, without opening a browser. It SHALL pass on only the flags in its allowlist, refusing `--host`, `--tunnel`, `--studio-url` and any other flag before the server starts.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_serve.py::TestTheServerListensOnLoopbackOnly`

#### Scenario: What the server is started with
| Given | Then |
|---|---|
| no arguments | `uv run langgraph dev --config langgraph.json --host 127.0.0.1 --port 2024 --no-browser` |
| `--port 8123 --no-reload` | `--port 8123`, and `--no-reload` passed on |
| `--port=9000` | `--port 9000` |

#### Scenario: Refused before the server starts
| Given | Then |
|---|---|
| `--tunnel` | exit 2, `--tunnel` named, the server never started |
| `--studio-url https://smith.langchain.com` | exit 2, `--studio-url` named |
| `--host 0.0.0.0`, `--host=0.0.0.0` | exit 2, `--host` named |
| `--port` with no value | exit 2 |

#### Scenario: Counter-example -- the allowlisted flags pass on unchanged
- **GIVEN** `--allow-blocking --server-log-level DEBUG --n-jobs-per-worker 2`
- **THEN** each is passed on, in order, after the fixed flags

### Requirement: LOCAL-SERVE-ENVIRONMENT
`scripts/serve.sh` SHALL start the server from the local-only environment, whatever the calling shell exports. That environment is:

- the four tracing switches -- `LANGSMITH_TRACING`, `LANGSMITH_TRACING_V2`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_TRACING` -- set to `false`;
- the four credentials -- `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, `LANGSMITH_CONTROL_PLANE_API_KEY`, `LANGGRAPH_CLOUD_LICENSE_KEY` -- present and empty;
- `LANGSMITH_ENDPOINT` and `LANGCHAIN_ENDPOINT` set to `http://127.0.0.1:9`;
- `LANGGRAPH_CLI_NO_ANALYTICS=1` and `LANGGRAPH_NO_VERSION_CHECK=true`.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_serve.py::TestTheServerStartsFromTheLocalOnlyEnvironment`

#### Scenario: A shell that exports LangSmith
- **GIVEN** the shell exports `LANGSMITH_API_KEY=lsv2_from_shell`, `LANGGRAPH_CLOUD_LICENSE_KEY=lcl_from_shell`, `LANGCHAIN_TRACING_V2=true` and `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`
- **THEN** the server sees the twelve variables exactly as listed, credentials present and empty

#### Scenario: Counter-example -- the rest of the environment passes through
- **GIVEN** the shell exports `GOOGLE_API_KEY=g-123`
- **THEN** the server sees `GOOGLE_API_KEY=g-123`

### Requirement: LOCAL-SERVE-REFUSALS
`scripts/serve.sh` SHALL refuse to start the server when there is no `langgraph.json`, when `langgraph.json` has an `env` key, or when `.env` sets a LangSmith credential to a value or switches tracing on. It SHALL name the variable and never print its value.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_serve.py::TestTheServerRefusesWhatWouldUndoIt`

#### Scenario: Refused
| Given | Then |
|---|---|
| no `langgraph.json` | exit 2, `langgraph.json` named |
| `langgraph.json` with `"env": ".env"` | exit 2, `env` named |
| `langgraph.json` with `"env": {"OPENAI_API_KEY": "sk-1"}` | exit 2, `sk-1` never printed |
| `.env` with `LANGSMITH_API_KEY=lsv2_secret_value` | exit 2, `LANGSMITH_API_KEY` named, `lsv2_secret_value` never printed |
| `.env` with `export LANGCHAIN_TRACING_V2="true"` | exit 2, `LANGCHAIN_TRACING_V2` named |
| `.env` with `LANGSMITH_TRACING=tRuE` -- the server reads it lower-cased | exit 2, `LANGSMITH_TRACING` named |
| `.env` with `LANGGRAPH_CLOUD_LICENSE_KEY='lcl_abc'` | exit 2, `LANGGRAPH_CLOUD_LICENSE_KEY` named |

#### Scenario: Counter-example -- what .env may hold
- **GIVEN** `.env` with `# LANGSMITH_API_KEY=lsv2_old`, `LANGSMITH_API_KEY=`, `LANGSMITH_TRACING=false` and `GOOGLE_API_KEY=g-123`
- **THEN** the server starts

### Requirement: LOCAL-AGENT-SETTINGS
The langgraph pack's settings additions SHALL give the agent the same local-only environment that `scripts/serve.sh` gives the server. They SHALL deny every Bash command:

- containing `smith.langchain.com`, `--studio-url` or `--tunnel`, under any spelling of any launcher;
- running `langgraph deploy` or `langgraph up`, which need LangSmith;
- starting the development server any way but `scripts/serve.sh`: `langgraph dev`, `langgraph_cli dev`, `langgraph-cli dev` or `langgraph_api.cli`.

- **Kind:** deterministic
- **Proved by:** `.claude/sdd/tests/test_serve.py::TestTheAgentWorksInTheSameEnvironment`

#### Scenario: Denied, as Claude Code matches a Bash rule -- `*` stands for any text
| Given | Then |
|---|---|
| `uv run langgraph dev --no-browser` | denied |
| `uv run python -m langgraph_cli dev` | denied |
| `npx @langchain/langgraph-cli dev` | denied |
| `uv run python -m langgraph_api.cli --open-browser` | denied |
| `langgraph up --wait` | denied |
| `uvx --from langgraph-cli langgraph deploy` | denied |
| `curl https://api.smith.langchain.com/info` | denied |
| `some-launcher serve --tunnel` | denied |
| `some-launcher serve --studio-url https://studio.example.org` | denied |

#### Scenario: One environment, in two places
- **GIVEN** the additions' `env`, and the environment `scripts/serve.sh` starts the server with
- **THEN** both are the twelve variables of LOCAL-SERVE-ENVIRONMENT, with the same values

#### Scenario: Counter-example -- local work is not denied
| Given | Then |
|---|---|
| `bash scripts/serve.sh --port 8123` | allowed |
| `uv run langgraph validate` | allowed |
| `uv run pytest -q` | allowed |

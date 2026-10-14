# tools Specification

## Purpose
Tools are what the assistant may do beyond answering. Each one arrives with a capability manifest saying what it reads, what it changes, how it fails and how it is bounded, and the factory refuses any tool whose manifest the assistant cannot honour yet.

## Requirements

### Requirement: TOOLS-MANIFEST
Every tool the factory is given SHALL carry a capability manifest -- the tool's name, its output's type, the errors it raises, whether it is idempotent, its timeout, its retry class, its rate limit and its side-effect level, and its audit event; its input's schema is the tool's own. The factory SHALL refuse, before compiling anything and naming the tool, a manifest the assistant cannot honour: none, or one that is not a manifest; one naming another tool; a side effect other than `read` -- no write has an approval route before slice 4; a retry class other than `none` -- a tool's failure propagates; a rate limit other than the run's `TOOL_CALLS_PER_RUN`, the one limit enforced. A tool declaring `read` SHALL be given only a view of its store that refuses a write.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_tool_manifests.py::TestToolManifests`

#### Scenario: The task tools' manifests
| Tool | Arguments | Side effect | Idempotent | Retry class | Rate limit | Errors | Audit event |
|---|---|---|---|---|---|---|---|
| `list_tasks` | none | `read` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | none |
| `search_tasks` | `query` | `read` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | none |

- **AND** each holds a view of the list and no store: the view has no method to add, its connection refuses an `INSERT`, `PRAGMA query_only = OFF` and an `ATTACH`, and its wait is its manifest's timeout
- **AND** the factory compiles a graph given both, offering the model exactly `list_tasks` and `search_tasks`

#### Scenario: Counter-example -- a tool the assistant cannot honour is refused
| The tool `add` given with | Refused, naming |
|---|---|
| no manifest | `add` |
| a dictionary in the manifest's place | `add` |
| a manifest naming `sum` | `add` and `sum` |
| a manifest declaring the side effect `write` | `add` and `write` |
| a manifest declaring the side effect `network` | `add` and `network` |
| a manifest declaring the retry class `transient` | `add` and `transient` |
| a manifest declaring the retry class `always` | `add` and `always` |
| a manifest declaring a rate limit of 5 calls a run | `add` and `5` |
| a manifest declaring a rate limit of 21 calls a run | `add` and `21` |
| a manifest declaring `read`, beside a second tool with none | the second tool |

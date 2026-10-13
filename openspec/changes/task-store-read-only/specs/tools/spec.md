## Purpose

Tools are what the assistant may do beyond answering. Each one arrives with a capability manifest saying what it reads, what it changes, how it fails and how it is bounded, and the factory refuses any tool whose manifest the assistant cannot honour yet.

## ADDED Requirements

### Requirement: TOOLS-MANIFEST
Every tool the factory is given SHALL carry a capability manifest -- the tool's name, its output's type, the errors it raises, whether it is idempotent, its timeout, its retry class, its rate limit, its side-effect level and its audit event; its input's schema is the tool's own. The factory SHALL refuse, before compiling anything and naming the tool, a tool without a manifest, a manifest naming another tool, and a manifest declaring a side effect other than `read`: no write has an approval route before slice 4.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_tool_manifests.py::TestToolManifests`

#### Scenario: The task tools' manifests
| Tool | Side effect | Idempotent | Retry class | Audit event |
|---|---|---|---|---|
| `list_tasks` | `read` | yes | `none` | none |
| `search_tasks` | `read` | yes | `none` | none |

- **AND** the factory compiles a graph given both, offering the model exactly `list_tasks` and `search_tasks`

#### Scenario: Counter-example -- a tool the assistant cannot honour is refused
| The tool `add` given with | Refused, naming |
|---|---|
| no manifest | `add` |
| a manifest naming `sum` | `add` and `sum` |
| a manifest declaring the side effect `write` | `add` and `write` |
| a manifest declaring `read`, beside a second tool with none | the second tool |

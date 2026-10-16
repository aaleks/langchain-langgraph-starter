# tools Specification

## Purpose
Tools are what the assistant may do beyond answering. Each one arrives with a capability manifest saying what it reads, what it changes, how it fails and how it is bounded, and the factory refuses any tool whose manifest the assistant cannot honour yet.

## Requirements

### Requirement: TOOLS-MANIFEST
Every tool the factory is given SHALL carry a capability manifest -- the tool's name, its output's type, the errors it raises, whether it is idempotent, its timeout, its retry class, its rate limit and its side-effect level, and its audit event; its input's schema is the tool's own. The factory SHALL refuse, before compiling anything and naming the tool, a manifest the assistant cannot honour: none, or one that is not a manifest; one naming another tool; a side effect other than `read` or `write`; a `write` that is not idempotent or names no audit event, or that arrives without the task list's writer or without a builder turning its arguments into a write -- each write runs only through the approval route (ASSISTANT-WRITE-APPROVAL), applied by that writer; a retry class other than `none` -- a tool's failure propagates; a rate limit other than the run's `TOOL_CALLS_PER_RUN`, the one limit enforced. A tool declaring `read` SHALL be given only a view of its store that refuses a write, never the store.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_tool_manifests.py::TestToolManifests`

#### Scenario: The task tools' manifests
| Tool | Arguments | Side effect | Idempotent | Retry class | Rate limit | Errors | Audit event |
|---|---|---|---|---|---|---|---|
| `list_tasks` | none | `read` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | none |
| `search_tasks` | `query` | `read` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | none |
| `add_task` | `title`, `assignee`, `notes` | `write` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | `task_writes` |
| `close_task` | `task_id` | `write` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | `task_writes` |
| `reassign_task` | `task_id`, `assignee` | `write` | yes | `none` | `TOOL_CALLS_PER_RUN` | `sqlite3.Error` | `task_writes` |

- **AND** each read holds a view of the list and no store: the view has no method to add, its connection refuses an `INSERT`, `PRAGMA query_only = OFF` and an `ATTACH`, and its wait is its manifest's timeout
- **AND** the factory compiles a graph given all five and the list's writer, offering the model exactly those five

#### Scenario: Counter-example -- a tool the assistant cannot honour is refused
| The tool `add` given with | Refused, naming |
|---|---|
| no manifest | `add` |
| a dictionary in the manifest's place | `add` |
| a manifest naming `sum` | `add` and `sum` |
| a manifest declaring the side effect `write`, no writer given | `add` and `writer` |
| a manifest declaring `write`, not idempotent, with a writer | `add` and `idempotent` |
| a manifest declaring `write`, no audit event, with a writer | `add` and `audit` |
| a manifest declaring `write`, with a writer, no builder in `metadata["write"]` | `add` and `builder` |
| a manifest declaring the side effect `network` | `add` and `network` |
| a manifest declaring the retry class `transient` | `add` and `transient` |
| a manifest declaring the retry class `always` | `add` and `always` |
| a manifest declaring a rate limit of 5 calls a run | `add` and `5` |
| a manifest declaring a rate limit of 21 calls a run | `add` and `21` |
| a manifest declaring `read`, beside a second tool with none | the second tool |
| `list_tasks` built over a reader waiting 1 s, its manifest saying 5 | `list_tasks` |

### Requirement: TOOLS-TASK-WRITES
The assistant SHALL offer the model three write tools, each with its input schema: `add_task(title: str, assignee: str = "", notes: str = "")`, `close_task(task_id: int)` and `reassign_task(task_id: int, assignee: str)`. Each SHALL be only a proposal: called directly, outside the approval route, it SHALL raise `RuntimeError` and write nothing.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_tool_manifests.py::TestTaskWriteTools`

#### Scenario: The schemas the model sees
| Tool | Required | Optional |
|---|---|---|
| `add_task` | `title` (string) | `assignee`, `notes` (strings, default empty) |
| `close_task` | `task_id` (integer) | none |
| `reassign_task` | `task_id` (integer), `assignee` (string) | none |

#### Scenario: Counter-example -- called directly, nothing written
- **WHEN** `add_task` is invoked directly with `{"title": "Renew passport"}`
- **THEN** it raises `RuntimeError`, and the list holds no task

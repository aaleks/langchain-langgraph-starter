## ADDED Requirements

### Requirement: ASSISTANT-TOOL-CALL-BUDGET
A run SHALL execute at most `TOOL_CALLS_PER_RUN` (20) tool calls: a turn whose proposed calls would take the run past it SHALL end the run with an error naming the run's limit, none of that turn's calls executed.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestToolCallBudget`

#### Scenario: Calls per run
| The model proposes | Executed | The run |
|---|---|---|
| 4 calls a turn, for 5 turns, then answers | 20 | completes |
| 3 calls a turn, for 7 turns | 18 -- the seventh turn's 3 not | raises, naming the run limit |

#### Scenario: Counter-example -- exactly the budget is not past it
- **GIVEN** a model proposing 20 calls in one turn, then answering
- **THEN** all 20 are executed and the run completes

## MODIFIED Requirements

### Requirement: ASSISTANT-MODEL-CALL-BUDGET
A run of the assistant SHALL make at most `MODEL_CALLS_PER_RUN` model turns, a domain budget equal to 10; each turn SHALL make at most `1 + MODEL_RETRIES` attempts (ASSISTANT-TRANSIENT-RETRY), its retries spending none of the budget. A model still proposing tool calls when the budget is spent SHALL end the run with `ModelCallLimitExceededError` -- never with a message that reads like an answer, and never at the step ceiling first under the ceiling the factory's graph runs with: `create_agent`'s 9,999 supersteps, where the budget needs 51 -- one more per turn since the tool-call budget's middleware (ASSISTANT-TOOL-CALL-BUDGET).

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestModelCallBudget`

#### Scenario: A model that never stops proposing tool calls
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on every call
- **WHEN** the assistant runs on the human message `keep adding`
- **THEN** the run raises `ModelCallLimitExceededError`, not `GraphRecursionError`
- **AND** the graph's step ceiling is 9,999, `MODEL_CALLS_PER_RUN` is 10, and the model was called exactly `MODEL_CALLS_PER_RUN` times and the tool as many

#### Scenario: A retried turn spends one unit of the budget
- **GIVEN** a scripted model whose every turn first times out, then proposes `add(a=1, b=1)`
- **WHEN** the assistant runs with the registry's retry policy on the human message `keep adding`
- **THEN** the run raises `ModelCallLimitExceededError` after 10 turns: 20 attempts, and the tool called 10 times

#### Scenario: Counter-example -- an answer on the last call within budget completes
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on calls 1 to 9 and answers on call 10
- **WHEN** the assistant runs on the human message `keep adding`
- **THEN** the run completes without an error, its last message is an ai message with no tool call
- **AND** the model was called exactly 10 times and the tool 9 times

#### Scenario: Counter-example -- a caller's step ceiling below 41 ends the run first
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on every call
- **WHEN** the assistant runs on the human message `keep adding` with `recursion_limit` 50, then again with 51
- **THEN** at 50 the run raises `GraphRecursionError`; at 51 it raises `ModelCallLimitExceededError` -- measured, with both budgets' middleware. The title's 41 was the measured value before the tool-call budget; it still holds as a bound, 51 now being the measured one

### Requirement: ASSISTANT-REGISTERED
`langgraph.json` SHALL register exactly one graph, under the id `assistant`, bound to the `assistant` export of `src/starter/infrastructure/agents/registry.py`. That export SHALL be the graph the factory compiles -- so it carries the budgets and the retry policy -- with the model the process's settings choose and the tools `list_tasks` and `search_tasks` over the task list they name, both read when it is loaded; with no model configured it SHALL complete runs with every outbound network connection refused.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`

#### Scenario: The graph the server would load
- **GIVEN** `langgraph.json` at the repository root
- **THEN** its graphs are exactly `{"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}`
- **AND** loading that path as a file and reading `assistant` from it gives a compiled graph, the only one the registry binds

#### Scenario: Compiled by the factory, budget included
- **GIVEN** the registered graph, and a graph the factory compiles from a scripted model and the two task tools
- **THEN** their nodes are the same, both budgets' middleware among them, and so are their step ceilings -- the retry policy wraps the model call and has no node of its own: its own scenario proves it

#### Scenario: The model the process's settings choose
- **WHEN** the graph is loaded through `langgraph.json`, the settings in the process's environment

| Settings | The registered graph's model |
|---|---|
| none of the Open WebUI settings | the offline model |
| `OPENWEBUI_URL` -- a stand-in on `127.0.0.1` -- `OPENWEBUI_API_KEY=sk-local`, `OPENWEBUI_MODEL=llama3.1:8b` | the Open WebUI client those settings describe: a run on `hello` reaches the stand-in once, at `/api/chat/completions` with the key |
| `OPENWEBUI_URL` and `OPENWEBUI_MODEL` only | none: refused at load, naming `OPENWEBUI_API_KEY` |
| `TASKS_DB` naming a task list at schema version 2 | none: refused at load, naming the file |

#### Scenario: A task the owner added, read through the registered graph
- **GIVEN** `TASKS_DB` naming a list to which `starter tasks add "Renew passport"` added task 1, and Open WebUI configured -- a stand-in on `127.0.0.1` that proposes `list_tasks`, then answers
- **WHEN** the graph is loaded through `langgraph.json` and runs on the human message `what is open?`
- **THEN** the transcript's message types are `human, ai, tool, ai`, and the tool message is `{"tasks": [{"id": 1, "title": "Renew passport", "assignee": "", "notes": ""}], "more": 0}`
- **AND** the stand-in received two requests, the second carrying that tool message

#### Scenario: Its retry policy is the domain's
- **GIVEN** Open WebUI configured, answering the first request with HTTP 503
- **WHEN** the registered graph runs on the human message `hello`
- **THEN** the request is retried once, and the run completes with the transcript `human, ai`
- **AND** answering it with HTTP 401 instead, the run raises the 401 after that one request, not retried

#### Scenario: An offline run of the registered graph
- **GIVEN** no Open WebUI configured, and a process in which every outbound socket connection is refused before the graph is loaded
- **WHEN** the graph is loaded through `langgraph.json` and runs on the human message `hello`
- **THEN** the run completes, and the transcript's message types are `human, ai` with no tool call
- **AND** no outbound connection was attempted

#### Scenario: A second turn follows the first
- **GIVEN** the registered graph, with no Open WebUI configured
- **WHEN** it runs on `hello`, then on that transcript followed by `hello again`
- **THEN** the second transcript's message types are `human, ai, human, ai`, and its two answers have different ids

#### Scenario: Counter-example -- the factory's graph offers a tool it is given; the registered graph offers none
- **GIVEN** a graph the factory compiles from a scripted model and the recording `add` tool
- **THEN** that graph offers the model exactly `add`, and the registered graph offers no `add` -- only `list_tasks` and `search_tasks`

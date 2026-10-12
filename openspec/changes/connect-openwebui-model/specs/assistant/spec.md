## ADDED Requirements

### Requirement: ASSISTANT-TRANSIENT-RETRY
A model failure that the domain classifies as transient -- a timeout, a failed connection, or HTTP 408, 429, 500, 502, 503 or 504 -- SHALL be retried, at most `MODEL_RETRIES` times (2); when the retries are spent the run SHALL end with that failure, never with a message that reads like an answer. Any other failure SHALL NOT be retried.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestTransientRetry`

#### Scenario: A transient failure, then an answer
- **GIVEN** a scripted model whose first call fails with a timeout, then answers
- **WHEN** the assistant runs on the human message `hello`
- **THEN** the run completes with the transcript `human, ai`, and the model was called 2 times

#### Scenario: Transient failures past the retries
- **GIVEN** a scripted model whose calls all fail with HTTP 503
- **WHEN** the assistant runs on the human message `hello`
- **THEN** the run raises that failure, and the model was called 3 times -- once, then `MODEL_RETRIES` retries

#### Scenario: Counter-example -- a failure that is not transient is not retried
| First call fails with | Model calls | The run |
|---|---|---|
| HTTP 401 | 1 | raises it |
| HTTP 400 | 1 | raises it |

## MODIFIED Requirements

### Requirement: ASSISTANT-ERRORS-PROPAGATE
An exception that a tool raises, or that the model raises and the retry policy does not classify as transient, SHALL end the run by propagating to the caller unchanged -- the unexpected class, never turned into a message the run carries on with.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestErrorsPropagate`

#### Scenario: A tool raises
- **GIVEN** a scripted model that proposes `explode(a=1)`, then answers, and a tool `explode` that raises `RuntimeError("explode failed")`
- **WHEN** the assistant runs on the human message `explode`
- **THEN** the run raises that `RuntimeError`, and the model was called once

#### Scenario: The model raises
- **GIVEN** a scripted model whose first call raises `RuntimeError("model broke")`, which is not transient
- **WHEN** the assistant runs on the human message `hello`
- **THEN** the run raises that `RuntimeError`, the model was called once, and no tool is called

#### Scenario: Counter-example -- a tool that returns an error text has not raised
- **GIVEN** a scripted model that proposes `explain(a=1)`, then answers, and a tool `explain` that returns `error: nothing to explain`
- **WHEN** the assistant runs on the human message `explain`
- **THEN** the run completes, and the tool message answering the call has status `success` and content `error: nothing to explain`

### Requirement: ASSISTANT-REGISTERED
`langgraph.json` SHALL register exactly one graph, under the id `assistant`, bound to the `assistant` export of `src/starter/infrastructure/agents/registry.py`. That export SHALL be the graph the factory compiles -- so it carries the budget and the retry policy -- with the model the settings choose and no tools; with no model configured it SHALL complete runs with every outbound network connection refused.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`

#### Scenario: The graph the server would load
- **GIVEN** `langgraph.json` at the repository root
- **THEN** its graphs are exactly `{"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}`
- **AND** loading that path as a file and reading `assistant` from it gives a compiled graph, the only one the registry binds

#### Scenario: Compiled by the factory, budget included
- **GIVEN** the registered graph, and a graph the factory compiles from a scripted model and no tools
- **THEN** their nodes are the same, the budget's and the retry policy's middleware among them, and so are their step ceilings

#### Scenario: The model the settings choose
| Settings | The registered graph's model |
|---|---|
| none of the Open WebUI settings | the offline model |
| `OPENWEBUI_URL`, `OPENWEBUI_API_KEY`, `OPENWEBUI_MODEL` all set | the Open WebUI client those settings describe |

#### Scenario: Its retry policy is the domain's
- **GIVEN** Open WebUI configured, answering the first request with HTTP 503
- **WHEN** the registered graph runs on the human message `hello`
- **THEN** the request is retried once, and the run completes with the transcript `human, ai`

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
- **THEN** that graph has a `tools` node, and the registered graph has none

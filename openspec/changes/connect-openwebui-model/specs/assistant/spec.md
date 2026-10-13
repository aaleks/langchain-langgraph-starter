## ADDED Requirements

### Requirement: ASSISTANT-TRANSIENT-RETRY
A model failure that the domain classifies as transient (MODEL-TRANSIENT-FAILURES) -- a streamed chunk that never came included -- SHALL be retried within its turn, at most `MODEL_RETRIES` times (2); when the retries are spent the run SHALL end with that failure, never with a message that reads like an answer. Any other failure SHALL NOT be retried.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestTransientRetry`

#### Scenario: A transient failure, then an answer
- **GIVEN** a scripted model whose first call fails with a timeout, then answers
- **WHEN** the assistant runs on the human message `hello`
- **THEN** the run completes with the transcript `human, ai`, and the model was called 2 times

#### Scenario: Each kind of transient failure, as the client raises it
| The first call fails with | Model calls | The run |
|---|---|---|
| `openai.APITimeoutError` | 2 | completes, `human, ai` |
| `openai.APIConnectionError` (refused) | 2 | completes, `human, ai` |
| a builtin `TimeoutError` -- langchain-openai's streamed-chunk timeout | 2 | completes, `human, ai` |
| HTTP 429 | 2 | completes, `human, ai` |

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
`langgraph.json` SHALL register exactly one graph, under the id `assistant`, bound to the `assistant` export of `src/starter/infrastructure/agents/registry.py`. That export SHALL be the graph the factory compiles -- so it carries the budget and the retry policy -- with the model the process's settings choose, read when it is loaded, and no tools; with no model configured it SHALL complete runs with every outbound network connection refused.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`

#### Scenario: The graph the server would load
- **GIVEN** `langgraph.json` at the repository root
- **THEN** its graphs are exactly `{"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}`
- **AND** loading that path as a file and reading `assistant` from it gives a compiled graph, the only one the registry binds

#### Scenario: Compiled by the factory, budget included
- **GIVEN** the registered graph, and a graph the factory compiles from a scripted model and no tools
- **THEN** their nodes are the same, the budget's middleware among them, and so are their step ceilings -- the retry policy wraps the model call and has no node of its own: its own scenario proves it

#### Scenario: The model the process's settings choose
- **WHEN** the graph is loaded through `langgraph.json`, the settings in the process's environment

| Settings | The registered graph's model |
|---|---|
| none of the Open WebUI settings | the offline model |
| `OPENWEBUI_URL` -- a stand-in on `127.0.0.1` -- `OPENWEBUI_API_KEY=sk-local`, `OPENWEBUI_MODEL=llama3.1:8b` | the Open WebUI client those settings describe: a run on `hello` reaches the stand-in once, at `/api/chat/completions` with the key |
| `OPENWEBUI_URL` and `OPENWEBUI_MODEL` only | none: refused at load, naming `OPENWEBUI_API_KEY` |

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
- **THEN** that graph has a `tools` node, and the registered graph has none

### Requirement: ASSISTANT-MODEL-CALL-BUDGET
A run of the assistant SHALL make at most `MODEL_CALLS_PER_RUN` model turns, a domain budget equal to 10; each turn SHALL make at most `1 + MODEL_RETRIES` attempts (ASSISTANT-TRANSIENT-RETRY), its retries spending none of the budget. A model still proposing tool calls when the budget is spent SHALL end the run with `ModelCallLimitExceededError` -- never with a message that reads like an answer, and never at the step ceiling first under the ceiling the factory's graph runs with: `create_agent`'s 9,999 supersteps, where the budget needs 41.

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
- **WHEN** the assistant runs on the human message `keep adding` with `recursion_limit` 40, then again with 41
- **THEN** at 40 the run raises `GraphRecursionError`; at 41 it raises `ModelCallLimitExceededError`

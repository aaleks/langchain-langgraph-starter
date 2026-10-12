# assistant Specification

## Purpose
The assistant is the starter's first LangGraph graph: a tool loop, run end to end with fake models in the default suite, registered for the local server under a stable id, and bounded by a domain budget on model calls.

## Requirements

### Requirement: ASSISTANT-TOOL-LOOP
The assistant SHALL execute every call the model proposes to a tool it was given, with arguments that tool's schema accepts -- exactly once, with the model's arguments -- hand each result to the model's next call as a tool message answering that call, and end the run when the model answers without proposing a tool call. A reply carrying only `invalid_tool_calls` is outside this rule: its route is OPEN (frame.md, question 3).

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestToolLoop`

#### Scenario: One tool call, then an answer
- **GIVEN** a scripted model that proposes `add(a=2, b=3)`, then answers without a tool call, and a recording `add` tool
- **WHEN** the assistant runs on the human message `what is 2 + 3?`
- **THEN** the model is offered exactly the tool `add`, and the tool is called once, with `{"a": 2, "b": 3}`
- **AND** the transcript's message types are `human, ai, tool, ai`, the tool message's content is `5` and it answers the proposed call's id
- **AND** the model's second call receives that tool message as its last input, and the model was called 2 times

#### Scenario: Two tool calls proposed in one turn
- **GIVEN** a scripted model that proposes `add(a=1, b=2)` and `add(a=3, b=4)` in one message, then answers
- **WHEN** the assistant runs on the human message `add 1 and 2, and 3 and 4`
- **THEN** the tool is called twice, with `{"a": 1, "b": 2}` and `{"a": 3, "b": 4}`
- **AND** the transcript's message types are `human, ai, tool, tool, ai`: two tool messages, `3` and `7`, each answering its own call's id
- **AND** both tool messages are the last inputs of the model's second call, and the model was called 2 times

#### Scenario: Counter-example -- the model answers at once
- **GIVEN** a scripted model that answers without proposing a tool call
- **WHEN** the assistant runs on the human message `hello`
- **THEN** no tool is called, the transcript's message types are `human, ai`, and the model was called once

### Requirement: ASSISTANT-TOOL-ERROR
A call the model proposes to a tool it was not given, or with arguments that tool's schema refuses, SHALL execute no tool. The model's next call SHALL receive a tool message with status `error` answering that call, and the run SHALL go on under the same budget -- the model-recoverable class, handed back rather than raised.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestToolError`

#### Scenario: A call to a tool the model was not given
- **GIVEN** a scripted model that proposes `multiply(a=2, b=3)`, then answers, and only the recording `add` tool
- **WHEN** the assistant runs on the human message `what is 2 times 3?`
- **THEN** no tool is called, and the transcript's message types are `human, ai, tool, ai`
- **AND** the tool message has status `error`, answers the proposed call's id, and is the last input of the model's second call

#### Scenario: Arguments the tool's schema refuses
- **GIVEN** a scripted model that proposes `add(a="two", b=3)`, then answers
- **WHEN** the assistant runs on the human message `what is two plus 3?`
- **THEN** no tool is called, and the transcript's message types are `human, ai, tool, ai`
- **AND** the tool message has status `error`, answers the proposed call's id, and is the last input of the model's second call

#### Scenario: Refused calls still spend the budget
- **GIVEN** a scripted model that proposes `multiply(a=2, b=3)` on every call
- **WHEN** the assistant runs on the human message `keep multiplying`
- **THEN** the run raises `ModelCallLimitExceededError` after 10 model calls, and no tool is called

#### Scenario: Counter-example -- a valid call beside a refused one still runs
- **GIVEN** a scripted model that proposes `add(a=1, b=2)` and `multiply(a=3, b=4)` in one message, then answers
- **WHEN** the assistant runs on the human message `add 1 and 2, multiply 3 and 4`
- **THEN** the tool is called once, with `{"a": 1, "b": 2}`
- **AND** the `add` call is answered by a tool message `3` with status `success`, the `multiply` call by one with status `error`

### Requirement: ASSISTANT-ERRORS-PROPAGATE
An exception that a tool or the model raises SHALL end the run by propagating to the caller unchanged -- the unexpected class, never turned into a message the run carries on with.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestErrorsPropagate`

#### Scenario: A tool raises
- **GIVEN** a scripted model that proposes `explode(a=1)`, then answers, and a tool `explode` that raises `RuntimeError("explode failed")`
- **WHEN** the assistant runs on the human message `explode`
- **THEN** the run raises that `RuntimeError`, and the model was called once

#### Scenario: The model raises
- **GIVEN** a scripted model whose first call raises `TimeoutError("model timed out")`
- **WHEN** the assistant runs on the human message `hello`
- **THEN** the run raises that `TimeoutError`, and no tool is called

#### Scenario: Counter-example -- a tool that returns an error text has not raised
- **GIVEN** a scripted model that proposes `explain(a=1)`, then answers, and a tool `explain` that returns `error: nothing to explain`
- **WHEN** the assistant runs on the human message `explain`
- **THEN** the run completes, and the tool message answering the call has status `success` and content `error: nothing to explain`

### Requirement: ASSISTANT-MODEL-CALL-BUDGET
A run of the assistant SHALL make at most `MODEL_CALLS_PER_RUN` model calls, a domain budget equal to 10. A model still proposing tool calls when the budget is spent SHALL end the run with `ModelCallLimitExceededError` -- never with a message that reads like an answer, and never at the step ceiling first under the ceiling the factory's graph runs with: `create_agent`'s 9,999 supersteps, where the budget needs 41.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestModelCallBudget`

#### Scenario: A model that never stops proposing tool calls
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on every call
- **WHEN** the assistant runs on the human message `keep adding`
- **THEN** the run raises `ModelCallLimitExceededError`, not `GraphRecursionError`
- **AND** the graph's step ceiling is 9,999, `MODEL_CALLS_PER_RUN` is 10, and the model was called exactly `MODEL_CALLS_PER_RUN` times and the tool as many

#### Scenario: Counter-example -- an answer on the last call within budget completes
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on calls 1 to 9 and answers on call 10
- **WHEN** the assistant runs on the human message `keep adding`
- **THEN** the run completes without an error, its last message is an ai message with no tool call
- **AND** the model was called exactly 10 times and the tool 9 times

#### Scenario: Counter-example -- a caller's step ceiling below 41 ends the run first
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on every call
- **WHEN** the assistant runs on the human message `keep adding` with `recursion_limit` 40, then again with 41
- **THEN** at 40 the run raises `GraphRecursionError`; at 41 it raises `ModelCallLimitExceededError`

### Requirement: ASSISTANT-REGISTERED
`langgraph.json` SHALL register exactly one graph, under the id `assistant`, bound to the `assistant` export of `src/starter/infrastructure/agents/registry.py`. That export SHALL be the graph the factory compiles -- so it carries the budget -- with the offline model and no tools, and it SHALL complete runs with every outbound network connection refused.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`

#### Scenario: The graph the server would load
- **GIVEN** `langgraph.json` at the repository root
- **THEN** its graphs are exactly `{"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}`
- **AND** loading that path as a file and reading `assistant` from it gives a compiled graph, the only one the registry binds

#### Scenario: Compiled by the factory, budget included
- **GIVEN** the registered graph, and a graph the factory compiles from a scripted model and no tools
- **THEN** their nodes are the same, the budget's middleware among them, and so are their step ceilings

#### Scenario: An offline run of the registered graph
- **GIVEN** a process in which every outbound socket connection is refused before the graph is loaded
- **WHEN** the graph is loaded through `langgraph.json` and runs on the human message `hello`
- **THEN** the run completes, and the transcript's message types are `human, ai` with no tool call
- **AND** no outbound connection was attempted

#### Scenario: A second turn follows the first
- **GIVEN** the registered graph
- **WHEN** it runs on `hello`, then on that transcript followed by `hello again`
- **THEN** the second transcript's message types are `human, ai, human, ai`, and its two answers have different ids

#### Scenario: Counter-example -- the factory's graph offers a tool it is given; the registered graph offers none
- **GIVEN** a graph the factory compiles from a scripted model and the recording `add` tool
- **THEN** that graph has a `tools` node, and the registered graph has none

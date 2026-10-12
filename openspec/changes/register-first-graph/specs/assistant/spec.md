## Purpose

The assistant is the starter's first LangGraph graph: a tool loop, run end to end with fake models in the default suite, registered for the local server under a stable id, and bounded by a domain budget on model calls.

## ADDED Requirements

### Requirement: ASSISTANT-TOOL-LOOP
The assistant SHALL execute every tool call the model proposes, exactly once and with the model's arguments, hand each result back to the model as a tool message answering that call, and end the run when the model answers without proposing a tool call.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestToolLoop`

#### Scenario: One tool call, then an answer
- **GIVEN** a scripted model that proposes `add(a=2, b=3)`, then answers without a tool call, and a recording `add` tool
- **WHEN** the assistant runs on the human message `what is 2 + 3?`
- **THEN** the tool is called once, with `{"a": 2, "b": 3}`
- **AND** the transcript's message types are `human, ai, tool, ai`, the tool message's content is `5` and it answers the proposed call's id
- **AND** the model was called 2 times

#### Scenario: Two tool calls proposed in one turn
- **GIVEN** a scripted model that proposes `add(a=1, b=2)` and `add(a=3, b=4)` in one message, then answers
- **THEN** the tool is called twice, with `{"a": 1, "b": 2}` and `{"a": 3, "b": 4}`
- **AND** the transcript holds two tool messages, `3` and `7`, each answering its own call's id

#### Scenario: Counter-example -- the model answers at once
- **GIVEN** a scripted model that answers without proposing a tool call
- **THEN** no tool is called, the transcript's message types are `human, ai`, and the model was called once

### Requirement: ASSISTANT-MODEL-CALL-BUDGET
A run of the assistant SHALL make at most `MODEL_CALLS_PER_RUN` model calls, a domain budget equal to 10. A model still proposing tool calls when the budget is spent SHALL end the run with `ModelCallLimitExceededError` -- never with a message that reads like an answer, and never at the runtime's step ceiling first.

- **Kind:** deterministic
- **Proved by:** `tests/integration/agents/test_assistant.py::TestModelCallBudget`

#### Scenario: A model that never stops proposing tool calls
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on every call
- **WHEN** the assistant runs on the human message `keep adding`
- **THEN** the run raises `ModelCallLimitExceededError`, not `GraphRecursionError`
- **AND** the model was called exactly 10 times and the tool 10 times

#### Scenario: Counter-example -- an answer on the last call within budget completes
- **GIVEN** a scripted model that proposes `add(a=1, b=1)` on calls 1 to 9 and answers on call 10
- **THEN** the run completes without an error, its last message is an ai message with no tool call
- **AND** the model was called exactly 10 times and the tool 9 times

### Requirement: ASSISTANT-REGISTERED
`langgraph.json` SHALL register exactly one graph, under the id `assistant`, bound to the `assistant` export of `src/starter/infrastructure/agents/registry.py`. That export SHALL be a compiled graph that completes a run with every outbound network connection refused, because until a requirement names a provider its model is offline.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_registered_assistant.py::TestAssistantIsRegistered`

#### Scenario: The graph the server would load
- **GIVEN** `langgraph.json` at the repository root
- **THEN** its graphs are exactly `{"assistant": "./src/starter/infrastructure/agents/registry.py:assistant"}`
- **AND** loading that path as a file and reading `assistant` from it gives a `CompiledStateGraph`

#### Scenario: An offline run of the registered graph
- **GIVEN** a process in which every outbound socket connection is refused
- **WHEN** the registered graph runs on the human message `hello`
- **THEN** the run completes, and the transcript's message types are `human, ai` with no tool call

#### Scenario: Counter-example -- a graph the factory compiles for a test is not registered
- **GIVEN** the factory compiling an assistant from a scripted model and a recording tool
- **THEN** that graph is not the registry's export, and the registry exports exactly one compiled graph, `assistant`

## Purpose

The local server is how a person runs the starter's graphs on their own machine: started only by `scripts/serve.sh`, driven through its API, and never reaching anything beyond 127.0.0.1.

## ADDED Requirements

### Requirement: LOCAL-SERVER-SERVES-ASSISTANT
`bash scripts/serve.sh --port <port>` SHALL serve the registered graph `assistant` on 127.0.0.1: through the server's API, a run on a new thread SHALL stream its state and complete, and a second process SHALL read that thread's state.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestServesTheAssistant`

#### Scenario: The graph id is served
- **GIVEN** the server started with `bash scripts/serve.sh --port <a free port> --no-reload`
- **WHEN** a client searches the assistants for the graph id `assistant`
- **THEN** exactly one assistant is found, and its graph id is `assistant`

#### Scenario: A run streams and completes
- **WHEN** a client streams a run of `assistant` on a new thread, with the human message `hello` and the stream modes `values` and `updates`
- **THEN** the stream carries both `values` and `updates` events, the last `values` event's message types are `human, ai`, and the run's status is `success`

#### Scenario: A second process reads the thread
- **GIVEN** that run, completed
- **WHEN** a separate process reads the thread's state through the API
- **THEN** it reads the message types `human, ai`

#### Scenario: Counter-example -- a graph id that is not registered is not served
- **WHEN** a client searches the assistants for the graph id `agent`
- **THEN** the server refuses it as not found (HTTP 404), naming `assistant` as the only graph it serves

### Requirement: LOCAL-SERVER-STAYS-LOCAL
Started through `scripts/serve.sh` from a shell that exports a LangSmith key and switches tracing on, the server SHALL start, serve runs -- including one whose request asks for LangSmith tracing -- and SHALL attempt no connection and no name lookup beyond this machine (`127.0.0.1`, `::1`, `localhost`).

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestStaysLocal`

#### Scenario: Nothing beyond this machine, from a hostile shell
- **GIVEN** a shell exporting `LANGSMITH_TRACING=true`, `LANGCHAIN_TRACING_V2=true` and a `LANGSMITH_API_KEY`, and a connection probe loaded into every Python process the server starts
- **WHEN** the server starts and serves the runs of LOCAL-SERVER-SERVES-ASSISTANT
- **THEN** the probe recorded no connection and no name lookup beyond this machine
- **AND** it was loaded in the server's own process: it recorded that process starting

#### Scenario: A run that asks for LangSmith tracing
- **WHEN** a client streams a run of `assistant` whose request sets `langsmith_tracing` to `{"project_name": "probe"}`
- **THEN** the run completes, and the probe still recorded nothing beyond this machine

#### Scenario: Counter-example -- connections on this machine are not counted
- **GIVEN** probe records of a connection to `127.0.0.1` and lookups of `localhost` and `::1`, beside one lookup of `api.smith.langchain.com`
- **THEN** only the lookup of `api.smith.langchain.com` is reported as beyond this machine

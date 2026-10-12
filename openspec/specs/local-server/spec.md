# local-server Specification

## Purpose
The local server is how a person runs the starter's graphs on their own machine: started only by `scripts/serve.sh`, driven through its API, and never reaching anything beyond 127.0.0.1.

## Requirements

### Requirement: LOCAL-SERVER-SERVES-ASSISTANT
`bash scripts/serve.sh --port <port>` SHALL serve the registered graph `assistant` on 127.0.0.1: through the server's API, a run on a new thread SHALL stream its state and complete, and a second process SHALL read that thread's state.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestServesTheAssistant`

#### Scenario: The graph id is served
- **GIVEN** the server started with `bash scripts/serve.sh --port <a free port> --no-reload`
- **WHEN** a client searches the assistants for the graph id `assistant`
- **THEN** exactly one assistant is found, and its graph id is `assistant`

#### Scenario: Bound to this machine only
- **GIVEN** a probe recording every address the server's processes bind
- **THEN** each is `127.0.0.1` or `::1`, and the server's own port on `127.0.0.1` is among them

#### Scenario: A run streams and completes
- **WHEN** a client streams a run of `assistant` on a new thread, with the human message `hello` and the stream modes `values` and `updates`
- **THEN** the stream carries both `values` and `updates` events, the last `values` event's message types are `human, ai`, and the run's status is `success`

#### Scenario: A second process reads the thread
- **GIVEN** that run, completed
- **WHEN** a separate process reads the thread's state through the API
- **THEN** it reads the message types `human, ai`

#### Scenario: Counter-example -- a bind to every interface is not this machine only
- **GIVEN** bind records for `127.0.0.1` and `::1`, beside binds for `0.0.0.0` and for no address at all
- **THEN** only the binds for `0.0.0.0` and for no address are reported as beyond loopback

#### Scenario: Counter-example -- a graph id that is not registered is not served
- **WHEN** a client searches the assistants for the graph id `agent`
- **THEN** the server refuses it as not found (HTTP 404), naming `assistant` as the only graph it serves

### Requirement: LOCAL-SERVER-STAYS-LOCAL
Started through `scripts/serve.sh` from a shell that exports LangSmith keys, switches tracing on and points LangSmith's endpoint elsewhere, the server SHALL start, serve runs -- including one whose request asks for LangSmith tracing -- and stop, attempting no connection and no name lookup beyond this machine (`127.0.0.1`, `::1`, `localhost`, or no host at all).

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestStaysLocal`

#### Scenario: Nothing beyond this machine, from a hostile shell
- **GIVEN** a shell holding none of the suite's local-only variables, exporting all four tracing switches as `true`, a LangSmith API key and control-plane key, and LangSmith's endpoint at `http://langsmith-hostile.invalid`; and a connection probe loaded into every Python process the server starts
- **WHEN** the server starts, serves the runs of LOCAL-SERVER-SERVES-ASSISTANT, and is stopped by a signal -- SIGINT, a person's Ctrl+C, on POSIX; CTRL_BREAK on Windows, where a process group can receive no other
- **THEN** the probe recorded no connection and no name lookup beyond this machine
- **AND** it recorded the server's own process starting, and the signal alone stopped the server

#### Scenario: A run that asks for LangSmith tracing
- **WHEN** a client streams a run of `assistant` whose request sets `langsmith_tracing` to `{"project_name": "probe"}`
- **THEN** the run completes, the probe recorded nothing beyond this machine, and no connection to `serve.sh`'s closed LangSmith endpoint, `127.0.0.1:9` -- a clause the probe can break only on POSIX: on Windows an asyncio client's connect to a literal IP raises no event

#### Scenario: Counter-example -- connections on this machine are not counted
- **GIVEN** probe records of a connection to `127.0.0.1` and lookups of `localhost`, `::1` and no host, beside a connection to `203.0.113.7` and a lookup of `api.smith.langchain.com`
- **THEN** only the connection to `203.0.113.7` and the lookup of `api.smith.langchain.com` are reported as beyond this machine

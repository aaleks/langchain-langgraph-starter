## MODIFIED Requirements

### Requirement: LOCAL-SERVER-STAYS-LOCAL
Started through `scripts/serve.sh` from a shell that exports LangSmith keys, switches tracing on and points LangSmith's endpoint elsewhere, the server SHALL start, serve runs -- including one whose request asks for LangSmith tracing -- and stop, attempting no connection and no name lookup beyond this machine (`127.0.0.1`, `::1`, `localhost`, or no host at all) -- save one: the Open WebUI the owner's `.env` configures, wherever it runs, to which the assistant's conversation goes by the owner's choice.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestStaysLocal`

#### Scenario: Nothing beyond this machine, from a hostile shell
- **GIVEN** no Open WebUI configured, a shell holding none of the suite's local-only variables, exporting all four tracing switches as `true`, a LangSmith API key and control-plane key, and LangSmith's endpoint at `http://langsmith-hostile.invalid`; and a connection probe loaded into every Python process the server starts
- **WHEN** the server starts, serves the runs of LOCAL-SERVER-SERVES-ASSISTANT, and is stopped by a signal -- SIGINT, a person's Ctrl+C, on POSIX; CTRL_BREAK on Windows, where a process group can receive no other
- **THEN** the probe recorded no connection and no name lookup beyond this machine
- **AND** it recorded the server's own process starting, and the signal alone stopped the server

#### Scenario: A run that asks for LangSmith tracing
- **WHEN** a client streams a run of `assistant` whose request sets `langsmith_tracing` to `{"project_name": "probe"}`
- **THEN** the run completes, the probe recorded nothing beyond this machine, and no connection to `serve.sh`'s closed LangSmith endpoint, `127.0.0.1:9` -- a clause the probe can break only on POSIX: on Windows an asyncio client's connect to a literal IP raises no event

#### Scenario: Counter-example -- connections on this machine are not counted
- **GIVEN** probe records of a connection to `127.0.0.1` and lookups of `localhost`, `::1` and no host, beside a connection to `203.0.113.7` and a lookup of `api.smith.langchain.com`
- **THEN** only the connection to `203.0.113.7` and the lookup of `api.smith.langchain.com` are reported as beyond this machine

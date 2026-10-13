"""The registered graph, served by `scripts/serve.sh`, driven through the server's
API -- and nothing leaving the machine while it runs.

`live`: one server serves the whole module, from a hostile shell and under the
connection probe (tests/localserver.py). Every request is made during its
lifetime; every assertion reads what was recorded after the server was stopped
the way a person stops it -- a signal, then its lifespan shutdown -- so whatever
it would send while shutting down is in the record too.
`bash scripts/check.sh live` runs them; the default suite runs only the pure
counter-example at the end.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests.localserver import local_server

# This machine. `None` is a lookup of no host at all -- an address to bind.
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", None}
# What a socket may bind to: loopback only -- "" or "0.0.0.0" is every interface.
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
# Where serve.sh points LangSmith: a connection here means tracing came back on.
DEAD_ENDPOINT = ["127.0.0.1", 9]
HELLO = {"messages": [{"role": "human", "content": "hello"}]}
READ_THREAD = (
    "import json, sys\n"
    "from langgraph_sdk import get_sync_client\n"
    "state = get_sync_client(url=sys.argv[1]).threads.get_state(sys.argv[2])\n"
    "print(json.dumps([m['type'] for m in state['values']['messages']]))\n"
)


def beyond_this_machine(records: list[dict]) -> list[dict]:
    """The probe records of a connection or a name lookup not on this machine."""
    found = []
    for record in records:
        if record["kind"] == "connect":
            detail = record["detail"]
            host = detail[0] if isinstance(detail, list) else detail
        elif record["kind"] == "lookup":
            host = record["detail"]
        else:
            continue
        if host not in LOCAL_HOSTS:
            found.append(record)
    return found


def binds_beyond_loopback(records: list[dict]) -> list[dict]:
    """The probe records of a socket bound to anything but loopback."""
    return [
        r
        for r in records
        if r["kind"] == "bind"
        and not (isinstance(r["detail"], list) and r["detail"][0] in LOOPBACK)
    ]


def message_types(values: dict) -> list[str]:
    return [message["type"] for message in values["messages"]]


def stream(client, thread_id: str, **options) -> tuple[list[str], dict]:
    """Stream a run of `assistant`: the event kinds, and the last state streamed."""
    events, last = [], {}
    for part in client.runs.stream(thread_id, "assistant", input=HELLO, **options):
        events.append(part.event)
        if part.event == "values":
            last = part.data
    return events, last


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    """One server lifetime: started, every request the tests ask about, stopped."""
    from langgraph_sdk import get_sync_client
    from langgraph_sdk.errors import NotFoundError

    seen: dict = {}
    with local_server(tmp_path_factory.mktemp("local-server")) as server:
        client = get_sync_client(url=server.url)
        seen["found"] = client.assistants.search(graph_id="assistant")
        try:
            client.assistants.search(graph_id="agent")
            seen["unknown"] = None
        except NotFoundError as refused:
            seen["unknown"] = refused

        thread = client.threads.create()["thread_id"]
        seen["events"], seen["last"] = stream(client, thread, stream_mode=["values", "updates"])
        seen["runs"] = [run["status"] for run in client.runs.list(thread)]
        seen["second"] = subprocess.run(
            [sys.executable, "-c", READ_THREAD, server.url, thread],
            capture_output=True,
            text=True,
            timeout=120,
        )

        traced = client.threads.create()["thread_id"]
        _, seen["traced_last"] = stream(client, traced, langsmith_tracing={"project_name": "probe"})
        seen["traced_runs"] = [run["status"] for run in client.runs.list(traced)]
    seen["records"] = server.records()
    seen["stopped_gracefully"] = server.stopped_gracefully
    seen["port"] = int(server.url.rsplit(":", 1)[1])
    return seen


def probe_was_in_the_server(records: list[dict]) -> bool:
    """Whether the probe recorded the server's own process starting: a probe that
    never loaded records nothing, and nothing would read like a pass."""
    return any(
        r["kind"] == "start" and "dev" in r["detail"] and "langgraph" in " ".join(r["detail"])
        for r in records
    )


class TestServesTheAssistant:
    """LOCAL-SERVER-SERVES-ASSISTANT: `bash scripts/serve.sh --port <port>` SHALL
    serve the registered graph `assistant` on 127.0.0.1: through the server's
    API, a run on a new thread SHALL stream its state and complete, and a second
    process SHALL read that thread's state."""

    @pytest.mark.live
    def test_the_graph_id_is_served(self, session):
        assert [assistant["graph_id"] for assistant in session["found"]] == ["assistant"]

    @pytest.mark.live
    def test_it_is_bound_to_this_machine_only(self, session):
        binds = [r["detail"] for r in session["records"] if r["kind"] == "bind"]

        assert ["127.0.0.1", session["port"]] in binds, binds
        assert binds_beyond_loopback(session["records"]) == []

    @pytest.mark.live
    def test_a_run_streams_its_state_and_completes(self, session):
        assert {"values", "updates"} <= set(session["events"])
        assert message_types(session["last"]) == ["human", "ai"]
        assert session["runs"] == ["success"]

    @pytest.mark.live
    def test_a_second_process_reads_the_thread(self, session):
        second = session["second"]

        assert second.returncode == 0, second.stderr
        assert json.loads(second.stdout) == ["human", "ai"]

    def test_counter_example_a_bind_to_every_interface_is_not_this_machine_only(self):
        everywhere = {"pid": 1, "kind": "bind", "detail": ["0.0.0.0", 2024]}
        unnamed = {"pid": 1, "kind": "bind", "detail": ["", 2024]}
        records = [
            {"pid": 1, "kind": "bind", "detail": ["127.0.0.1", 0]},
            {"pid": 1, "kind": "bind", "detail": ["::1", 2024, 0, 0]},
            everywhere,
            unnamed,
            {"pid": 1, "kind": "connect", "detail": ["0.0.0.0", 9]},
        ]

        assert binds_beyond_loopback(records) == [everywhere, unnamed]

    @pytest.mark.live
    def test_counter_example_a_graph_id_that_is_not_registered_is_not_served(self, session):
        refused = session["unknown"]

        assert refused is not None, "the server answered a search for an unregistered id"
        assert refused.status_code == 404
        assert "['assistant']" in str(refused)


class TestStaysLocal:
    """LOCAL-SERVER-STAYS-LOCAL: Started through `scripts/serve.sh` from a shell
    that exports LangSmith keys, switches tracing on and points LangSmith's
    endpoint elsewhere, the server SHALL start, serve runs -- including one whose
    request asks for LangSmith tracing -- and stop, attempting no connection and
    no name lookup beyond this machine (`127.0.0.1`, `::1`, `localhost`, or no
    host at all) -- save one: the Open WebUI the owner's `.env` configures,
    wherever it runs. These tests configure none: the suite sets the settings
    empty, and the server inherits them."""

    @pytest.mark.live
    def test_nothing_beyond_this_machine_from_a_hostile_shell(self, session):
        records = session["records"]

        assert probe_was_in_the_server(records), records[:5]
        assert session["stopped_gracefully"] is True
        assert session["runs"] == ["success"]
        assert beyond_this_machine(records) == []

    @pytest.mark.live
    def test_a_run_that_asks_for_langsmith_tracing_still_stays_local(self, session):
        records = session["records"]

        assert probe_was_in_the_server(records), records[:5]
        assert session["stopped_gracefully"] is True
        assert session["traced_runs"] == ["success"]
        assert message_types(session["traced_last"]) == ["human", "ai"]
        assert beyond_this_machine(records) == []
        assert [r for r in records if r["detail"] == DEAD_ENDPOINT] == []

    def test_counter_example_connections_on_this_machine_are_not_counted(self):
        far_connect = {"pid": 2, "kind": "connect", "detail": ["203.0.113.7", 443]}
        far_lookup = {"pid": 3, "kind": "lookup", "detail": "api.smith.langchain.com"}
        records = [
            {"pid": 1, "kind": "start", "detail": ["langgraph", "dev"]},
            {"pid": 1, "kind": "connect", "detail": ["127.0.0.1", 53231]},
            {"pid": 1, "kind": "lookup", "detail": "localhost"},
            {"pid": 1, "kind": "lookup", "detail": None},
            {"pid": 2, "kind": "lookup", "detail": "::1"},
            far_connect,
            far_lookup,
        ]

        assert beyond_this_machine(records) == [far_connect, far_lookup]

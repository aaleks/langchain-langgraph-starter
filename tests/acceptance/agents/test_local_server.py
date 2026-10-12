"""The registered graph, served by `scripts/serve.sh`, driven through the server's
API -- and nothing leaving the machine while it runs.

`live`: each test needs a running server. `bash scripts/check.sh live` runs
them; the default suite runs only the pure counter-example below. The server is
started from a shell that switches LangSmith tracing on (tests/localserver.py).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests.localserver import local_server

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", None}
HELLO = {"messages": [{"role": "human", "content": "hello"}]}


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
def served(tmp_path_factory):
    from langgraph_sdk import get_sync_client

    with local_server(tmp_path_factory.mktemp("serves")) as server:
        client = get_sync_client(url=server.url)
        thread_id = client.threads.create()["thread_id"]
        events, last = stream(client, thread_id, stream_mode=["values", "updates"])
        yield {
            "server": server,
            "client": client,
            "thread": thread_id,
            "events": events,
            "last": last,
        }


@pytest.fixture(scope="module")
def watched(tmp_path_factory):
    """A whole server lifetime under the probe -- started, an ordinary run, a run
    asking for tracing, stopped -- read only after the stop, so whatever the
    server would send at exit is recorded too."""
    from langgraph_sdk import get_sync_client

    with local_server(tmp_path_factory.mktemp("watched")) as server:
        client = get_sync_client(url=server.url)
        ordinary = client.threads.create()["thread_id"]
        stream(client, ordinary)
        traced = client.threads.create()["thread_id"]
        _, traced_last = stream(client, traced, langsmith_tracing={"project_name": "probe"})
        statuses = {
            "ordinary": [run["status"] for run in client.runs.list(ordinary)],
            "traced": [run["status"] for run in client.runs.list(traced)],
        }
    return {"records": server.records(), "statuses": statuses, "traced_last": traced_last}


class TestServesTheAssistant:
    """LOCAL-SERVER-SERVES-ASSISTANT: `bash scripts/serve.sh --port <port>` SHALL
    serve the registered graph `assistant` on 127.0.0.1: through the server's
    API, a run on a new thread SHALL stream its state and complete, and a second
    process SHALL read that thread's state."""

    @pytest.mark.live
    def test_the_graph_id_is_served(self, served):
        found = served["client"].assistants.search(graph_id="assistant")

        assert [assistant["graph_id"] for assistant in found] == ["assistant"]

    @pytest.mark.live
    def test_a_run_streams_its_state_and_completes(self, served):
        assert {"values", "updates"} <= set(served["events"])
        assert message_types(served["last"]) == ["human", "ai"]
        runs = served["client"].runs.list(served["thread"])
        assert [run["status"] for run in runs] == ["success"]

    @pytest.mark.live
    def test_a_second_process_reads_the_thread(self, served):
        read = (
            "import json, sys\n"
            "from langgraph_sdk import get_sync_client\n"
            "state = get_sync_client(url=sys.argv[1]).threads.get_state(sys.argv[2])\n"
            "print(json.dumps([m['type'] for m in state['values']['messages']]))\n"
        )
        second = subprocess.run(
            [sys.executable, "-c", read, served["server"].url, served["thread"]],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert second.returncode == 0, second.stderr
        assert json.loads(second.stdout) == ["human", "ai"]

    @pytest.mark.live
    def test_counter_example_a_graph_id_that_is_not_registered_is_not_served(self, served):
        from langgraph_sdk.errors import NotFoundError

        with pytest.raises(NotFoundError) as refused:
            served["client"].assistants.search(graph_id="agent")

        assert refused.value.status_code == 404
        assert "['assistant']" in str(refused.value)


class TestStaysLocal:
    """LOCAL-SERVER-STAYS-LOCAL: Started through `scripts/serve.sh` from a shell
    that exports a LangSmith key and switches tracing on, the server SHALL start,
    serve runs -- including one whose request asks for LangSmith tracing -- and
    SHALL attempt no connection and no name lookup beyond this machine
    (`127.0.0.1`, `::1`, `localhost`)."""

    @pytest.mark.live
    def test_nothing_beyond_this_machine_from_a_hostile_shell(self, watched):
        records = watched["records"]

        assert watched["statuses"]["ordinary"] == ["success"]
        assert beyond_this_machine(records) == []
        # The probe was loaded where it matters: a probe that never loaded
        # records nothing, and nothing would read like a pass.
        started = [r["detail"] for r in records if r["kind"] == "start"]
        assert any("langgraph" in " ".join(argv) and "dev" in argv for argv in started), started

    @pytest.mark.live
    def test_a_run_that_asks_for_langsmith_tracing_still_stays_local(self, watched):
        assert watched["statuses"]["traced"] == ["success"]
        assert message_types(watched["traced_last"]) == ["human", "ai"]
        assert beyond_this_machine(watched["records"]) == []

    def test_counter_example_connections_on_this_machine_are_not_counted(self):
        smith = {"pid": 3, "kind": "lookup", "detail": "api.smith.langchain.com"}
        records = [
            {"pid": 1, "kind": "start", "detail": ["langgraph", "dev"]},
            {"pid": 1, "kind": "connect", "detail": ["127.0.0.1", 53231]},
            {"pid": 1, "kind": "lookup", "detail": "localhost"},
            {"pid": 2, "kind": "lookup", "detail": "::1"},
            smith,
        ]

        assert beyond_this_machine(records) == [smith]

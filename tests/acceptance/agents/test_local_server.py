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

from starter.infrastructure.models import OFFLINE_ANSWER
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


ORIGINS = ["http://localhost:3000", "https://evil.example", "http://localhost:8080"]


def preflight(url: str, origin: str) -> str | None:
    """A browser's CORS preflight to `/threads` from `origin`: the origin the
    server allows, or None. Straight to 127.0.0.1: no proxy."""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url + "/threads",
        method="OPTIONS",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=10) as answer:
            return answer.headers.get("Access-Control-Allow-Origin")
    except urllib.error.HTTPError as refused:
        return refused.headers.get("Access-Control-Allow-Origin")


def blind_post(url: str, headers: dict[str, str]) -> int:
    """A POST to `/threads` as a page sends one blind -- its answer's status."""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url + "/threads", method="POST", data=b'{"metadata": {}}', headers=headers
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=10) as answer:
            return answer.status
    except urllib.error.HTTPError as refused:
        return refused.code


def socket_handshake(url: str, origin: str | None) -> int:
    """A WebSocket handshake to the server's event stream, as a page or the SDK
    opens one -- 101 when accepted, else the status it was refused with."""
    import uuid

    from websockets.exceptions import InvalidStatus
    from websockets.sync.client import connect

    stream_url = url.replace("http://", "ws://") + f"/threads/{uuid.uuid4()}/stream/events"
    try:
        with connect(stream_url, origin=origin, proxy=None, open_timeout=10):
            return 101
    except InvalidStatus as refused:
        return refused.response.status_code


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
        seen["preflights"] = {origin: preflight(server.url, origin) for origin in ORIGINS}
        before = len(client.threads.search(limit=1000))
        seen["blind"] = {
            "page": blind_post(
                server.url, {"Origin": "https://evil.example", "Content-Type": "text/plain"}
            ),
            "rebound": blind_post(
                server.url, {"Host": "evil.example", "Content-Type": "application/json"}
            ),
        }
        seen["sockets"] = {
            "page": socket_handshake(server.url, "https://evil.example"),
            "agent-chat-ui": socket_handshake(server.url, "http://localhost:3000"),
            "sdk": socket_handshake(server.url, None),
        }
        seen["blind_threads"] = len(client.threads.search(limit=1000)) - before
        # A POST with no body and no Content-Type, as the SDK sends it.
        seen["copied"] = client.threads.copy(thread)["thread_id"] != thread
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


@pytest.fixture(scope="module")
def configured(tmp_path_factory):
    """A second server lifetime, its Open WebUI configured: a stand-in on
    127.0.0.1, so the one place the conversation may go is on this machine, and
    anything else the configured server reached would be beyond it."""
    from langgraph_sdk import get_sync_client

    from tests.openwebui_stub import openwebui_stub

    seen: dict = {}
    with openwebui_stub() as stub:
        settings = {
            "OPENWEBUI_URL": stub.url,
            "OPENWEBUI_API_KEY": "sk-local",
            "OPENWEBUI_MODEL": "llama3.1:8b",
        }
        with local_server(tmp_path_factory.mktemp("configured"), settings=settings) as server:
            client = get_sync_client(url=server.url)
            thread = client.threads.create()["thread_id"]
            _, seen["last"] = stream(client, thread)
            seen["runs"] = [run["status"] for run in client.runs.list(thread)]
        seen["requests"] = list(stub.requests)
    seen["records"] = server.records()
    seen["stopped_gracefully"] = server.stopped_gracefully
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
    host at all) -- save one: the Open WebUI the owner's settings configure,
    wherever it runs, to which the assistant's conversation goes by the owner's
    choice. The module's server configures none -- the suite sets the settings
    empty, and it inherits them; the `configured` server sets its Open WebUI on
    127.0.0.1."""

    @pytest.mark.live
    def test_nothing_beyond_this_machine_from_a_hostile_shell(self, session):
        records = session["records"]

        assert probe_was_in_the_server(records), records[:5]
        assert session["stopped_gracefully"] is True
        assert session["runs"] == ["success"]
        # No Open WebUI configured, checked: an owner's .env read by mistake
        # could answer from this machine, and nothing above would notice.
        assert session["last"]["messages"][-1]["content"] == OFFLINE_ANSWER
        assert beyond_this_machine(records) == []

    @pytest.mark.live
    def test_a_run_that_asks_for_langsmith_tracing_still_stays_local(self, session):
        records = session["records"]

        assert probe_was_in_the_server(records), records[:5]
        assert session["stopped_gracefully"] is True
        assert session["traced_runs"] == ["success"]
        assert message_types(session["traced_last"]) == ["human", "ai"]
        assert session["traced_last"]["messages"][-1]["content"] == OFFLINE_ANSWER
        assert beyond_this_machine(records) == []
        assert [r for r in records if r["detail"] == DEAD_ENDPOINT] == []

    @pytest.mark.live
    def test_with_open_webui_configured_the_conversation_goes_there_and_nowhere_else(
        self, configured
    ):
        records = configured["records"]

        assert probe_was_in_the_server(records), records[:5]
        assert configured["stopped_gracefully"] is True
        assert configured["runs"] == ["success"]
        assert message_types(configured["last"]) == ["human", "ai"]
        assert [(r["path"], r["authorization"]) for r in configured["requests"]] == [
            ("/api/chat/completions", "Bearer sk-local")
        ]
        assert beyond_this_machine(records) == []

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


def task_titles(path) -> list[str]:
    import sqlite3

    db = sqlite3.connect(path)
    titles = [title for (title,) in db.execute("SELECT title FROM tasks ORDER BY id")]
    db.close()
    return titles


def paused_then_resumed(client, decision: dict, task_list) -> dict:
    """A run on a new thread until it pauses, then resumed with `decision`: what
    the owner sees at each point."""
    seen: dict = {}
    thread = client.threads.create()["thread_id"]
    client.runs.wait(
        thread, "assistant", input={"messages": [{"role": "human", "content": "add the plumber"}]}
    )
    state = client.threads.get_state(thread)
    seen["paused_thread"] = client.threads.get(thread)["status"]
    seen["paused_runs"] = [run["status"] for run in client.runs.list(thread)]
    seen["interrupts"] = [i["value"] for i in state.get("interrupts", [])]
    seen["paused_tasks"] = task_titles(task_list)
    client.runs.wait(thread, "assistant", command={"resume": {"decisions": [decision]}})
    seen["thread"] = client.threads.get(thread)["status"]
    seen["runs"] = [run["status"] for run in client.runs.list(thread)]
    seen["last"] = client.threads.get_state(thread)["values"]["messages"][-1]
    seen["tasks"] = task_titles(task_list)
    return seen


@pytest.fixture(scope="module")
def approvals(tmp_path_factory):
    """A server whose model -- a stand-in on 127.0.0.1 -- proposes `add_task`:
    once approved, once rejected, each on its own thread."""
    from langgraph_sdk import get_sync_client

    from tests.openwebui_stub import openwebui_stub, tool_call

    plumber = tool_call("add_task", {"title": "Call the plumber"})
    workdir = tmp_path_factory.mktemp("approvals")
    seen: dict = {}
    with openwebui_stub(replies=[plumber, "done", plumber]) as stub:
        settings = {
            "OPENWEBUI_URL": stub.url,
            "OPENWEBUI_API_KEY": "sk-local",
            "OPENWEBUI_MODEL": "llama3.1:8b",
        }
        with local_server(workdir, settings=settings) as server:
            client = get_sync_client(url=server.url)
            task_list = workdir / "tasks.sqlite3"
            seen["approved"] = paused_then_resumed(client, {"type": "approve"}, task_list)
            seen["rejected"] = paused_then_resumed(client, {"type": "reject"}, task_list)
    return seen


class TestApprovalThroughTheServer:
    """LOCAL-SERVER-APPROVAL: Through the local server's API (`bash scripts/serve.sh`), a
    run whose model proposes a write SHALL pause with the approval request
    (ASSISTANT-WRITE-APPROVAL) -- the thread's status `interrupted`, its state
    showing the interrupt, the task list unchanged; the run itself ends `success`,
    as the server reports a run stopped at an interrupt (measured); a run on the
    same thread with `command={"resume": {"decisions": [{"type": "approve"}]}}`
    SHALL apply the write and complete, and with `{"type": "reject"}` SHALL end with
    nothing written."""

    @pytest.mark.live
    def test_approved_through_the_server(self, approvals):
        approved = approvals["approved"]

        assert approved["paused_thread"] == "interrupted"
        # The server ends the run itself `success`: the pause is the thread's.
        assert approved["paused_runs"] == ["success"]
        assert [
            [action["name"] for action in value["action_requests"]]
            for value in approved["interrupts"]
        ] == [["add_task"]]
        assert approved["paused_tasks"] == []
        assert approved["thread"] == "idle"
        assert approved["runs"] == ["success", "success"]
        assert approved["tasks"] == ["Call the plumber"]

    @pytest.mark.live
    def test_counter_example_rejected_through_the_server(self, approvals):
        rejected = approvals["rejected"]

        assert rejected["paused_thread"] == "interrupted"
        assert rejected["thread"] == "idle"
        assert rejected["runs"] == ["success", "success"]
        assert rejected["last"]["type"] == "tool"
        assert rejected["last"]["content"] == "The owner rejected this; nothing was changed."
        # The list holds the first thread's approved task only.
        assert rejected["tasks"] == ["Call the plumber"]


class TestBrowserOrigins:
    """LOCAL-SERVER-BROWSER-ORIGINS: `bash scripts/serve.sh` SHALL let a web page use the
    server only from `http://localhost:3000`, Agent Chat UI's default origin -- the
    owner's choice (2026-10-15): a preflight from any other origin SHALL get no CORS
    permission, and a request that would change anything from any other origin SHALL
    be refused before it reaches a route (LOCAL-SERVER-REQUEST-GUARD) -- a
    `text/plain` POST a browser sends without a preflight included -- so no other
    page in the owner's browser can read a paused run or approve a write. A client
    that is not a browser -- the SDK -- is unaffected."""

    @pytest.mark.live
    def test_a_browsers_preflight(self, session):
        assert session["preflights"] == {
            "http://localhost:3000": "http://localhost:3000",
            "https://evil.example": None,
            "http://localhost:8080": None,
        }

    @pytest.mark.live
    def test_a_pages_blind_write_is_refused(self, session):
        assert session["blind"] == {"page": 403, "rebound": 403}
        assert session["blind_threads"] == 0
        # The SDK's own requests went through: the session made its threads.
        assert session["runs"] == ["success"]
        assert session["copied"] is True

    @pytest.mark.live
    def test_a_pages_websocket_is_refused(self, session):
        assert session["sockets"] == {"page": 403, "agent-chat-ui": 101, "sdk": 101}

    def test_counter_example_set_by_the_script_not_by_chance(self):
        import re

        from tests.architecture.contract import REPO, shell_exports

        script = (REPO / "scripts" / "serve.sh").read_text(encoding="utf-8")
        from starter.domain.access import BROWSER_ORIGINS

        # One origin, held in one place: CORS and the request guard agree.
        assert re.findall(r"^CORS_ALLOW_ORIGINS=(\S+) \\$", script, re.M) == [
            ",".join(sorted(BROWSER_ORIGINS))
        ]
        assert BROWSER_ORIGINS == {"http://localhost:3000"}
        assert "CORS_ALLOW_ORIGINS" not in shell_exports(script)
        assert re.findall(r"^unset CORS_CONFIG$", script, re.M) == ["unset CORS_CONFIG"]
        assert re.findall(r"^if grep -Eq '\"cors\"\[\[:space:\]\]\*:' ", script, re.M)
        config = json.loads((REPO / "langgraph.json").read_text(encoding="utf-8"))
        assert config["http"] == {"app": "./src/starter/infrastructure/server/guard.py:app"}


def paused_across_a_restart(workdir, kill: bool) -> dict:
    """A run paused for approval, the server stopped -- gracefully, or killed --
    and started again on the same files, then the thread resumed with an
    approval: what the owner sees at each point."""
    from langgraph_sdk import get_sync_client
    from langgraph_sdk.errors import NotFoundError

    from tests.openwebui_stub import openwebui_stub, tool_call

    plumber = tool_call("add_task", {"title": "Call the plumber"})
    seen: dict = {}
    task_list = workdir / "tasks.sqlite3"
    with openwebui_stub(replies=[plumber, "done"]) as stub:
        settings = {
            "OPENWEBUI_URL": stub.url,
            "OPENWEBUI_API_KEY": "sk-local",
            "OPENWEBUI_MODEL": "llama3.1:8b",
        }
        with local_server(workdir, settings=settings) as server:
            client = get_sync_client(url=server.url)
            thread = client.threads.create()["thread_id"]
            human = {"messages": [{"role": "human", "content": "add the plumber"}]}
            client.runs.wait(thread, "assistant", input=human)
            seen["paused"] = client.threads.get(thread)["status"]
            if kill:
                server.kill()
        with local_server(workdir, settings=settings) as server:
            client = get_sync_client(url=server.url)
            if kill:
                try:
                    client.threads.get(thread)
                    seen["before_re_registered"] = "found"
                except NotFoundError:
                    seen["before_re_registered"] = "not found"
                seen["tasks_before"] = task_titles(task_list)
                client.threads.create(thread_id=thread, if_exists="do_nothing")
            else:
                seen["restarted"] = client.threads.get(thread)["status"]
                seen["next"] = client.threads.get_state(thread)["next"]
            approve = {"resume": {"decisions": [{"type": "approve"}]}}
            client.runs.wait(thread, "assistant", command=approve)
            seen["thread"] = client.threads.get(thread)["status"]
    seen["tasks"] = task_titles(task_list)
    return seen


@pytest.fixture(scope="module")
def restarts(tmp_path_factory):
    return {
        "graceful": paused_across_a_restart(tmp_path_factory.mktemp("graceful"), kill=False),
        "killed": paused_across_a_restart(tmp_path_factory.mktemp("killed"), kill=True),
    }


class TestDurableApprovals:
    """LOCAL-SERVER-DURABLE-APPROVAL: `langgraph.json` SHALL name the project's durable
    checkpointer, `{"backend": "custom", "path":
    "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`, so
    the local server keeps every checkpoint in the SQLite file `CHECKPOINTS_DB` names
    (SETTINGS-CHECKPOINTS-DB) the moment it is written. A run paused for the owner's
    approval SHALL survive the server's stop and start: after a graceful stop, the
    thread is `interrupted` at `review_writes` and an approval on it applies the
    write once; after the server is killed, the server may not know the thread --
    its own record of threads is flushed every 10 seconds (measured, `langgraph-api`
    0.16) -- and once a client re-registers it under its id,
    `threads.create(thread_id=..., if_exists="do_nothing")`, an approval applies the
    write once."""

    @pytest.mark.live
    def test_stopped_gracefully_started_again(self, restarts):
        graceful = restarts["graceful"]

        assert graceful["paused"] == "interrupted"
        assert graceful["restarted"] == "interrupted"
        assert graceful["next"] == ["review_writes"]
        assert graceful["thread"] == "idle"
        assert graceful["tasks"] == ["Call the plumber"]

    @pytest.mark.live
    def test_killed_the_thread_re_registered(self, restarts):
        killed = restarts["killed"]

        assert killed["paused"] == "interrupted"
        assert killed["thread"] == "idle"
        assert killed["tasks"] == ["Call the plumber"]

    @pytest.mark.live
    def test_counter_example_killed_not_re_registered(self, restarts):
        killed = restarts["killed"]

        assert killed["before_re_registered"] == "not found"
        assert killed["tasks_before"] == []

    def test_the_checkpointer_named_not_by_chance(self):
        from tests.architecture.contract import REPO

        config = json.loads((REPO / "langgraph.json").read_text(encoding="utf-8"))
        assert config["checkpointer"] == {
            "backend": "custom",
            "path": "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer",
        }

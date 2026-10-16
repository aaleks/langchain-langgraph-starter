"""The assistant's checkpoints in a SQLite file: a pause that outlives the
checkpointer and the graph that wrote it, and the state's version stamped on
each checkpoint -- the durable checkpointer the local server composes
(docs/decisions/0010), driven with a scripted model and a real task list in a
temporary directory, on `ainvoke`, the path the server runs.

Each `async with` opens the file anew: a checkpointer and a graph built after
one closes stand for the server started again.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from starter.domain.agents.state_versions import CheckpointVersionError
from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS, new_task
from starter.infrastructure.agents.checkpointers import VersionedSqliteSaver
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.tools import read_tools, write_tools
from starter.infrastructure.stores.tasks import TaskStore
from tests.fakes import ScriptedChatModel, answer, propose

THREAD = {"configurable": {"thread_id": "t1"}}
APPROVE = Command(resume={"decisions": [{"type": "approve"}]})
REJECT = Command(resume={"decisions": [{"type": "reject"}]})
PLUMBER = ("add_task", {"title": "Call the plumber"})


@pytest.fixture
def store(tmp_path):
    """A list holding task 1, `Renew passport`, open."""
    store = TaskStore(tmp_path / "tasks.sqlite3")
    store.open()
    store.add(new_task("Renew passport"))
    return store


def titles(store) -> list[str]:
    return [t["title"] for t in store.reader(1.0).open_tasks(50)["tasks"]]


def records(store) -> list[tuple[str, str]]:
    db = sqlite3.connect(store.path)
    rows = db.execute("SELECT decision, outcome FROM task_writes ORDER BY id").fetchall()
    db.close()
    return rows


async def run_on(path, store, script, value, *, saver=VersionedSqliteSaver):
    """One server lifetime: the file opened, a graph built on it, `value` run,
    the file closed. The model's replies are `script`; it is returned with the
    output to count its calls."""
    model = ScriptedChatModel(messages=iter(script))
    tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
    async with saver.from_conn_string(str(path)) as checkpointer:
        graph = build_assistant(
            model, tools, transient=lambda failure: False, writer=store.writer()
        ).copy(update={"checkpointer": checkpointer})
        out = await graph.ainvoke(value, THREAD)
        stamps = [c.metadata.get("state_version") async for c in checkpointer.alist(THREAD)]
    return out, model, stamps


def paused(path, store):
    proposal = propose(PLUMBER)
    out, _, stamps = asyncio.run(
        run_on(path, store, [proposal], {"messages": [HumanMessage("add the plumber")]})
    )
    assert "__interrupt__" in out
    return proposal, stamps


class TestPausedOnDisk:
    """ASSISTANT-PAUSED-ON-DISK: A run of the assistant paused for the owner's approval
    on the durable checkpointer SHALL resume on a checkpointer and a graph built anew
    on the same file -- as after the server's restart -- and the owner's decision
    SHALL decide the write once: approved, it is applied, and a second approval on a
    graph built anew again applies nothing more; rejected, nothing is written.
    Proved on `ainvoke`, the path the server runs."""

    def test_paused_rebuilt_approved(self, tmp_path, store):
        path = tmp_path / "checkpoints.sqlite3"
        proposal, _ = paused(path, store)

        out, _, _ = asyncio.run(run_on(path, store, [answer()], APPROVE))

        answers = {m.tool_call_id: m.content for m in out["messages"] if m.type == "tool"}
        assert answers[proposal.tool_calls[0]["id"]] == json.dumps(
            {"outcome": "applied", "task_id": 2}
        )
        assert titles(store) == ["Renew passport", "Call the plumber"]
        assert records(store) == [("approve", "applied")]

        asyncio.run(run_on(path, store, [answer()], APPROVE))

        assert titles(store) == ["Renew passport", "Call the plumber"]
        assert records(store) == [("approve", "applied")]

    def test_counter_example_rebuilt_rejected(self, tmp_path, store):
        path = tmp_path / "checkpoints.sqlite3"
        paused(path, store)

        asyncio.run(run_on(path, store, [], REJECT))

        assert titles(store) == ["Renew passport"]
        assert records(store) == [("reject", "rejected")]


class Newer(VersionedSqliteSaver):
    """A checkpointer of code one state version ahead -- what a rollback meets."""

    state_version = VersionedSqliteSaver.state_version + 1


class TestCheckpointVersion:
    """ASSISTANT-CHECKPOINT-VERSION: Every checkpoint the durable checkpointer writes
    SHALL carry the state's version in its metadata, `state_version`,
    `ASSISTANT_STATE_VERSION`. A thread whose latest checkpoint carries a version
    newer than the code's SHALL be refused before any node runs --
    `CheckpointVersionError`, naming both versions, nothing written and the model not
    called; one that carries no version -- written before the stamp -- or an older
    one SHALL be loaded as it is, the state contract deciding the rest
    (ASSISTANT-STATE-CONTRACT). What a version found means is the domain's
    `checkpoint_version_refusal`."""

    def test_stamped(self, tmp_path, store):
        from starter.infrastructure.agents.graphs.assistant.state import ASSISTANT_STATE_VERSION

        _, stamps = paused(tmp_path / "checkpoints.sqlite3", store)

        assert stamps and set(stamps) == {ASSISTANT_STATE_VERSION} == {2}

    def test_counter_example_older_code_meets_a_newer_checkpoint(self, tmp_path, store):
        path = tmp_path / "checkpoints.sqlite3"
        asyncio.run(
            run_on(path, store, [answer()], {"messages": [HumanMessage("hello")]}, saver=Newer)
        )
        model = ScriptedChatModel(messages=iter([propose(PLUMBER), answer()]))

        with pytest.raises(CheckpointVersionError, match="3, newer than 2"):
            asyncio.run(run_with(path, store, model, {"messages": [HumanMessage("add it")]}))

        assert model.calls == 0
        assert titles(store) == ["Renew passport"]
        assert records(store) == []


async def run_with(path, store, model, value):
    tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
    async with VersionedSqliteSaver.from_conn_string(str(path)) as checkpointer:
        graph = build_assistant(
            model, tools, transient=lambda failure: False, writer=store.writer()
        ).copy(update={"checkpointer": checkpointer})
        return await graph.ainvoke(value, THREAD)

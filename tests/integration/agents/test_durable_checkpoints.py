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
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
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


class Older(VersionedSqliteSaver):
    """A checkpointer of the code before, at state version 1."""

    state_version = 1


async def stamps_of(path, thread: str = "t1") -> list:
    """Every checkpoint's stamp on `thread`, read as stored -- no refusal."""
    config = {"configurable": {"thread_id": thread}}
    async with AsyncSqliteSaver.from_conn_string(str(path)) as plain:
        return [c.metadata.get("state_version") async for c in plain.alist(config)]


class TestCheckpointVersion:
    """ASSISTANT-CHECKPOINT-VERSION: Every checkpoint the durable checkpointer writes SHALL
    carry the state's version in its metadata, `state_version`,
    `ASSISTANT_STATE_VERSION`: the version of the code that wrote it. A thread whose
    latest checkpoint carries a version newer than the code's SHALL be refused before
    any node runs -- `CheckpointVersionError`, naming both versions, nothing written to
    the task list or the checkpoint file and the model not called -- and its state
    cannot be read through the checkpointer either; its history is listed as stored. One
    that carries no version -- written before the stamp -- or an older one SHALL be
    loaded as it is, the state contract deciding the rest (ASSISTANT-STATE-CONTRACT). A
    thread's copy SHALL keep each checkpoint's stamp, and a thread holding a checkpoint
    the code refuses SHALL not be copied. What a version found means is the domain's
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

        before = asyncio.run(stamps_of(path))

        with pytest.raises(CheckpointVersionError, match="3, newer than 2"):
            asyncio.run(run_with(path, store, model, {"messages": [HumanMessage("add it")]}))

        # Refused before any node: no checkpoint of its own written over the newer ones.
        assert asyncio.run(stamps_of(path)) == before == [3] * len(before)
        assert model.calls == 0
        assert titles(store) == ["Renew passport"]
        assert records(store) == []


class TestCheckpointVersionAcrossVersions:
    """ASSISTANT-CHECKPOINT-VERSION: Every checkpoint the durable checkpointer writes SHALL
    carry the state's version in its metadata, `state_version`,
    `ASSISTANT_STATE_VERSION`: the version of the code that wrote it. A thread whose
    latest checkpoint carries a version newer than the code's SHALL be refused before
    any node runs -- `CheckpointVersionError`, naming both versions, nothing written to
    the task list or the checkpoint file and the model not called -- and its state
    cannot be read through the checkpointer either; its history is listed as stored. One
    that carries no version -- written before the stamp -- or an older one SHALL be
    loaded as it is, the state contract deciding the rest (ASSISTANT-STATE-CONTRACT). A
    thread's copy SHALL keep each checkpoint's stamp, and a thread holding a checkpoint
    the code refuses SHALL not be copied. What a version found means is the domain's
    `checkpoint_version_refusal`."""

    @pytest.mark.parametrize(
        "writer", [Older, AsyncSqliteSaver], ids=["stamped-1", "written-before-the-stamp"]
    )
    def test_an_older_checkpoint_resumes_applied_once(self, tmp_path, store, writer):
        path = tmp_path / "checkpoints.sqlite3"
        out, _, _ = asyncio.run(
            run_on(
                path,
                store,
                [propose(PLUMBER)],
                {"messages": [HumanMessage("add the plumber")]},
                saver=writer,
            )
        )
        assert "__interrupt__" in out

        asyncio.run(run_on(path, store, [answer()], APPROVE))

        assert titles(store) == ["Renew passport", "Call the plumber"]
        assert records(store) == [("approve", "applied")]

    def test_a_copy_keeps_each_stamp(self, tmp_path, store):
        path = tmp_path / "checkpoints.sqlite3"
        asyncio.run(
            run_on(path, store, [answer()], {"messages": [HumanMessage("hi")]}, saver=Older)
        )

        asyncio.run(copy(path, "t1", "t2"))

        assert asyncio.run(stamps_of(path, "t2")) == asyncio.run(stamps_of(path, "t1"))
        assert set(asyncio.run(stamps_of(path, "t2"))) == {1}

    def test_counter_example_a_newer_thread_is_not_copied(self, tmp_path, store):
        path = tmp_path / "checkpoints.sqlite3"
        asyncio.run(
            run_on(path, store, [answer()], {"messages": [HumanMessage("hi")]}, saver=Newer)
        )

        with pytest.raises(CheckpointVersionError, match="3, newer than 2"):
            asyncio.run(copy(path, "t1", "t2"))

        assert asyncio.run(stamps_of(path, "t2")) == []


async def copy(path, source: str, target: str) -> None:
    async with VersionedSqliteSaver.from_conn_string(str(path)) as checkpointer:
        await checkpointer.acopy_thread(source, target)


class TestStrictDeserialization:
    """ASSISTANT-CHECKPOINT-STRICT: The durable checkpointer SHALL read a checkpoint with
    LangGraph's serializer in its strict mode, whatever the environment says: a msgpack
    value naming a constructor outside LangGraph's and LangChain's safe types SHALL NOT
    be called, and a value stored as pickle SHALL be refused. The file outlives the
    process that wrote it, so what it holds is read as untrusted."""

    def test_a_planted_constructor_is_not_called(self, tmp_path):
        import ormsgpack
        from langgraph.checkpoint.base import empty_checkpoint
        from langgraph.checkpoint.serde.jsonplus import EXT_CONSTRUCTOR_SINGLE_ARG, _msgpack_enc

        path = tmp_path / "checkpoints.sqlite3"
        planted = tmp_path / "made-by-a-checkpoint"
        value = ormsgpack.Ext(
            EXT_CONSTRUCTOR_SINGLE_ARG, _msgpack_enc(("os", "mkdir", str(planted)))
        )

        async def plant_then_load():
            checkpoint = empty_checkpoint()
            checkpoint["channel_values"] = {"messages": value}
            checkpoint["channel_versions"] = {"messages": 1}
            async with VersionedSqliteSaver.from_conn_string(str(path)) as checkpointer:
                await checkpointer.aput(
                    {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}},
                    checkpoint,
                    {"source": "input", "step": -1, "parents": {}},
                    {"messages": 1},
                )
            async with VersionedSqliteSaver.from_conn_string(str(path)) as checkpointer:
                await checkpointer.aget_tuple(THREAD)

        asyncio.run(plant_then_load())

        assert not planted.exists()

    def test_counter_example_a_pickled_value_is_refused(self, tmp_path, store):
        import pickle

        path = tmp_path / "checkpoints.sqlite3"
        asyncio.run(run_on(path, store, [answer()], {"messages": [HumanMessage("hi")]}))
        db = sqlite3.connect(path)
        db.execute("UPDATE checkpoints SET type = 'pickle', checkpoint = ?", (pickle.dumps({}),))
        db.commit()
        db.close()

        async def load():
            async with VersionedSqliteSaver.from_conn_string(str(path)) as checkpointer:
                await checkpointer.aget_tuple(THREAD)

        with pytest.raises(NotImplementedError, match="pickle"):
            asyncio.run(load())


class TestTheServersCheckpointer:
    """LOCAL-SERVER-DURABLE-APPROVAL: `langgraph.json` SHALL name the project's durable
    checkpointer, `{"backend": "custom", "path":
    "./src/starter/infrastructure/agents/checkpointers.py:durable_checkpointer"}`, so
    the local server keeps every checkpoint in the SQLite file `CHECKPOINTS_DB` names
    (SETTINGS-CHECKPOINTS-DB) the moment it is written, its folder created; the
    registered graph carries no checkpointer of its own, the server supplies it. A run
    paused for the owner's approval SHALL survive the server's stop and start: after a
    graceful stop, the thread is `interrupted` at `review_writes` and an approval on it
    applies the write once; after the server is killed, the server may not know the
    thread -- its own record of threads is flushed on a 10-second clock (measured,
    `langgraph-api` 0.16), so a flush may or may not have caught it -- and once a client
    re-registers it under its id, `threads.create(thread_id=...,
    if_exists="do_nothing")`, an approval applies the write once."""

    def test_loaded_as_the_server_loads_it(self, tmp_path, store):
        import importlib.util

        from starter.config.settings import Settings
        from tests.architecture.contract import REPO

        config = json.loads((REPO / "langgraph.json").read_text(encoding="utf-8"))
        module_path, name = config["checkpointer"]["path"].rsplit(":", 1)
        spec = importlib.util.spec_from_file_location("server_checkpointer", REPO / module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = tmp_path / "nested" / "checkpoints.sqlite3"
        settings = Settings("", "", "", str(store.path), checkpoints_db=str(target))

        async def pause_on_it():
            async with getattr(module, name)(settings) as checkpointer:
                assert type(checkpointer).__name__ == "VersionedSqliteSaver"
                tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
                model = ScriptedChatModel(messages=iter([propose(PLUMBER)]))
                graph = build_assistant(
                    model, tools, transient=lambda failure: False, writer=store.writer()
                ).copy(update={"checkpointer": checkpointer})
                return await graph.ainvoke({"messages": [HumanMessage("add it")]}, THREAD)

        out = asyncio.run(pause_on_it())

        assert "__interrupt__" in out
        assert target.is_file()
        assert asyncio.run(stamps_of(target))

    def test_the_registered_graph_carries_no_checkpointer(self):
        from starter.infrastructure.agents import registry

        assert registry.assistant.checkpointer is None


async def run_with(path, store, model, value):
    tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
    async with VersionedSqliteSaver.from_conn_string(str(path)) as checkpointer:
        graph = build_assistant(
            model, tools, transient=lambda failure: False, writer=store.writer()
        ).copy(update={"checkpointer": checkpointer})
        return await graph.ainvoke(value, THREAD)

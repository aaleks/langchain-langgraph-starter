"""The assistant's writes: proposed by the model, checked, paused for the owner's
decision, then applied once or rejected -- driven through the factory with a
scripted model, a real task list in a temporary file, and an in-memory
checkpointer (a pause needs one; it is no evidence of durability)."""

from __future__ import annotations

import json
import sqlite3

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS, new_task
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.tools import read_tools, write_tools
from starter.infrastructure.stores.tasks import TaskStore
from tests.fakes import answer, propose

REJECTED = "The owner rejected this; nothing was changed."


def no_retries(failure: Exception) -> bool:
    return False


@pytest.fixture
def store(tmp_path):
    """A list holding task 1, `Renew passport`, open."""
    store = TaskStore(tmp_path / "tasks.sqlite3")
    store.open()
    store.add(new_task("Renew passport"))
    return store


def graph_for(model, store):
    tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
    graph = build_assistant(model, tools, transient=no_retries, writer=store.writer())
    return graph.copy(update={"checkpointer": InMemorySaver()})


def thread(name: str = "t1") -> dict:
    return {"configurable": {"thread_id": name}}


def tasks(store) -> list[tuple]:
    db = sqlite3.connect(store.path)
    rows = db.execute("SELECT id, title, assignee, status FROM tasks ORDER BY id").fetchall()
    db.close()
    return rows


def records(store) -> list[tuple]:
    db = sqlite3.connect(store.path)
    rows = db.execute("SELECT write_key, decision, outcome FROM task_writes ORDER BY id").fetchall()
    db.close()
    return rows


def answers(messages) -> dict[str, tuple[str, str]]:
    return {m.tool_call_id: (m.status, m.content) for m in messages if m.type == "tool"}


class TestWriteProposal:
    """ASSISTANT-WRITE-PROPOSAL: A call the model proposes to a write tool -- `add_task`,
    `close_task` or `reassign_task` (TOOLS-TASK-WRITES) -- SHALL be checked before
    the owner sees it, by the tool's schema and by TASKS-WRITE-VALUES. A call either
    refuses SHALL be answered by a tool message of status `error`, reading `Error:
    <tool> was not proposed: <why>`, nothing written and the owner not asked, and
    the run SHALL go on to the model. A call both accept SHALL wait for the owner
    (ASSISTANT-WRITE-APPROVAL), after the reply's other calls have run."""

    @pytest.mark.parametrize(
        ("call", "message"),
        [
            (
                ("add_task", {"title": "   "}),
                "Error: add_task was not proposed: the title is blank",
            ),
            (
                ("close_task", {"task_id": 0}),
                "Error: close_task was not proposed: the task_id is not between 1 and "
                "9223372036854775807",
            ),
            (
                ("reassign_task", {"task_id": 1}),
                "Error: reassign_task was not proposed: its arguments do not match its schema",
            ),
        ],
        ids=["blank-title", "id-0", "no-assignee"],
    )
    def test_a_proposal_refused_before_the_owner_sees_it(self, fake_llm, store, call, message):
        proposal = propose(call)
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)

        out = graph.invoke({"messages": [HumanMessage("do it")]}, thread())

        assert "__interrupt__" not in out
        assert answers(out["messages"]) == {proposal.tool_calls[0]["id"]: ("error", message)}
        assert graph.get_state(thread()).next == ()
        assert model.calls == 2
        assert records(store) == []

    def test_writes_spend_the_tool_call_budget(self, fake_llm, store):
        from starter.domain.agents.budgets import ToolCallBudgetExceededError

        proposal = propose(*[("add_task", {"title": "Call the plumber"})] * 21)
        graph = graph_for(fake_llm([proposal, answer()]), store)

        with pytest.raises(ToolCallBudgetExceededError) as ended:
            graph.invoke({"messages": [HumanMessage("add it 21 times")]}, thread())

        assert ended.value.count == 21
        assert graph.get_state(thread()).next == ("run_tools",)
        assert records(store) == []

    def test_counter_example_a_read_beside_a_write_runs_first(self, fake_llm, store):
        proposal = propose(("list_tasks", {}), ("add_task", {"title": "Call the plumber"}))
        graph = graph_for(fake_llm([proposal, answer()]), store)

        out = graph.invoke({"messages": [HumanMessage("list, then add")]}, thread())

        read_id, write_id = (call["id"] for call in proposal.tool_calls)
        assert graph.get_state(thread()).next == ("review_writes",)
        assert set(answers(out["messages"])) == {read_id}
        assert [a["name"] for a in out["__interrupt__"][0].value["action_requests"]] == ["add_task"]
        assert write_id not in answers(out["messages"])


class TestWriteApproval:
    """ASSISTANT-WRITE-APPROVAL: A reply's write calls that pass their checks SHALL pause
    the run before anything is written, at `review_writes`, with `interrupt()`
    carrying LangChain's approval request: `action_requests`, one per call in the
    reply's order -- the tool's name, its checked arguments and a description -- and
    `review_configs`, one per tool named, in the order first named, allowing exactly
    `approve` and `reject`. The run SHALL be resumed on the same thread with
    `Command(resume={"decisions": [...]})`, one decision per action, in order
    (ASSISTANT-WRITE-DECISIONS)."""

    PROPOSAL = (
        ("add_task", {"title": " Call the plumber ", "assignee": "sam"}),
        ("close_task", {"task_id": 1}),
    )

    def test_the_request(self, fake_llm, store):
        graph = graph_for(fake_llm([propose(*self.PROPOSAL), answer()]), store)
        before = tasks(store)

        out = graph.invoke({"messages": [HumanMessage("add it, close 1")]}, thread())

        assert graph.get_state(thread()).next == ("review_writes",)
        assert [i.value for i in out["__interrupt__"]] == [
            {
                "action_requests": [
                    {
                        "name": "add_task",
                        "args": {"title": "Call the plumber", "assignee": "sam", "notes": ""},
                        "description": 'Add the task "Call the plumber", assigned to sam',
                    },
                    {"name": "close_task", "args": {"task_id": 1}, "description": "Close task 1"},
                ],
                "review_configs": [
                    {"action_name": "add_task", "allowed_decisions": ["approve", "reject"]},
                    {"action_name": "close_task", "allowed_decisions": ["approve", "reject"]},
                ],
            }
        ]
        assert tasks(store) == before
        assert records(store) == []

    def test_one_review_config_per_tool(self, fake_llm, store):
        proposal = propose(("add_task", {"title": "a"}), ("add_task", {"title": "b"}))
        graph = graph_for(fake_llm([proposal, answer()]), store)

        request = graph.invoke({"messages": [HumanMessage("add both")]}, thread())["__interrupt__"][
            0
        ].value

        assert [a["args"]["title"] for a in request["action_requests"]] == ["a", "b"]
        assert request["review_configs"] == [
            {"action_name": "add_task", "allowed_decisions": ["approve", "reject"]}
        ]

    @pytest.mark.parametrize(
        ("call", "description"),
        [
            (("add_task", {"title": "Renew passport"}), 'Add the task "Renew passport"'),
            (("reassign_task", {"task_id": 3, "assignee": "ana"}), "Reassign task 3 to ana"),
            (("reassign_task", {"task_id": 3, "assignee": ""}), "Unassign task 3"),
        ],
        ids=["unassigned-creation", "reassignment", "unassignment"],
    )
    def test_each_description(self, fake_llm, store, call, description):
        graph = graph_for(fake_llm([propose(call), answer()]), store)

        out = graph.invoke({"messages": [HumanMessage("do it")]}, thread())

        assert out["__interrupt__"][0].value["action_requests"][0]["description"] == description

    def test_counter_example_reads_alone_never_pause(self, fake_llm, store):
        graph = graph_for(fake_llm([propose(("list_tasks", {})), answer()]), store)

        out = graph.invoke({"messages": [HumanMessage("list")]}, thread())

        assert "__interrupt__" not in out
        assert graph.get_state(thread()).next == ()


class TestWriteDecisions:
    """ASSISTANT-WRITE-DECISIONS: Each decision SHALL decide its write. `{"type":
    "approve"}` SHALL apply it through the task list's writer (TASKS-WRITES), under
    ASSISTANT-WRITE-KEY's key, and answer the call with its outcome as JSON --
    `{"outcome": "applied", "task_id": 8}`, status `success`, or `{"outcome":
    "refused", "task_id": 7, "reason": "no task 7"}`, status `error`. Anything else
    SHALL reject it: `{"type": "reject"}`, another type, a missing decision, or
    decisions that do not match the actions in number. A rejected write writes
    nothing, is recorded as rejected (TASKS-AUDIT), and is answered `The owner
    rejected this; nothing was changed.`, status `error`. When every write of the
    reply is approved the run SHALL go on to the model; when any is rejected it
    SHALL end, the model not called again."""

    APPLIED_2 = ("success", json.dumps({"outcome": "applied", "task_id": 2}))
    APPLIED_1 = ("success", json.dumps({"outcome": "applied", "task_id": 1}))
    REJECTED = ("error", REJECTED)

    @pytest.mark.parametrize(
        ("resume", "add", "close", "goes_on", "decided"),
        [
            (
                {"decisions": [{"type": "approve"}, {"type": "approve"}]},
                APPLIED_2,
                APPLIED_1,
                True,
                [("approve", "applied"), ("approve", "applied")],
            ),
            (
                {"decisions": [{"type": "approve"}, {"type": "reject"}]},
                APPLIED_2,
                REJECTED,
                False,
                [("approve", "applied"), ("reject", "rejected")],
            ),
            (
                {"decisions": [{"type": "reject"}, {"type": "reject"}]},
                REJECTED,
                REJECTED,
                False,
                [("reject", "rejected"), ("reject", "rejected")],
            ),
            (
                {"decisions": [{"type": "approve"}, {"type": "edit"}]},
                APPLIED_2,
                REJECTED,
                False,
                [("approve", "applied"), ("reject", "rejected")],
            ),
            (
                {"decisions": [{"type": "approve"}]},
                REJECTED,
                REJECTED,
                False,
                [("reject", "rejected"), ("reject", "rejected")],
            ),
            (
                {"decisions": "yes"},
                REJECTED,
                REJECTED,
                False,
                [("reject", "rejected"), ("reject", "rejected")],
            ),
        ],
        ids=[
            "approve-approve",
            "approve-reject",
            "reject-reject",
            "approve-edit",
            "one-decision-for-two",
            "not-a-list",
        ],
    )
    def test_decisions(self, fake_llm, store, resume, add, close, goes_on, decided):
        proposal = propose(*TestWriteApproval.PROPOSAL)
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)
        graph.invoke({"messages": [HumanMessage("add it, close 1")]}, thread())

        out = graph.invoke(Command(resume=resume), thread())

        add_id, close_id = (call["id"] for call in proposal.tool_calls)
        assert answers(out["messages"]) == {add_id: add, close_id: close}
        assert graph.get_state(thread()).next == ()
        assert model.calls == (2 if goes_on else 1)
        assert out["messages"][-1].type == ("ai" if goes_on else "tool")
        assert [(d, o) for _, d, o in records(store)] == decided
        applied = [row for row in decided if row[1] == "applied"]
        expected_tasks = [(1, "Renew passport", "", "open")]
        if add == self.APPLIED_2:
            expected_tasks.append((2, "Call the plumber", "sam", "open"))
        if close == self.APPLIED_1:
            expected_tasks[0] = (1, "Renew passport", "", "closed")
        assert tasks(store) == expected_tasks
        assert len(applied) == sum(1 for o in (add, close) if o[0] == "success")

    def test_counter_example_an_approved_write_the_list_refuses(self, fake_llm, store):
        proposal = propose(("close_task", {"task_id": 7}))
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)
        graph.invoke({"messages": [HumanMessage("close 7")]}, thread())

        out = graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread())

        refused = json.dumps({"outcome": "refused", "task_id": 7, "reason": "no task 7"})
        assert answers(out["messages"]) == {proposal.tool_calls[0]["id"]: ("error", refused)}
        assert model.calls == 2
        assert out["messages"][-1].type == "ai"


class TestWriteKey:
    """ASSISTANT-WRITE-KEY: An approved or rejected write SHALL be decided under the key
    `<thread id>:<reply id>:<call id>` -- the thread's id, the id of the reply that
    proposed the call, the call's id -- so a replay of `apply_writes` from its
    checkpoint changes the task list once. Not the superstep: a replay runs
    `apply_writes` at another step (measured: 5, then 6). A key longer than
    `WRITE_KEY_MAX` SHALL end the run with `ValueError`, nothing written."""

    def test_replayed_applied_once(self, fake_llm, store):
        proposal = propose(("add_task", {"title": "Call the plumber"}))
        graph = graph_for(fake_llm([proposal, answer(), answer()]), store)
        graph.invoke({"messages": [HumanMessage("add it")]}, thread())
        graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread())
        before_apply = next(
            s for s in graph.get_state_history(thread()) if s.next == ("apply_writes",)
        )

        graph.invoke(None, before_apply.config)

        assert [row[1] for row in tasks(store)] == ["Renew passport", "Call the plumber"]
        (key, decision, outcome), *more = records(store)
        assert more == []
        reply_id = graph.get_state(thread()).values["messages"][1].id
        assert key == f"t1:{reply_id}:{proposal.tool_calls[0]['id']}"
        assert (decision, outcome) == ("approve", "applied")

    def test_counter_example_a_thread_id_too_long_for_a_key(self, fake_llm, store):
        long = thread("t" * 300)
        graph = graph_for(fake_llm([propose(("add_task", {"title": "Call the plumber"}))]), store)
        graph.invoke({"messages": [HumanMessage("add it")]}, long)
        before = tasks(store)

        with pytest.raises(ValueError):
            graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), long)

        assert tasks(store) == before
        assert records(store) == []

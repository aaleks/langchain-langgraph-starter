"""The assistant's writes: proposed by the model, checked, paused for the owner's
decision, then applied once or rejected -- driven through the factory with a
scripted model, a real task list in a temporary file, and an in-memory
checkpointer (a pause needs one; it is no evidence of durability)."""

from __future__ import annotations

import asyncio
import json
import sqlite3

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from starter.application.prompts import UNRUN_CALL_ANSWER
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


# The server runs a graph with `astream`: each route is proved on both paths.
PATHS = ["invoke", "ainvoke"]


def run(graph, value, config, path: str):
    if path == "ainvoke":
        return asyncio.run(graph.ainvoke(value, config))
    return graph.invoke(value, config)


def answers(messages) -> dict[str, tuple[str, str]]:
    return {m.tool_call_id: (m.status, m.content) for m in messages if m.type == "tool"}


class TestWriteProposal:
    """ASSISTANT-WRITE-PROPOSAL: A call the model proposes to a write tool -- `add_task`,
    `close_task` or `reassign_task` (TOOLS-TASK-WRITES) -- SHALL be checked before
    the owner sees it, by the tool's schema, strictly -- `true` or `"1"` is no task
    id -- and by TASKS-WRITE-VALUES; a call with no thread to pause on -- no
    checkpointer to come back to -- or whose key (ASSISTANT-WRITE-KEY) would be too
    long to record, is refused too. A refused call SHALL be answered by a tool
    message of status `error`, reading `Error: <tool> was not proposed: <why>`,
    nothing written and the owner not asked, and the run SHALL go on to the model. A
    call both accept SHALL wait for the owner (ASSISTANT-WRITE-APPROVAL), after the
    reply's other calls have run."""

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
            (
                ("close_task", {"task_id": True}),
                "Error: close_task was not proposed: its arguments do not match its schema",
            ),
            (
                ("close_task", {"task_id": "1"}),
                "Error: close_task was not proposed: its arguments do not match its schema",
            ),
        ],
        ids=["blank-title", "id-0", "no-assignee", "id-true", "id-text"],
    )
    @pytest.mark.parametrize("path", PATHS)
    def test_a_proposal_refused_before_the_owner_sees_it(
        self, fake_llm, store, call, message, path
    ):
        proposal = propose(call)
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)

        out = run(graph, {"messages": [HumanMessage("do it")]}, thread(), path)

        assert "__interrupt__" not in out
        assert answers(out["messages"]) == {proposal.tool_calls[0]["id"]: ("error", message)}
        assert graph.get_state(thread()).next == ()
        assert model.calls == 2
        assert records(store) == []

    def test_a_key_too_long_is_refused_before_the_owner_is_asked(self, fake_llm, store):
        proposal = propose(("add_task", {"title": "Call the plumber"}))
        model = fake_llm([proposal, answer()])
        long = thread("t" * 300)

        out = graph_for(model, store).invoke({"messages": [HumanMessage("add it")]}, long)

        assert "__interrupt__" not in out
        assert model.calls == 2
        assert answers(out["messages"]) == {
            proposal.tool_calls[0]["id"]: (
                "error",
                "Error: add_task was not proposed: its key would be too long to record",
            )
        }
        assert records(store) == []

    @pytest.mark.parametrize("config", [None, {"configurable": {"thread_id": "t1"}}])
    def test_with_no_thread_to_pause_on_a_write_is_refused(self, fake_llm, store, config):
        proposal = propose(("add_task", {"title": "Call the plumber"}))
        model = fake_llm([proposal, answer()])
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        # No checkpointer: a thread id alone is nothing to come back to.
        graph = build_assistant(model, tools, transient=no_retries, writer=store.writer())

        out = graph.invoke({"messages": [HumanMessage("add it")]}, config)

        assert "__interrupt__" not in out
        assert answers(out["messages"]) == {
            proposal.tool_calls[0]["id"]: (
                "error",
                "Error: add_task was not proposed: there is no thread to pause on for the "
                "owner's decision",
            )
        }
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

    @pytest.mark.parametrize("path", PATHS)
    def test_a_refused_write_beside_a_read_is_answered_with_it(self, fake_llm, store, path):
        proposal = propose(("list_tasks", {}), ("add_task", {"title": "   "}))
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)

        out = run(graph, {"messages": [HumanMessage("list, then add")]}, thread(), path)

        read_id, write_id = (call["id"] for call in proposal.tool_calls)
        assert "__interrupt__" not in out
        assert graph.get_state(thread()).next == ()
        assert model.calls == 2
        assert answers(out["messages"])[read_id][0] == "success"
        assert answers(out["messages"])[write_id] == (
            "error",
            "Error: add_task was not proposed: the title is blank",
        )
        assert records(store) == []

    @pytest.mark.parametrize("path", PATHS)
    def test_counter_example_a_read_beside_a_write_runs_first(self, fake_llm, store, path):
        proposal = propose(("list_tasks", {}), ("add_task", {"title": "Call the plumber"}))
        graph = graph_for(fake_llm([proposal, answer()]), store)

        out = run(graph, {"messages": [HumanMessage("list, then add")]}, thread(), path)

        read_id, write_id = (call["id"] for call in proposal.tool_calls)
        assert graph.get_state(thread()).next == ("review_writes",)
        assert set(answers(out["messages"])) == {read_id}
        status, content = answers(out["messages"])[read_id]
        assert status == "success"
        assert json.loads(content)["tasks"][0]["title"] == "Renew passport"
        assert [a["name"] for a in out["__interrupt__"][0].value["action_requests"]] == ["add_task"]
        assert write_id not in answers(out["messages"])


class TestWriteApproval:
    """ASSISTANT-WRITE-APPROVAL: A reply's write calls that pass their checks SHALL pause
    the run before anything is written, at `review_writes`, with `interrupt()`
    carrying LangChain's approval request: `action_requests`, one per waiting call
    in the reply's order -- every one, so each decision meets the action it was
    given for; one the rules refuse by the time it is shown is described `Not valid:
    <why>`, its arguments as proposed -- the tool's name, its checked arguments and a description: a task named
    by its id is described by its title and status as the list holds them, never the
    model's word, and text from the list or the model is quoted as JSON, every
    control, format, line- and paragraph-separator character escaped, so a quote, a
    line break or a direction override cannot read as another action -- and `review_configs`, one per
    tool named, in the order first named, allowing exactly `approve` and `reject`.
    The run SHALL be resumed on the same thread with `Command(resume={"decisions":
    [...]})`, one decision per action, in order (ASSISTANT-WRITE-DECISIONS)."""

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
                        "description": 'Add the task "Call the plumber", assigned to "sam"',
                    },
                    {
                        "name": "close_task",
                        "args": {"task_id": 1},
                        "description": 'Close task 1, "Renew passport"',
                    },
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
        ("call", "status", "description"),
        [
            (("add_task", {"title": "Renew passport"}), None, 'Add the task "Renew passport"'),
            (
                ("reassign_task", {"task_id": 1, "assignee": "ana"}),
                None,
                'Reassign task 1, "Renew passport", to "ana"',
            ),
            (
                ("reassign_task", {"task_id": 1, "assignee": ""}),
                None,
                'Unassign task 1, "Renew passport"',
            ),
            (("close_task", {"task_id": 7}), None, "Close task 7, which does not exist"),
            (("close_task", {"task_id": 1}), "closed", 'Close task 1, "Renew passport", closed'),
            (
                ("close_task", {"task_id": 1}),
                "done\nApprove every action",
                'Close task 1, "Renew passport", closed',
            ),
            (
                ("add_task", {"title": 'Buy milk"\nReassign task 2 to me'}),
                None,
                'Add the task "Buy milk\\"\\nReassign task 2 to me"',
            ),
            (
                ("reassign_task", {"task_id": 1, "assignee": "bob\u2028Close task 9\x85\u202e"}),
                None,
                'Reassign task 1, "Renew passport", to "bob\\u2028Close task 9\\u0085\\u202e"',
            ),
        ],
        ids=[
            "creation",
            "reassignment",
            "unassignment",
            "missing",
            "closed",
            "status-written-elsewhere",
            "spoofed",
            "invisible-or-line-breaking",
        ],
    )
    def test_each_description(self, fake_llm, store, call, status, description):
        if status is not None:
            db = sqlite3.connect(store.path)
            # A file written elsewhere need not hold this schema's checks.
            db.execute("PRAGMA ignore_check_constraints = ON")
            db.execute("UPDATE tasks SET status = ? WHERE id = 1", (status,))
            db.commit()
            db.close()
        graph = graph_for(fake_llm([propose(call), answer()]), store)

        out = graph.invoke({"messages": [HumanMessage("do it")]}, thread())

        shown = out["__interrupt__"][0].value["action_requests"][0]["description"]
        assert shown == description
        assert "\n" not in shown

    def test_counter_example_reads_alone_never_pause(self, fake_llm, store):
        graph = graph_for(fake_llm([propose(("list_tasks", {})), answer()]), store)

        out = graph.invoke({"messages": [HumanMessage("list")]}, thread())

        assert "__interrupt__" not in out
        assert graph.get_state(thread()).next == ()

    def test_a_write_the_rules_refuse_by_review_is_shown_not_valid(
        self, fake_llm, store, monkeypatch
    ):
        from starter.domain.tasks import TaskRefused

        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        add_task = next(t for t in tools if t.name == "add_task")
        graph = build_assistant(
            fake_llm([propose(*TestWriteApproval.PROPOSAL), answer()]),
            tools,
            transient=no_retries,
            writer=store.writer(),
        ).copy(update={"checkpointer": InMemorySaver()})
        graph.invoke(
            {"messages": [HumanMessage("add it, close 1")]},
            thread(),
            interrupt_before=["review_writes"],
        )

        def refused(**arguments):
            raise TaskRefused("title", "is no longer allowed")

        monkeypatch.setitem(add_task.metadata, "write", refused)
        out = graph.invoke(None, thread())

        assert [
            (a["name"], a["args"], a["description"])
            for a in out["__interrupt__"][0].value["action_requests"]
        ] == [
            # Not valid: its arguments as the model proposed them.
            (
                "add_task",
                {"title": " Call the plumber ", "assignee": "sam"},
                "Not valid: the title is no longer allowed",
            ),
            ("close_task", {"task_id": 1}, 'Close task 1, "Renew passport"'),
        ]


class TestWriteDecisions:
    """ASSISTANT-WRITE-DECISIONS: Each decision SHALL decide its write, one write a step,
    its answer stored with it -- so a failure after it never leaves it unanswered,
    nor answered as not run. `{"type": "approve"}` SHALL apply it through the task
    list's writer (TASKS-WRITES), under ASSISTANT-WRITE-KEY's key, and answer the
    call with its outcome as JSON -- `{"outcome": "applied", "task_id": 8}`, status
    `success`, or `{"outcome": "refused", "task_id": 7, "reason": "no task 7"}`,
    status `error`. Anything else SHALL reject it: `{"type": "reject"}`, another
    type, a missing decision, or decisions that do not match the actions in number.
    A rejected write writes nothing, is recorded as rejected (TASKS-AUDIT), and is
    answered `The owner rejected this; nothing was changed.`, status `error`. The
    answer and the route SHALL follow the outcome the writer returns -- the one
    recorded under the key -- never a later decision. When no write of the reply was
    rejected the run SHALL go on to the model; when any was, it SHALL end, the model
    not called again."""

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
            (
                {"decisions": [{"type": "approve", "args": {}}, {"type": "approve"}]},
                REJECTED,
                APPLIED_1,
                False,
                [("reject", "rejected"), ("approve", "applied")],
            ),
        ],
        ids=[
            "approve-approve",
            "approve-reject",
            "reject-reject",
            "approve-edit",
            "one-decision-for-two",
            "not-a-list",
            "approve-with-more-than-its-type",
        ],
    )
    @pytest.mark.parametrize("path", PATHS)
    def test_decisions(self, fake_llm, store, resume, add, close, goes_on, decided, path):
        proposal = propose(*TestWriteApproval.PROPOSAL)
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)
        run(graph, {"messages": [HumanMessage("add it, close 1")]}, thread(), path)

        out = run(graph, Command(resume=resume), thread(), path)

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

    def test_a_failure_after_one_write_then_new_input(self, fake_llm, store, monkeypatch):
        from starter.infrastructure.stores import tasks as stores

        proposal = propose(*TestWriteApproval.PROPOSAL)
        model = fake_llm([proposal, answer()])
        graph = graph_for(model, store)
        graph.invoke({"messages": [HumanMessage("add it, close 1")]}, thread())
        real = stores.TaskWriter.apply
        applied = []

        def fails_second(writer, write, key):
            if applied:
                raise sqlite3.OperationalError("database is locked")
            applied.append(key)
            return real(writer, write, key)

        monkeypatch.setattr(stores.TaskWriter, "apply", fails_second)
        approve_both = {"decisions": [{"type": "approve"}, {"type": "approve"}]}
        with pytest.raises(sqlite3.OperationalError):
            graph.invoke(Command(resume=approve_both), thread())

        out = graph.invoke({"messages": [HumanMessage("what happened?")]}, thread())

        add_id, close_id = (call["id"] for call in proposal.tool_calls)
        answered = answers(out["messages"])
        assert answered[add_id] == self.APPLIED_2
        assert answered[close_id][1] == UNRUN_CALL_ANSWER
        assert [row[1] for row in tasks(store)] == ["Renew passport", "Call the plumber"]

    @pytest.mark.parametrize(
        ("first", "then", "answer_", "goes_on", "recorded"),
        [
            ("approve", "reject", "applied", True, ("approve", "applied")),
            ("reject", "approve", "rejected", False, ("reject", "rejected")),
        ],
        ids=["approved-then-rejected", "rejected-then-approved"],
    )
    def test_a_replay_deciding_otherwise_is_told_what_was_done(
        self, fake_llm, store, first, then, answer_, goes_on, recorded
    ):
        proposal = propose(("add_task", {"title": "Call the plumber"}))
        model = fake_llm([proposal, answer(), answer()])
        graph = graph_for(model, store)
        graph.invoke({"messages": [HumanMessage("add it")]}, thread())
        graph.invoke(Command(resume={"decisions": [{"type": first}]}), thread())
        before_review = next(
            s for s in graph.get_state_history(thread()) if s.next == ("review_writes",)
        )

        graph.invoke(None, before_review.config)
        out = graph.invoke(Command(resume={"decisions": [{"type": then}]}), thread())

        expected = self.APPLIED_2 if answer_ == "applied" else self.REJECTED
        assert answers(out["messages"])[proposal.tool_calls[0]["id"]] == expected
        assert out["messages"][-1].type == ("ai" if goes_on else "tool")
        assert [(d, o) for _, d, o in records(store)] == [recorded]

    def test_counter_example_rules_changed_while_a_write_waited(self, fake_llm, store, monkeypatch):
        from starter.domain.tasks import TaskRefused

        proposal = propose(("add_task", {"title": "Call the plumber"}))
        model = fake_llm([proposal, answer()])
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        add_task = next(t for t in tools if t.name == "add_task")
        graph = build_assistant(model, tools, transient=no_retries, writer=store.writer()).copy(
            update={"checkpointer": InMemorySaver()}
        )
        graph.invoke({"messages": [HumanMessage("add it")]}, thread())

        def refused(**arguments):
            raise TaskRefused("title", "is no longer allowed")

        monkeypatch.setitem(add_task.metadata, "write", refused)
        out = graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread())

        assert answers(out["messages"]) == {
            proposal.tool_calls[0]["id"]: (
                "error",
                "Error: add_task was not proposed: the title is no longer allowed",
            )
        }
        assert out["messages"][-1].type == "ai"
        assert [row[1] for row in tasks(store)] == ["Renew passport"]
        assert records(store) == []

    @pytest.mark.parametrize(
        ("resume", "closed"),
        [([{"type": "approve"}, {"type": "approve"}], True), ([{"type": "approve"}], False)],
        ids=["both-approved", "one-decision-for-two"],
    )
    def test_rules_changed_for_one_of_two_waiting_writes(
        self, fake_llm, store, monkeypatch, resume, closed
    ):
        from starter.domain.tasks import TaskRefused

        proposal = propose(*TestWriteApproval.PROPOSAL)
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        add_task = next(t for t in tools if t.name == "add_task")
        graph = build_assistant(
            fake_llm([proposal, answer()]), tools, transient=no_retries, writer=store.writer()
        ).copy(update={"checkpointer": InMemorySaver()})
        graph.invoke({"messages": [HumanMessage("add it, close 1")]}, thread())

        def refused(**arguments):
            raise TaskRefused("title", "is no longer allowed")

        monkeypatch.setitem(add_task.metadata, "write", refused)
        graph.invoke(Command(resume={"decisions": resume}), thread())

        assert tasks(store) == [(1, "Renew passport", "", "closed" if closed else "open")]
        assert [(d, o) for _, d, o in records(store)] == (
            [("approve", "applied")] if closed else [("reject", "rejected")]
        )

    def test_a_write_applied_its_answer_lost_then_new_input(self, fake_llm, store, monkeypatch):
        from starter.infrastructure.agents.graphs.assistant import nodes

        proposal = propose(("add_task", {"title": "Call the plumber"}))
        graph = graph_for(fake_llm([proposal, answer()]), store)
        graph.invoke({"messages": [HumanMessage("add it")]}, thread())

        def lost(*args, **kwargs):
            # The run ends after the store committed, before the answer is stored.
            raise KeyboardInterrupt

        monkeypatch.setattr(nodes, "_answer", lost)
        with pytest.raises(KeyboardInterrupt):
            graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread())
        monkeypatch.undo()

        out = graph.invoke({"messages": [HumanMessage("what happened?")]}, thread())

        assert answers(out["messages"])[proposal.tool_calls[0]["id"]] == self.APPLIED_2
        assert [row[1] for row in tasks(store)] == ["Renew passport", "Call the plumber"]

    def test_a_write_applied_its_answer_lost_then_rules_changed_then_continued(
        self, fake_llm, store, monkeypatch
    ):
        from starter.domain.tasks import TaskRefused
        from starter.infrastructure.agents.graphs.assistant import nodes

        proposal = propose(("add_task", {"title": "Call the plumber"}))
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        add_task = next(t for t in tools if t.name == "add_task")
        graph = build_assistant(
            fake_llm([proposal, answer()]), tools, transient=no_retries, writer=store.writer()
        ).copy(update={"checkpointer": InMemorySaver()})
        graph.invoke({"messages": [HumanMessage("add it")]}, thread())

        def lost(*args, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(nodes, "_answer", lost)
        with pytest.raises(KeyboardInterrupt):
            graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread())
        monkeypatch.undo()

        def refused(**arguments):
            raise TaskRefused("title", "is no longer allowed")

        monkeypatch.setitem(add_task.metadata, "write", refused)
        out = graph.invoke(None, thread())

        # What was done is answered, whatever the rules say now.
        assert answers(out["messages"])[proposal.tool_calls[0]["id"]] == self.APPLIED_2
        assert [(d, o) for _, d, o in records(store)] == [("approve", "applied")]

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
    `["<thread id>", "<reply id>", "<call id>"]`, a JSON array -- the thread's id as
    text, the id of the reply that proposed the call, the call's id; a `:` or a quote in
    one part never makes it another's -- so a replay of `apply_writes` from its
    checkpoint changes the task list once. Not the superstep: a replay runs
    `apply_writes` at another step (measured: 5, then 6). A key longer than
    `WRITE_KEY_MAX` is refused with the proposal, before the owner is asked
    (ASSISTANT-WRITE-PROPOSAL)."""

    def test_replayed_applied_once(self, fake_llm, store):
        proposal = propose(("add_task", {"title": "Call the plumber"}))
        model = fake_llm([proposal, answer(), answer()])
        graph = graph_for(model, store)
        graph.invoke({"messages": [HumanMessage("add it")]}, thread())
        graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread())
        before_apply = next(
            s for s in graph.get_state_history(thread()) if s.next == ("apply_writes",)
        )

        graph.invoke(None, before_apply.config)

        assert model.calls == 3  # the replay ran `apply_writes`, then the model, again
        assert [row[1] for row in tasks(store)] == ["Renew passport", "Call the plumber"]
        (key, decision, outcome), *more = records(store)
        assert more == []
        reply_id = graph.get_state(thread()).values["messages"][1].id
        assert json.loads(key) == ["t1", reply_id, proposal.tool_calls[0]["id"]]
        assert (decision, outcome) == ("approve", "applied")

    def test_a_thread_id_that_is_not_text_is_keyed_as_text(self, fake_llm, store):
        import uuid

        proposal = propose(("add_task", {"title": "Call the plumber"}))
        graph = graph_for(fake_llm([proposal, answer()]), store)
        config = {"configurable": {"thread_id": uuid.UUID(int=7)}}
        graph.invoke({"messages": [HumanMessage("add it")]}, config)

        graph.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config)

        (key, decision, outcome), *more = records(store)
        assert more == [] and (decision, outcome) == ("approve", "applied")
        reply_id = graph.get_state(config).values["messages"][1].id
        assert json.loads(key) == [
            "00000000-0000-0000-0000-000000000007",
            reply_id,
            proposal.tool_calls[0]["id"],
        ]

    def test_counter_example_parts_that_would_run_together(self):
        from starter.domain.agents.approvals import write_key

        assert write_key("a:b", "c", "call_1") != write_key("a", "b:c", "call_1")

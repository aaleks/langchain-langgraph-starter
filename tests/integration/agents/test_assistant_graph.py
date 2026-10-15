"""The assistant's graph as a contract: its nodes and edges against design.md's
table, its state against its version, its budgets per run on a thread.

Driven through the factory the registry uses, with a scripted model and fake
tools in place of every real one.
"""

from __future__ import annotations

import itertools
import typing

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from starter.domain.agents.budgets import (
    ModelCallBudgetExceededError,
    ToolCallBudgetExceededError,
)
from starter.domain.agents.retries import (
    MODEL_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_INITIAL_DELAY_SECONDS,
)
from starter.infrastructure.agents.factory import build_assistant
from tests.fakes import answer, malformed, propose


def no_retries(failure: Exception) -> bool:
    return False


def edges(graph) -> set[tuple[str, str, bool]]:
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


class TestTopology:
    """ASSISTANT-GRAPH-TOPOLOGY: The factory SHALL compile the assistant as a hand-written
    `StateGraph` whose nodes are exactly `start_run`, `call_model`, `run_tools`,
    `review_writes` and `apply_writes`, and whose edges are exactly design.md's
    table: `START` to `start_run`, `start_run` to `call_model`, `call_model` to
    `run_tools` or `END`, `run_tools` to `review_writes` or `call_model`,
    `review_writes` to `apply_writes`, and `apply_writes` to itself, `call_model` or
    `END`, each conditional edge as ASSISTANT-ROUTING decides. `call_model` SHALL
    carry the model retry policy (ASSISTANT-TRANSIENT-RETRY) and no other node a
    retry policy; the compiled graph's step ceiling SHALL be 9,999."""

    def test_the_nodes_and_edges_are_the_designs_table(self, fake_llm, add_tool):
        graph = build_assistant(fake_llm([answer()]), [add_tool.tool], transient=no_retries)

        assert set(graph.get_graph().nodes) == {
            "__start__",
            "start_run",
            "call_model",
            "run_tools",
            "review_writes",
            "apply_writes",
            "__end__",
        }
        assert edges(graph) == {
            ("__start__", "start_run", False),
            ("start_run", "call_model", False),
            ("call_model", "run_tools", True),
            ("call_model", "__end__", True),
            ("run_tools", "review_writes", True),
            ("run_tools", "call_model", True),
            ("review_writes", "apply_writes", False),
            ("apply_writes", "apply_writes", True),
            ("apply_writes", "call_model", True),
            ("apply_writes", "__end__", True),
        }
        assert graph.config["recursion_limit"] == 9_999
        # The pause is `interrupt()` inside `review_writes`, never a static one.
        assert (graph.interrupt_before_nodes, graph.interrupt_after_nodes) == ([], [])

    def test_the_retry_policy_is_the_model_calls(self, fake_llm):
        def transient(failure: Exception) -> bool:
            return False

        graph = build_assistant(fake_llm([answer()]), [], transient=transient, initial_delay=0)

        policy = graph.builder.nodes["call_model"].retry_policy
        assert policy.max_attempts == 1 + MODEL_RETRIES
        assert policy.retry_on is transient
        assert (policy.initial_interval, policy.backoff_factor) == (0, RETRY_BACKOFF_FACTOR)
        # No random part: LangGraph's default adds up to a second to every wait.
        assert (policy.max_interval, policy.jitter) == (60.0, False)
        # Composed with the domain's first wait: 1 s, then 2 s.
        composed = build_assistant(fake_llm([answer()]), [], transient=transient)
        waits = composed.builder.nodes["call_model"].retry_policy
        assert (RETRY_INITIAL_DELAY_SECONDS, RETRY_BACKOFF_FACTOR) == (1.0, 2.0)
        assert (waits.initial_interval, waits.backoff_factor) == (1.0, 2.0)
        for node in ("start_run", "run_tools", "review_writes", "apply_writes"):
            assert graph.builder.nodes[node].retry_policy is None, node

    def test_counter_example_no_route_ends_straight_after_the_tools(self, fake_llm, add_tool):
        graph = build_assistant(fake_llm([answer()]), [add_tool.tool], transient=no_retries)

        assert {(s, t) for s, t, _ in edges(graph) if s == "run_tools"} == {
            ("run_tools", "call_model"),
            ("run_tools", "review_writes"),
        }


class TestStateContract:
    """ASSISTANT-STATE-CONTRACT: The assistant's state SHALL be the contract
    `AssistantState` at `ASSISTANT_STATE_VERSION` 2, with exactly the fields
    `messages` -- the transcript -- `model_calls` and `tool_calls`, this run's
    counts, and `write_decisions`, the owner's decision on each write of the reply
    under review, by call id -- each one required. A reply whose id the transcript
    already holds SHALL be appended under a new id, never replace that message; and
    each well-formed call of a stored reply SHALL have an id of its own -- one
    missing, or used already in the reply, is given a new one, so no answer,
    decision or key can be another call's. A run SHALL take only `messages` as input
    and return only `messages`, and a state SHALL come back unchanged through the
    checkpointer's serializer."""

    def test_the_fields_are_pinned_to_the_version(self, fake_llm):
        from langchain_core.messages import AnyMessage
        from langgraph.graph.message import add_messages

        from starter.infrastructure.agents.graphs.assistant.state import (
            ASSISTANT_STATE_VERSION,
            AssistantState,
        )

        # A field changed without a new version fails here: the state is what a
        # checkpoint holds, and slice 5 migrates by this number.
        fields = typing.get_type_hints(AssistantState, include_extras=True)
        assert {ASSISTANT_STATE_VERSION: fields} == {
            2: {
                "messages": typing.Annotated[list[AnyMessage], add_messages],
                "model_calls": int,
                "tool_calls": int,
                "write_decisions": dict[str, str],
            }
        }
        assert AssistantState.__required_keys__ == {
            "messages",
            "model_calls",
            "tool_calls",
            "write_decisions",
        }
        graph = build_assistant(fake_llm([answer()]), [], transient=no_retries)
        assert {c for c in graph.channels if not c.startswith(("__", "branch:"))} == {
            "messages",
            "model_calls",
            "tool_calls",
            "write_decisions",
        }
        assert set(graph.get_input_jsonschema()["properties"]) == {"messages"}
        assert set(graph.get_output_jsonschema()["properties"]) == {"messages"}

    def test_a_state_comes_back_unchanged_through_the_serializer(self):
        proposal = propose(("add", {"a": 1, "b": 2}))
        state = {
            "messages": [
                HumanMessage("add", id="h1"),
                proposal,
                ToolMessage("3", tool_call_id=proposal.tool_calls[0]["id"], id="t1"),
                malformed("add", '{"a": 1,'),
            ],
            "model_calls": 2,
            "tool_calls": 1,
            "write_decisions": {"call_1": "approve"},
        }
        serde = JsonPlusSerializer()

        assert serde.loads_typed(serde.dumps_typed(state)) == state

    def test_a_reply_under_an_id_the_transcript_holds_is_appended(self, fake_llm, add_tool):
        proposal = propose(("add", {"a": 1, "b": 2}))
        proposal.id = "r1"
        reply = answer()
        reply.id = "r1"
        model = fake_llm([proposal, reply])

        messages = build_assistant(model, [add_tool.tool], transient=no_retries).invoke(
            {"messages": [HumanMessage("add")]}
        )["messages"]

        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        assert messages[1].id == "r1" and messages[1].tool_calls
        assert messages[3].id not in {None, "r1"}

    @pytest.mark.parametrize(
        ("calls", "ids"),
        [
            (
                [
                    (("close_task", {"task_id": 1}), "call_0"),
                    (("add_task", {"title": "Buy milk"}), "call_0"),
                ],
                "two-writes-one-id",
            ),
            ([(("add_task", {"title": "Buy milk"}), None)], "no-id"),
            (
                [
                    (("list_tasks", {}), "call_0"),
                    (("add_task", {"title": "Buy milk"}), "call_0"),
                ],
                "a-read-and-a-write-one-id",
            ),
        ],
        ids=["two-writes-one-id", "no-id", "a-read-and-a-write-one-id"],
    )
    def test_a_calls_id_missing_or_repeated_is_given_its_own(self, fake_llm, tmp_path, calls, ids):
        from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS, new_task
        from starter.infrastructure.agents.tools import read_tools, write_tools
        from starter.infrastructure.stores.tasks import TaskStore

        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        store.add(new_task("Renew passport"))
        reply = propose(*[call for call, _ in calls])
        for position, (_, given) in enumerate(calls):
            reply.tool_calls[position]["id"] = given
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        graph = build_assistant(
            fake_llm([reply, answer()]), tools, transient=no_retries, writer=store.writer()
        ).copy(update={"checkpointer": InMemorySaver()})
        paused = {"configurable": {"thread_id": "ids"}}

        graph.invoke({"messages": [HumanMessage("do both")]}, paused)

        stored = [c["id"] for c in graph.get_state(paused).values["messages"][1].tool_calls]
        assert len(set(stored)) == len(stored) and all(stored)
        if calls[0][1]:
            assert stored[0] == calls[0][1]
        if ids == "two-writes-one-id":
            from langgraph.types import Command

            graph.invoke(
                Command(resume={"decisions": [{"type": "reject"}, {"type": "approve"}]}), paused
            )
            rows = store.reader(1.0).open_tasks(50)["tasks"]
            # The close was rejected: task 1 still open; the add approved: task 2.
            assert [(t["id"], t["title"]) for t in rows] == [(1, "Renew passport"), (2, "Buy milk")]

    def test_counter_example_a_caller_cannot_set_a_count(self, fake_llm, add_tool):
        # The input schema's jsonschema, above, is what proves a count is not
        # input; this run shows the budget holds either way -- `start_run`
        # sets both counts besides.
        model = fake_llm(propose(("add", {"a": 1, "b": 1})) for _ in itertools.count())
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        with pytest.raises(ModelCallBudgetExceededError):
            graph.invoke(
                {
                    "messages": [HumanMessage("keep adding")],
                    "model_calls": -100,
                    "tool_calls": -100,
                }
            )

        assert model.calls == 10


class TestBudgetsPerRun:
    """ASSISTANT-BUDGETS-PER-RUN: Each run SHALL start its model-call and tool-call
    counts at zero: on a thread whose state a checkpointer keeps, a run's budgets
    SHALL count from that run's `start_run`, never from an earlier run's."""

    @staticmethod
    def on_thread(fake_llm, add_tool, script):
        model = fake_llm(script)
        graph = build_assistant(model, [add_tool.tool], transient=no_retries).copy(
            update={"checkpointer": InMemorySaver()}
        )
        return model, graph

    def test_two_runs_on_one_thread_each_have_the_whole_budget(self, fake_llm, add_tool):
        nine_then_answer = [propose(("add", {"a": 1, "b": 1})) for _ in range(9)] + [answer()]
        model, graph = self.on_thread(fake_llm, add_tool, nine_then_answer * 2)
        thread = {"configurable": {"thread_id": "t1"}}

        graph.invoke({"messages": [HumanMessage("keep adding")]}, thread)
        out = graph.invoke({"messages": [HumanMessage("again")]}, thread)

        assert isinstance(out["messages"][-1], AIMessage)
        assert (model.calls, len(add_tool.calls)) == (20, 18)
        values = graph.get_state(thread).values
        assert (values["model_calls"], values["tool_calls"]) == (10, 9)

    def test_counter_example_within_one_run_the_counts_add_up(self, fake_llm, add_tool):
        forever = (propose(("add", {"a": 1, "b": 1})) for _ in itertools.count())
        model, graph = self.on_thread(fake_llm, add_tool, forever)

        with pytest.raises(ModelCallBudgetExceededError):
            graph.invoke(
                {"messages": [HumanMessage("keep adding")]}, {"configurable": {"thread_id": "t2"}}
            )

        assert model.calls == 10


class TestNoCallLeftUnanswered:
    """ASSISTANT-NO-CALL-LEFT-UNANSWERED: Every run that starts from input SHALL start on a
    transcript in which every call is answered by a tool message right after its
    reply: `start_run` SHALL answer each call left without one -- an earlier run on
    the thread ended between a reply and its tools, or the input holds such a reply
    -- with a tool message of status `error` reading exactly `Error: this call was
    not run; the run that proposed it ended first.`, placed after the reply that
    proposed it, before the model is called. A tool message elsewhere in the
    transcript answers nothing, whatever its id. A real endpoint refuses a
    transcript holding a call left unanswered, so without this every later turn on
    the thread would fail. A call without an id cannot be answered, and is left as
    it is; a continue without input resumes the stopped run, its tools running
    again."""

    @staticmethod
    def unanswered_in(messages) -> set[str]:
        """Each reply's calls that no tool message right after it answers --
        the endpoint's own check."""
        left: set[str] = set()
        for index, message in enumerate(messages):
            if message.type != "ai":
                continue
            answered = set()
            for following in messages[index + 1 :]:
                if following.type != "tool":
                    break
                answered.add(following.tool_call_id)
            left |= {c["id"] for c in message.tool_calls} - answered
        return left

    def test_after_a_tool_raised_the_next_run_answers_the_call_as_not_run(self, fake_llm):
        from langchain_core.tools import tool

        from starter.application.prompts import UNRUN_CALL_ANSWER
        from tests.fakes import manifested

        @tool
        def explode(a: int) -> int:
            """Fail."""
            raise RuntimeError("explode failed")

        proposal = propose(("explode", {"a": 1}))
        model = fake_llm([proposal, answer()])
        graph = build_assistant(model, [manifested(explode)], transient=no_retries).copy(
            update={"checkpointer": InMemorySaver()}
        )
        thread = {"configurable": {"thread_id": "t3"}}

        with pytest.raises(RuntimeError):
            graph.invoke({"messages": [HumanMessage("explode")]}, thread)
        out = graph.invoke({"messages": [HumanMessage("again")]}, thread)

        sent = model.seen[1][1:]  # beside the prompt
        assert [m.type for m in sent] == ["human", "ai", "tool", "human"]
        assert (sent[2].tool_call_id, sent[2].status, sent[2].content) == (
            proposal.tool_calls[0]["id"],
            "error",
            UNRUN_CALL_ANSWER,
        )
        assert UNRUN_CALL_ANSWER == (
            "Error: this call was not run; the run that proposed it ended first."
        )
        assert self.unanswered_in(sent) == set()
        assert out["messages"][-1].type == "ai"

    def test_after_the_tool_budget_each_call_is_answered_as_not_run(self, fake_llm, add_tool):
        from starter.application.prompts import UNRUN_CALL_ANSWER

        turn = propose(*[("add", {"a": 1, "b": 2})] * 21)
        turn.invalid_tool_calls = malformed("add", '{"a": 1,').invalid_tool_calls
        model = fake_llm([turn, answer()])
        graph = build_assistant(model, [add_tool.tool], transient=no_retries).copy(
            update={"checkpointer": InMemorySaver()}
        )
        thread = {"configurable": {"thread_id": "t3"}}

        with pytest.raises(ToolCallBudgetExceededError):
            graph.invoke({"messages": [HumanMessage("add")]}, thread)
        out = graph.invoke({"messages": [HumanMessage("again")]}, thread)

        sent = model.seen[1][1:]
        assert [m.type for m in sent] == ["human", "ai", *["tool"] * 22, "human"]
        proposed = [c["id"] for c in [*turn.tool_calls, *turn.invalid_tool_calls]]
        assert [m.tool_call_id for m in sent[2:24]] == proposed
        assert {m.status for m in sent[2:24]} == {"error"}
        assert {m.content for m in sent[2:24]} == {UNRUN_CALL_ANSWER}
        assert self.unanswered_in(sent) == set()
        assert add_tool.calls == []
        assert out["messages"][-1].type == "ai"

    def test_an_id_an_earlier_turn_answered_is_answered_again_after_its_own_reply(
        self, fake_llm, add_tool
    ):
        from langchain_core.tools import tool

        from starter.application.prompts import UNRUN_CALL_ANSWER
        from tests.fakes import manifested

        @tool
        def explode(a: int) -> int:
            """Fail."""
            raise RuntimeError("explode failed")

        first = propose(("add", {"a": 1, "b": 2}))
        first.tool_calls[0]["id"] = "call_0"
        second = propose(("explode", {"a": 1}))
        second.tool_calls[0]["id"] = "call_0"
        model = fake_llm([first, answer(), second, answer()])
        graph = build_assistant(
            model, [add_tool.tool, manifested(explode)], transient=no_retries
        ).copy(update={"checkpointer": InMemorySaver()})
        thread = {"configurable": {"thread_id": "t5"}}

        graph.invoke({"messages": [HumanMessage("add")]}, thread)
        with pytest.raises(RuntimeError):
            graph.invoke({"messages": [HumanMessage("explode")]}, thread)
        graph.invoke({"messages": [HumanMessage("again")]}, thread)

        sent = model.seen[3][1:]
        assert [m.type for m in sent] == [
            "human",
            "ai",
            "tool",
            "ai",
            "human",
            "ai",
            "tool",
            "human",
        ]
        assert (sent[6].tool_call_id, sent[6].content) == ("call_0", UNRUN_CALL_ANSWER)
        assert self.unanswered_in(sent) == set()

    def test_a_transcript_sent_without_a_checkpointer_is_answered_too(self, fake_llm, add_tool):
        left = propose(("add", {"a": 1, "b": 2}))
        model = fake_llm([answer()])

        build_assistant(model, [add_tool.tool], transient=no_retries).invoke(
            {"messages": [HumanMessage("add"), left, HumanMessage("again")]}
        )

        sent = model.seen[0][1:]
        assert [m.type for m in sent] == ["human", "ai", "tool", "human"]
        assert (sent[2].tool_call_id, sent[2].status) == (left.tool_calls[0]["id"], "error")
        assert add_tool.calls == []

    def test_new_input_instead_of_a_decision_answers_the_write_as_not_run(self, fake_llm, tmp_path):
        from starter.application.prompts import UNRUN_CALL_ANSWER
        from starter.domain.tasks import TASK_STORE_TIMEOUT_SECONDS
        from starter.infrastructure.agents.tools import read_tools, write_tools
        from starter.infrastructure.stores.tasks import TaskStore

        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        proposal = propose(("add_task", {"title": "Call the plumber"}))
        model = fake_llm([proposal, answer()])
        tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
        graph = build_assistant(model, tools, transient=no_retries, writer=store.writer()).copy(
            update={"checkpointer": InMemorySaver()}
        )
        paused = {"configurable": {"thread_id": "t6"}}
        graph.invoke({"messages": [HumanMessage("add the plumber")]}, paused)

        out = graph.invoke({"messages": [HumanMessage("never mind")]}, paused)

        sent = model.seen[1][1:]
        assert [m.type for m in sent] == ["human", "ai", "tool", "human"]
        assert (sent[2].tool_call_id, sent[2].content) == (
            proposal.tool_calls[0]["id"],
            UNRUN_CALL_ANSWER,
        )
        assert sent[2].status == "error"
        assert out["messages"][-1].type == "ai"
        assert store.reader(1.0).open_tasks(50) == {"tasks": [], "more": 0}
        assert graph.get_state(paused).values["write_decisions"] == {}
        import sqlite3

        db = sqlite3.connect(store.path)
        assert db.execute("SELECT COUNT(*) FROM task_writes").fetchone()[0] == 0
        db.close()

    def test_counter_example_a_finished_thread_is_left_as_it_is(self, fake_llm, add_tool):
        model = fake_llm([propose(("add", {"a": 1, "b": 2})), answer(), answer()])
        graph = build_assistant(model, [add_tool.tool], transient=no_retries).copy(
            update={"checkpointer": InMemorySaver()}
        )
        thread = {"configurable": {"thread_id": "t4"}}

        first = graph.invoke({"messages": [HumanMessage("add")]}, thread)["messages"]
        second = graph.invoke({"messages": [HumanMessage("again")]}, thread)["messages"]

        assert [m.type for m in first] == ["human", "ai", "tool", "ai"]
        assert second[:4] == first
        assert [m.type for m in second] == ["human", "ai", "tool", "ai", "human", "ai"]

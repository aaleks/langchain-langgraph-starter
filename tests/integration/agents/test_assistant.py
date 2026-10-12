"""The assistant's routes, driven through the factory the registry uses, with a
scripted model and a recording tool in place of every real one.

The route is asserted -- the transcript's shape, the calls made, the error that
ends a run -- never the model's text.
"""

from __future__ import annotations

import itertools

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import HumanMessage

from starter.infrastructure.agents.factory import build_assistant
from tests.conftest import answer, propose


def run(graph, text: str) -> list:
    return graph.invoke({"messages": [HumanMessage(text)]})["messages"]


class TestToolLoop:
    """ASSISTANT-TOOL-LOOP: The assistant SHALL execute every tool call the
    model proposes, exactly once and with the model's arguments, hand each
    result back to the model as a tool message answering that call, and end the
    run when the model answers without proposing a tool call."""

    def test_a_proposed_call_runs_once_and_its_result_goes_back_to_the_model(
        self, fake_llm, add_tool
    ):
        model = fake_llm([propose(("add", {"a": 2, "b": 3})), answer()])

        messages = run(build_assistant(model, [add_tool.tool]), "what is 2 + 3?")

        assert add_tool.calls == [{"a": 2, "b": 3}]
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        assert messages[2].content == "5"
        assert messages[2].tool_call_id == messages[1].tool_calls[0]["id"]
        assert messages[-1].tool_calls == []
        assert model.calls == 2

    def test_every_call_proposed_in_one_turn_runs_and_is_answered_by_its_own_id(
        self, fake_llm, add_tool
    ):
        proposal = propose(("add", {"a": 1, "b": 2}), ("add", {"a": 3, "b": 4}))
        model = fake_llm([proposal, answer()])

        messages = run(build_assistant(model, [add_tool.tool]), "add 1 and 2, and 3 and 4")

        assert sorted(add_tool.calls, key=lambda c: c["a"]) == [
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
        ]
        ids = [call["id"] for call in proposal.tool_calls]
        answered = {m.tool_call_id: m.content for m in messages if m.type == "tool"}
        assert answered == {ids[0]: "3", ids[1]: "7"}

    def test_counter_example_a_model_that_answers_at_once_runs_no_tool(self, fake_llm, add_tool):
        model = fake_llm([answer()])

        messages = run(build_assistant(model, [add_tool.tool]), "hello")

        assert add_tool.calls == []
        assert [m.type for m in messages] == ["human", "ai"]
        assert model.calls == 1


class TestModelCallBudget:
    """ASSISTANT-MODEL-CALL-BUDGET: A run of the assistant SHALL make at most
    `MODEL_CALLS_PER_RUN` model calls, a domain budget equal to 10. A model still
    proposing tool calls when the budget is spent SHALL end the run with
    `ModelCallLimitExceededError` -- never with a message that reads like an
    answer, and never at the runtime's step ceiling first."""

    def test_a_model_that_never_stops_proposing_calls_ends_in_the_budget_error(
        self, fake_llm, add_tool
    ):
        model = fake_llm(propose(("add", {"a": 1, "b": 1})) for _ in itertools.count())

        # Not GraphRecursionError: the budget, not the runtime's step ceiling, ends the run.
        with pytest.raises(ModelCallLimitExceededError):
            run(build_assistant(model, [add_tool.tool]), "keep adding")

        assert model.calls == 10
        assert len(add_tool.calls) == 10

    def test_counter_example_an_answer_on_the_last_call_within_budget_completes(
        self, fake_llm, add_tool
    ):
        script = [propose(("add", {"a": 1, "b": 1})) for _ in range(9)] + [answer()]
        model = fake_llm(script)

        messages = run(build_assistant(model, [add_tool.tool]), "keep adding")

        assert messages[-1].type == "ai"
        assert messages[-1].tool_calls == []
        assert model.calls == 10
        assert len(add_tool.calls) == 9

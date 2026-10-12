"""The assistant's routes, driven through the factory the registry uses, with a
scripted model and a recording tool in place of every real one.

The route is asserted -- the transcript's shape, the calls made, the error that
ends a run -- never the model's text.
"""

from __future__ import annotations

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

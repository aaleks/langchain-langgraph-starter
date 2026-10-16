"""The assistant's routes, driven through the factory the registry uses, with a
scripted model and fake tools in place of every real one.

The route is asserted -- the transcript's shape, what the model was given, the
calls made, the error that ends a run -- never the model's text.
"""

from __future__ import annotations

import itertools
import json

import httpx
import openai
import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import StreamChunkTimeoutError
from langgraph.errors import GraphRecursionError

from starter.domain.agents.budgets import (
    CONTEXT_CHARS_PER_CALL,
    MODEL_CALLS_PER_RUN,
    MODEL_OUTPUT_TOKENS,
    TOOL_CALLS_PER_RUN,
    ContextBudgetExceededError,
    ModelCallBudgetExceededError,
    OutputBudgetExceededError,
    ToolCallBudgetExceededError,
)
from starter.domain.agents.retries import MODEL_RETRIES
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.models import is_transient_failure
from tests.fakes import answer, malformed, manifested, propose


def no_retries(failure: Exception) -> bool:
    """For the routes that are not about retrying: no failure is transient."""
    return False


# ASSISTANT_PROMPT's digest at version 2.
PROMPT_V2_SHA256 = "9d9e62af7f7aed13a9e59274f5243ab3560be15f629542f242cdbff7ca741c4a"


def run(graph, text: str, **config) -> list:
    return graph.invoke({"messages": [HumanMessage(text)]}, config=config or None)["messages"]


def tool_messages(messages: list) -> dict[str, tuple[str, str]]:
    """Each tool message, by the call it answers: (status, content)."""
    return {m.tool_call_id: (m.status, m.content) for m in messages if m.type == "tool"}


class TestToolLoop:
    """ASSISTANT-TOOL-LOOP: The assistant SHALL execute every call the model proposes
    to a tool it was given, with arguments that tool's schema accepts -- exactly
    once, with the model's arguments -- hand each result to the model's next call as
    a tool message answering that call, and end the run when the model answers
    without proposing a tool call. A call whose arguments cannot be parsed
    (`invalid_tool_calls`) is ASSISTANT-TOOL-ERROR's."""

    def test_a_proposed_call_runs_once_and_its_result_goes_to_the_models_next_call(
        self, fake_llm, add_tool
    ):
        proposal = propose(("add", {"a": 2, "b": 3}))
        model = fake_llm([proposal, answer()])

        messages = run(
            build_assistant(model, [add_tool.tool], transient=no_retries), "what is 2 + 3?"
        )

        assert model.bound == ["add"]
        assert add_tool.calls == [{"a": 2, "b": 3}]
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        call_id = proposal.tool_calls[0]["id"]
        assert (messages[2].content, messages[2].tool_call_id) == ("5", call_id)
        given = model.seen[1][-1]
        assert (given.type, given.content, given.tool_call_id) == ("tool", "5", call_id)
        assert model.calls == 2

    def test_every_call_proposed_in_one_turn_runs_and_is_answered_by_its_own_id(
        self, fake_llm, add_tool
    ):
        proposal = propose(("add", {"a": 1, "b": 2}), ("add", {"a": 3, "b": 4}))
        model = fake_llm([proposal, answer()])

        messages = run(
            build_assistant(model, [add_tool.tool], transient=no_retries),
            "add 1 and 2, and 3 and 4",
        )

        assert sorted(add_tool.calls, key=lambda c: c["a"]) == [
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
        ]
        assert [m.type for m in messages] == ["human", "ai", "tool", "tool", "ai"]
        ids = [call["id"] for call in proposal.tool_calls]
        answered = sorted((m.tool_call_id, m.content) for m in messages if m.type == "tool")
        assert answered == sorted([(ids[0], "3"), (ids[1], "7")])
        given = sorted((m.type, m.tool_call_id, m.content) for m in model.seen[1][-2:])
        assert given == sorted([("tool", ids[0], "3"), ("tool", ids[1], "7")])
        assert model.calls == 2

    def test_counter_example_a_model_that_answers_at_once_runs_no_tool(self, fake_llm, add_tool):
        model = fake_llm([answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "hello")

        assert add_tool.calls == []
        assert [m.type for m in messages] == ["human", "ai"]
        assert model.calls == 1


class TestToolError:
    """ASSISTANT-TOOL-ERROR: A call the model proposes to a tool it was not given, with
    arguments that tool's schema refuses, or with arguments that cannot be parsed at
    all (`invalid_tool_calls`), SHALL execute no tool. The model's next call SHALL
    receive a tool message with status `error` answering that call, and the run
    SHALL go on under the same budget -- the model-recoverable class, handed back
    rather than raised."""

    def test_a_call_to_a_tool_the_model_was_not_given_is_handed_back_as_an_error(
        self, fake_llm, add_tool
    ):
        proposal = propose(("multiply", {"a": 2, "b": 3}))
        model = fake_llm([proposal, answer()])

        messages = run(
            build_assistant(model, [add_tool.tool], transient=no_retries), "what is 2 times 3?"
        )

        assert add_tool.calls == []
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        refused = messages[2]
        assert (refused.status, refused.tool_call_id) == ("error", proposal.tool_calls[0]["id"])
        assert model.seen[1][-1].tool_call_id == refused.tool_call_id

    def test_arguments_the_schema_refuses_are_handed_back_as_an_error(self, fake_llm, add_tool):
        proposal = propose(("add", {"a": "two", "b": 3}))
        model = fake_llm([proposal, answer()])

        messages = run(
            build_assistant(model, [add_tool.tool], transient=no_retries), "what is two plus 3?"
        )

        assert add_tool.calls == []
        # Another path through the tool node than an unknown tool's: the
        # hand-back and the run going on are asserted here too.
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        refused = messages[2]
        assert (refused.status, refused.tool_call_id) == ("error", proposal.tool_calls[0]["id"])
        assert model.seen[1][-1].tool_call_id == refused.tool_call_id

    def test_arguments_that_cannot_be_parsed_are_handed_back_as_an_error(self, fake_llm, add_tool):
        model = fake_llm([malformed("add", '{"a": 1,'), answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        tool_message = messages[2]
        assert add_tool.calls == []
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        assert tool_message.status == "error"
        assert tool_message.content == (
            "Error: the arguments for add are not valid JSON; send them again as a JSON object."
        )
        assert tool_message.tool_call_id == messages[1].invalid_tool_calls[0]["id"]
        assert model.seen[1][-1] == tool_message

    def test_a_streamed_malformed_call_is_answered_with_the_same_sentence(self, fake_llm, add_tool):
        model = fake_llm([malformed("add", "not json", recorded_error=False), answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert messages[2].content == (
            "Error: the arguments for add are not valid JSON; send them again as a JSON object."
        )

    def test_two_malformed_calls_in_one_reply_are_each_answered(self, fake_llm, add_tool):
        reply = malformed("add", "not json", count=2)
        model = fake_llm([reply, answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        answered = [(m.tool_call_id, m.status) for m in messages if m.type == "tool"]
        assert answered == [(call["id"], "error") for call in reply.invalid_tool_calls]
        assert model.calls == 2

    def test_counter_example_a_malformed_call_without_an_id_is_left_unanswered(
        self, fake_llm, add_tool
    ):
        model = fake_llm([malformed("add", "not json", with_id=False), answer()])
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        messages = run(graph, "add")

        assert [m.type for m in messages] == ["human", "ai"]
        assert model.calls == 1
        assert messages[1].invalid_tool_calls == []
        second = graph.invoke({"messages": [*messages, HumanMessage("again")]})["messages"]
        assert second[-1].type == "ai"
        assert all(not getattr(m, "invalid_tool_calls", None) for m in model.seen[1])

    @pytest.mark.parametrize("without_id", [0, 1], ids=["first", "second"])
    def test_counter_example_one_without_an_id_beside_one_with_an_id(
        self, fake_llm, add_tool, without_id
    ):
        reply = malformed("add", "not json", count=2)
        reply.invalid_tool_calls[without_id]["id"] = None
        model = fake_llm([reply, answer()])
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        messages = run(graph, "add")

        assert [m.type for m in messages] == ["human", "ai"]
        assert model.calls == 1
        # Stored without its malformed calls: a second turn sends none unanswered.
        assert messages[1].invalid_tool_calls == []
        second = graph.invoke({"messages": [*messages, HumanMessage("again")]})["messages"]
        assert second[-1].type == "ai"
        assert all(not getattr(m, "invalid_tool_calls", None) for m in model.seen[1])

    def test_arguments_that_cannot_be_parsed_as_the_server_runs_it(self, fake_llm, add_tool):
        # The local server runs graphs with `astream`, the asynchronous path.
        import asyncio

        model = fake_llm([malformed("add", '{"a": 1,'), answer()])
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        messages = asyncio.run(graph.ainvoke({"messages": [HumanMessage("add")]}))["messages"]

        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]
        assert messages[2].status == "error"
        assert model.calls == 2

    def test_refused_calls_still_spend_the_budget(self, fake_llm, add_tool):
        model = fake_llm(propose(("multiply", {"a": 2, "b": 3})) for _ in itertools.count())

        with pytest.raises(ModelCallBudgetExceededError):
            run(build_assistant(model, [add_tool.tool], transient=no_retries), "keep multiplying")

        assert model.calls == 10
        assert add_tool.calls == []

    def test_invalid_calls_still_spend_the_budget(self, fake_llm, add_tool):
        model = fake_llm(malformed("add", '{"a": 1,') for _ in itertools.count())

        # A ceiling of 100, well above the 22 the budget needs: were the budget
        # not counting these turns, the run would end at the ceiling, not loop on.
        with pytest.raises(ModelCallBudgetExceededError):
            run(
                build_assistant(model, [add_tool.tool], transient=no_retries),
                "add",
                recursion_limit=100,
            )

        assert model.calls == MODEL_CALLS_PER_RUN
        assert add_tool.calls == []

    def test_counter_example_a_valid_call_beside_an_invalid_one_still_runs(
        self, fake_llm, add_tool
    ):
        both = malformed("add", '{"a": 1,')
        both.tool_calls = propose(("add", {"a": 1, "b": 2})).tool_calls
        model = fake_llm([both, answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        answers = tool_messages(messages)
        assert add_tool.calls == [{"a": 1, "b": 2}]
        assert answers[both.tool_calls[0]["id"]] == ("success", "3")
        assert answers[both.invalid_tool_calls[0]["id"]] == (
            "error",
            "Error: the arguments for add are not valid JSON; send them again as a JSON object.",
        )

    def test_counter_example_a_malformed_call_without_an_id_beside_a_well_formed_one(
        self, fake_llm, add_tool
    ):
        both = malformed("add", '{"a": 1,', with_id=False)
        both.tool_calls = propose(("add", {"a": 1, "b": 2})).tool_calls
        model = fake_llm([both, answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert add_tool.calls == [{"a": 1, "b": 2}]
        assert tool_messages(messages) == {both.tool_calls[0]["id"]: ("success", "3")}
        assert messages[1].invalid_tool_calls == []
        assert model.calls == 2

    def test_counter_example_a_valid_call_beside_a_refused_one_still_runs(self, fake_llm, add_tool):
        proposal = propose(("add", {"a": 1, "b": 2}), ("multiply", {"a": 3, "b": 4}))
        model = fake_llm([proposal, answer()])

        messages = run(
            build_assistant(model, [add_tool.tool], transient=no_retries),
            "add 1 and 2, multiply 3 and 4",
        )

        assert add_tool.calls == [{"a": 1, "b": 2}]
        add_id, multiply_id = (call["id"] for call in proposal.tool_calls)
        answered = tool_messages(messages)
        assert answered[add_id] == ("success", "3")
        assert answered[multiply_id][0] == "error"


class TestErrorsPropagate:
    """ASSISTANT-ERRORS-PROPAGATE: An exception that a tool raises, or that the
    model raises and the retry policy does not classify as transient, SHALL end
    the run by propagating to the caller unchanged -- the unexpected class, never
    turned into a message the run carries on with."""

    def test_a_tools_exception_reaches_the_caller_unchanged(self, fake_llm):
        failure = RuntimeError("explode failed")

        @tool
        def explode(a: int) -> int:
            """Fail."""
            raise failure

        model = fake_llm([propose(("explode", {"a": 1})), answer()])

        with pytest.raises(RuntimeError) as raised:
            run(build_assistant(model, [manifested(explode)], transient=no_retries), "explode")

        assert raised.value is failure
        assert model.calls == 1

    def test_the_models_exception_reaches_the_caller_unchanged(self, fake_llm, add_tool):
        failure = RuntimeError("model broke")
        model = fake_llm([failure])
        graph = build_assistant(model, [add_tool.tool], transient=is_transient_failure)

        with pytest.raises(RuntimeError) as raised:
            run(graph, "hello")

        assert raised.value is failure
        assert model.calls == 1
        assert add_tool.calls == []

    def test_counter_example_a_tool_that_returns_an_error_text_has_not_raised(self, fake_llm):
        @tool
        def explain(a: int) -> str:
            """Explain nothing."""
            return "error: nothing to explain"

        proposal = propose(("explain", {"a": 1}))
        model = fake_llm([proposal, answer()])

        messages = run(
            build_assistant(model, [manifested(explain, str)], transient=no_retries), "explain"
        )

        assert tool_messages(messages) == {
            proposal.tool_calls[0]["id"]: ("success", "error: nothing to explain")
        }
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]


class TestModelCallBudget:
    """ASSISTANT-MODEL-CALL-BUDGET: A run of the assistant SHALL make at most
    `MODEL_CALLS_PER_RUN` model turns, a domain budget equal to 10; each turn SHALL
    make at most `1 + MODEL_RETRIES` attempts (ASSISTANT-TRANSIENT-RETRY), its
    retries spending none of the budget. A model still proposing tool calls when the
    budget is spent SHALL end the run with `ModelCallBudgetExceededError`, naming
    the budget -- never with a message that reads like an answer, and never at the
    step ceiling first under the ceiling the factory's graph runs with: 9,999
    supersteps (ASSISTANT-GRAPH-TOPOLOGY), where the budget needs 22 -- `start_run`,
    then `call_model` and `run_tools` for each of the 10 turns, then the eleventh
    `call_model`, which refuses."""

    def test_a_model_that_never_stops_proposing_calls_ends_in_the_budget_error(
        self, fake_llm, add_tool
    ):
        model = fake_llm(propose(("add", {"a": 1, "b": 1})) for _ in itertools.count())
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        # Not GraphRecursionError: the budget, not the runtime's step ceiling, ends the run.
        with pytest.raises(ModelCallBudgetExceededError) as ended:
            run(graph, "keep adding")

        assert str(ended.value) == "a run may make 10 model calls, and this one has made them all"

        assert graph.config["recursion_limit"] == 9_999
        assert MODEL_CALLS_PER_RUN == 10
        assert model.calls == MODEL_CALLS_PER_RUN
        assert len(add_tool.calls) == MODEL_CALLS_PER_RUN

    def test_a_retried_turn_spends_one_unit_of_the_budget(self, fake_llm, add_tool):
        def every_turn_times_out_first():
            while True:
                yield openai.APITimeoutError(request=REQUEST)
                yield propose(("add", {"a": 1, "b": 1}))

        model = fake_llm(every_turn_times_out_first())
        graph = build_assistant(
            model, [add_tool.tool], transient=is_transient_failure, initial_delay=0
        )

        with pytest.raises(ModelCallBudgetExceededError):
            run(graph, "keep adding")

        assert model.calls == 2 * MODEL_CALLS_PER_RUN
        assert len(add_tool.calls) == MODEL_CALLS_PER_RUN

    def test_counter_example_an_answer_on_the_last_call_within_budget_completes(
        self, fake_llm, add_tool
    ):
        script = [propose(("add", {"a": 1, "b": 1})) for _ in range(9)] + [answer()]
        model = fake_llm(script)

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "keep adding")

        assert messages[-1].type == "ai"
        assert messages[-1].tool_calls == []
        assert model.calls == 10
        assert len(add_tool.calls) == 9

    @pytest.mark.parametrize(
        ("recursion_limit", "ends_with"),
        [(21, GraphRecursionError), (22, ModelCallBudgetExceededError)],
    )
    def test_counter_example_a_callers_step_ceiling_below_22_ends_the_run_first(
        self, fake_llm, add_tool, recursion_limit, ends_with
    ):
        model = fake_llm(propose(("add", {"a": 1, "b": 1})) for _ in itertools.count())

        with pytest.raises(ends_with):
            run(
                build_assistant(model, [add_tool.tool], transient=no_retries),
                "keep adding",
                recursion_limit=recursion_limit,
            )


REQUEST = httpx.Request("POST", "http://127.0.0.1:9/api/chat/completions")


def status_failure(code: int) -> openai.APIStatusError:
    """What the openai client raises for an HTTP error from Open WebUI."""
    return openai.APIStatusError(
        f"HTTP {code}", response=httpx.Response(code, request=REQUEST), body=None
    )


def retrying(model) -> object:
    """The assistant with the registry's retry policy, without waiting between tries."""
    return build_assistant(model, [], transient=is_transient_failure, initial_delay=0)


class TestTransientRetry:
    """ASSISTANT-TRANSIENT-RETRY: A model failure that the domain classifies as
    transient (MODEL-TRANSIENT-FAILURES) -- a streamed chunk that never came
    included -- SHALL be retried within its turn, at most `MODEL_RETRIES` times
    (2); when the retries are spent the run SHALL end with that failure, never
    with a message that reads like an answer. Any other failure SHALL NOT be
    retried."""

    @pytest.mark.parametrize(
        "failure",
        [
            openai.APITimeoutError(request=REQUEST),
            openai.APIConnectionError(request=REQUEST),
            StreamChunkTimeoutError(120.0),
            "429",
        ],
        ids=["openai-timeout", "connection-refused", "stream-chunk-timeout", "http-429"],
    )
    def test_each_kind_of_transient_failure_as_the_client_raises_it_is_retried(
        self, fake_llm, failure
    ):
        first = status_failure(429) if failure == "429" else failure
        model = fake_llm([first, answer()])

        messages = run(retrying(model), "hello")

        assert [m.type for m in messages] == ["human", "ai"]
        assert model.calls == 2

    def test_a_timeout_is_retried_and_the_answer_completes_the_run(self, fake_llm):
        model = fake_llm([openai.APITimeoutError(request=REQUEST), answer()])

        messages = run(retrying(model), "hello")

        assert [m.type for m in messages] == ["human", "ai"]
        assert model.calls == 2

    def test_transient_failures_past_the_retries_end_the_run_with_the_failure(self, fake_llm):
        model = fake_llm(status_failure(503) for _ in itertools.count())

        with pytest.raises(openai.APIStatusError) as raised:
            run(retrying(model), "hello")

        assert raised.value.status_code == 503
        assert MODEL_RETRIES == 2
        assert model.calls == 1 + MODEL_RETRIES

    @pytest.mark.parametrize("code", [401, 400])
    def test_counter_example_a_failure_that_is_not_transient_is_not_retried(self, fake_llm, code):
        model = fake_llm([status_failure(code), answer()])

        with pytest.raises(openai.APIStatusError) as raised:
            run(retrying(model), "hello")

        assert raised.value.status_code == code
        assert model.calls == 1


class TestToolCallBudget:
    """ASSISTANT-TOOL-CALL-BUDGET: A run SHALL execute at most `TOOL_CALLS_PER_RUN`
    (20) tool calls: a turn whose proposed calls would take the run past it SHALL
    end the run with `ToolCallBudgetExceededError`, naming the count the turn would
    reach and the limit, none of that turn's calls executed. Every well-formed call
    counts, run or refused -- an unknown tool, arguments its schema refuses; a
    malformed call is answered, never executed, and is not counted."""

    @staticmethod
    def turns(per_turn: int, count: int) -> list:
        return [propose(*[("add", {"a": 1, "b": 2})] * per_turn) for _ in range(count)]

    def test_four_calls_a_turn_for_five_turns_completes(self, fake_llm, add_tool):
        model = fake_llm([*self.turns(4, 5), answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert TOOL_CALLS_PER_RUN == 20
        assert len(add_tool.calls) == 20
        assert messages[-1].type == "ai" and messages[-1].tool_calls == []

    def test_a_turn_that_would_pass_the_budget_ends_the_run_none_of_its_calls_run(
        self, fake_llm, add_tool
    ):
        model = fake_llm([*self.turns(3, 7), answer()])

        with pytest.raises(ToolCallBudgetExceededError) as ended:
            run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert str(ended.value) == (
            "a turn would take the run to 21 tool calls; the run's limit is 20"
        )
        assert (ended.value.count, ended.value.budget) == (21, 20)
        assert len(add_tool.calls) == 18

    def test_a_malformed_call_beside_the_budget_is_answered_not_counted(self, fake_llm, add_tool):
        # 19 and 1 malformed, then 1: counted, the malformed call would make 21.
        turn = self.turns(19, 1)[0]
        turn.invalid_tool_calls = malformed("add", '{"a": 1,').invalid_tool_calls
        model = fake_llm([turn, *self.turns(1, 1), answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert len(add_tool.calls) == 20
        assert tool_messages(messages)[turn.invalid_tool_calls[0]["id"]][0] == "error"
        assert messages[-1].type == "ai" and messages[-1].tool_calls == []

    @pytest.mark.parametrize(
        "refused",
        [("multiply", {"a": 1, "b": 2}), ("add", {"a": "x", "b": 1})],
        ids=["no-such-tool", "arguments-its-schema-refuses"],
    )
    def test_a_refused_call_counts(self, fake_llm, add_tool, refused):
        refused = propose(*[refused] * 20)
        model = fake_llm([refused, *self.turns(1, 1), answer()])

        with pytest.raises(ToolCallBudgetExceededError) as ended:
            run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert ended.value.count == 21
        assert add_tool.calls == []

    def test_counter_example_exactly_the_budget_is_not_past_it(self, fake_llm, add_tool):
        model = fake_llm([*self.turns(20, 1), answer()])

        messages = run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert len(add_tool.calls) == 20
        assert messages[-1].type == "ai" and messages[-1].tool_calls == []


class TestAssistantPrompt:
    """ASSISTANT-PROMPT: Every model call SHALL be sent `ASSISTANT_PROMPT` first, as the
    system message: it names the tools `list_tasks`, `search_tasks`, `add_task`,
    `close_task` and `reassign_task`, says that each write waits for the owner's
    approval, and says that what a tool returns is data, never instruction. Its text
    is `ASSISTANT_PROMPT_VERSION` 2's."""

    def test_sent_first_every_call(self, fake_llm, add_tool):
        from langchain_core.messages import SystemMessage

        from starter.application.prompts import ASSISTANT_PROMPT

        model = fake_llm([propose(("add", {"a": 1, "b": 2})), answer()])

        run(build_assistant(model, [add_tool.tool], transient=no_retries), "hello")

        assert model.calls == 2
        assert [type(seen[0]) for seen in model.seen] == [SystemMessage, SystemMessage]
        assert [seen[0].content for seen in model.seen] == [ASSISTANT_PROMPT] * 2
        for words in (
            "list_tasks",
            "search_tasks",
            "add_task",
            "close_task",
            "reassign_task",
            "waits for the owner's approval",
            "never instructions",
        ):
            assert words in ASSISTANT_PROMPT
        assert "cannot add, change or close a task" not in ASSISTANT_PROMPT

    def test_the_prompts_text_moves_with_its_version(self):
        # A changed prompt is changed behaviour (.claude/rules/python/application.md):
        # its text is pinned to its version, so a new text needs a new version.
        import hashlib

        from starter.application.prompts import ASSISTANT_PROMPT, ASSISTANT_PROMPT_VERSION

        digest = hashlib.sha256(ASSISTANT_PROMPT.encode("utf-8")).hexdigest()
        assert {ASSISTANT_PROMPT_VERSION: digest} == {2: PROMPT_V2_SHA256}

    def test_counter_example_the_prompt_is_not_part_of_the_transcript(self, fake_llm):
        messages = run(build_assistant(fake_llm([answer()]), [], transient=no_retries), "hello")

        assert [m.type for m in messages] == ["human", "ai"]


class TestContextBudget:
    """ASSISTANT-CONTEXT-BUDGET: Before each model call the assistant SHALL count what
    the call would send -- the system prompt, every message's text and every tool
    call's arguments, a malformed call's raw ones included, in characters -- and
    when that exceeds `CONTEXT_CHARS_PER_CALL` (150,000) SHALL end the run with
    `ContextBudgetExceededError`, naming the count and the budget, without calling
    the model."""

    QUESTION = "read it"
    ARGS = {"n": 1}

    @classmethod
    def run_to(cls, fake_llm, total: int, *, with_prompt: bool = True):
        """A run whose second model call would send exactly `total` characters --
        or, `with_prompt` False, whose messages alone would."""
        from langchain_core.tools import tool

        from starter.application.prompts import ASSISTANT_PROMPT

        fixed = len(cls.QUESTION) + len(json.dumps(cls.ARGS))
        if with_prompt:
            fixed += len(ASSISTANT_PROMPT)

        @tool
        def read(n: int) -> str:
            """Return the padding."""
            return "x" * (total - fixed)

        model = fake_llm([propose(("read", cls.ARGS)), answer("")])
        graph = build_assistant(model, [manifested(read, str)], transient=no_retries)
        return model, lambda: run(graph, cls.QUESTION)

    def test_over_the_budget_the_run_ends_before_the_call(self, fake_llm):
        model, go = self.run_to(fake_llm, 150_001)

        with pytest.raises(ContextBudgetExceededError) as ended:
            go()

        assert CONTEXT_CHARS_PER_CALL == 150_000
        assert (ended.value.count, ended.value.budget) == (150_001, 150_000)
        assert "150001" in str(ended.value) and "150000" in str(ended.value)
        assert model.calls == 1

    def test_exactly_the_budget_completes(self, fake_llm):
        model, go = self.run_to(fake_llm, 150_000)

        messages = go()

        assert messages[-1].type == "ai"
        assert model.calls == 2

    def test_counter_example_the_prompt_counts(self, fake_llm):
        model, go = self.run_to(fake_llm, 149_990, with_prompt=False)

        with pytest.raises(ContextBudgetExceededError):
            go()

        assert model.calls == 1

    @pytest.mark.parametrize(("total", "ends"), [(150_001, True), (150_000, False)])
    def test_as_the_server_runs_it_asynchronously(self, fake_llm, total, ends):
        # The local server runs graphs with `astream`, and an async-only tool
        # runs only there: the context budget holds on that path too.
        import asyncio

        from langchain_core.tools import tool

        from starter.application.prompts import ASSISTANT_PROMPT

        fixed = len(self.QUESTION) + len(json.dumps(self.ARGS)) + len(ASSISTANT_PROMPT)

        @tool
        async def read(n: int) -> str:
            """Return the padding."""
            return "x" * (total - fixed)

        model = fake_llm([propose(("read", self.ARGS)), answer("")])
        graph = build_assistant(model, [manifested(read, str)], transient=no_retries)
        go = graph.ainvoke({"messages": [HumanMessage(self.QUESTION)]})

        if ends:
            with pytest.raises(ContextBudgetExceededError):
                asyncio.run(go)
        else:
            assert asyncio.run(go)["messages"][-1].type == "ai"
        assert model.calls == (1 if ends else 2)

    def test_the_retry_policy_does_not_retry_it(self, fake_llm):
        from langchain_core.tools import tool

        from starter.application.prompts import ASSISTANT_PROMPT

        fixed = len(self.QUESTION) + len(json.dumps(self.ARGS)) + len(ASSISTANT_PROMPT)

        @tool
        def read(n: int) -> str:
            """Return the padding."""
            return "x" * (150_001 - fixed)

        model = fake_llm([propose(("read", self.ARGS)), answer("")])
        graph = build_assistant(
            model, [manifested(read, str)], transient=is_transient_failure, initial_delay=0
        )

        with pytest.raises(ContextBudgetExceededError):
            run(graph, self.QUESTION)

        # Not transient, so never retried: the predicate itself, since the budget
        # refuses before the model is called either way.
        assert is_transient_failure(ContextBudgetExceededError(150_001, 150_000)) is False
        assert is_transient_failure(OutputBudgetExceededError(4096)) is False
        assert is_transient_failure(ModelCallBudgetExceededError(10)) is False
        assert is_transient_failure(ToolCallBudgetExceededError(21, 20)) is False
        assert model.calls == 1

    def test_counter_example_an_ai_messages_text_counts(self, fake_llm):
        from langchain_core.tools import tool

        from starter.application.prompts import ASSISTANT_PROMPT

        said = "a" * 11
        fixed = len(self.QUESTION) + len(json.dumps(self.ARGS)) + len(ASSISTANT_PROMPT)

        @tool
        def read(n: int) -> str:
            """Return the padding."""
            return "x" * (149_990 - fixed)

        reply = propose(("read", self.ARGS))
        reply.content = said
        model = fake_llm([reply, answer("")])
        graph = build_assistant(model, [manifested(read, str)], transient=no_retries)

        with pytest.raises(ContextBudgetExceededError) as ended:
            run(graph, self.QUESTION)

        assert ended.value.count == 150_001
        assert model.calls == 1

    def test_counter_example_a_malformed_calls_raw_arguments_count(self, fake_llm, add_tool):
        from starter.application.prompts import ASSISTANT_PROMPT

        raw = '{"a": 1, "b'
        assert len(raw) == 11
        answer_text = (
            "Error: the arguments for add are not valid JSON; send them again as a JSON object."
        )
        question = "q" * (149_990 - len(ASSISTANT_PROMPT) - len(answer_text))
        model = fake_llm([malformed("add", raw), answer("")])
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        with pytest.raises(ContextBudgetExceededError) as ended:
            run(graph, question)

        assert ended.value.count == 150_001
        assert model.calls == 1


class TestOutputBudget:
    """ASSISTANT-OUTPUT-BUDGET: A reply cut off at the client's cap of
    `MODEL_OUTPUT_TOKENS` (4,096) tokens (MODEL-OPENWEBUI-CLIENT) -- its finish
    reason `length`, or its output tokens reaching the cap -- SHALL end the run with
    `OutputBudgetExceededError`, naming the cap: never handed on as an answer, nor
    its calls run, nor stored in the thread, nor retried. A backend that ignores the
    cap -- an Ollama model behind Open WebUI without `num_predict` set there -- is
    outside this rule."""

    @staticmethod
    def cut_off(message):
        message.response_metadata = {"finish_reason": "length"}
        return message

    def test_a_reply_cut_off_at_the_cap_ends_the_run(self, fake_llm):
        model = fake_llm([self.cut_off(answer("a long answer, cut")), answer()])

        with pytest.raises(OutputBudgetExceededError) as ended:
            run(build_assistant(model, [], transient=no_retries), "hello")

        assert MODEL_OUTPUT_TOKENS == 4096
        assert ended.value.cap == 4096
        assert str(ended.value) == "a reply was cut off at its cap of 4096 tokens"
        assert model.calls == 1

    def test_a_call_cut_off_at_the_cap_is_not_run(self, fake_llm, add_tool):
        model = fake_llm([self.cut_off(propose(("add", {"a": 1, "b": 2}))), answer()])

        with pytest.raises(OutputBudgetExceededError):
            run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert add_tool.calls == []

    def test_a_call_cut_off_mid_arguments_is_not_handed_back(self, fake_llm, add_tool):
        model = fake_llm([self.cut_off(malformed("add", '{"a": 1, "b')), answer()])

        with pytest.raises(OutputBudgetExceededError):
            run(build_assistant(model, [add_tool.tool], transient=no_retries), "add")

        assert model.calls == 1

    @pytest.mark.parametrize(("output_tokens", "ends"), [(4097, True), (4096, True), (4095, False)])
    def test_a_reply_that_reached_the_cap_though_it_says_stop(self, fake_llm, output_tokens, ends):
        # An Ollama model capped by its own num_predict reports `stop` (measured on
        # the owner's server): the tokens are what show it was cut off.
        reply = answer("cut")
        reply.response_metadata = {"finish_reason": "stop"}
        reply.usage_metadata = {
            "input_tokens": 10,
            "output_tokens": output_tokens,
            "total_tokens": 10 + output_tokens,
        }
        graph = build_assistant(fake_llm([reply]), [], transient=no_retries)

        if ends:
            with pytest.raises(OutputBudgetExceededError):
                run(graph, "hello")
        else:
            assert run(graph, "hello")[-1].type == "ai"

    def test_a_reply_that_stopped_completes(self, fake_llm):
        reply = answer("done")
        reply.response_metadata = {"finish_reason": "stop"}

        messages = run(build_assistant(fake_llm([reply]), [], transient=no_retries), "hello")

        assert messages[-1].type == "ai"

    def test_a_cut_off_reply_is_not_stored_in_the_thread(self, fake_llm):
        from langgraph.checkpoint.memory import InMemorySaver

        model = fake_llm([self.cut_off(answer("a long answer, cut"))])
        graph = build_assistant(model, [], transient=no_retries).copy(
            update={"checkpointer": InMemorySaver()}
        )
        thread = {"configurable": {"thread_id": "cut"}}

        with pytest.raises(OutputBudgetExceededError):
            graph.invoke({"messages": [HumanMessage("hello")]}, thread)

        assert [m.type for m in graph.get_state(thread).values["messages"]] == ["human"]

    def test_under_the_registrys_retry_predicate_it_is_not_retried(self, fake_llm):
        model = fake_llm([self.cut_off(answer("cut")), answer()])

        with pytest.raises(OutputBudgetExceededError):
            run(retrying(model), "hello")

        assert model.calls == 1

    def test_counter_example_a_reply_with_no_finish_reason_completes(self):
        from starter.infrastructure.models import build_offline_model

        messages = run(build_assistant(build_offline_model(), [], transient=no_retries), "hello")

        assert [m.type for m in messages] == ["human", "ai"]

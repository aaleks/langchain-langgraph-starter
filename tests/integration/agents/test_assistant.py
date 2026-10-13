"""The assistant's routes, driven through the factory the registry uses, with a
scripted model and fake tools in place of every real one.

The route is asserted -- the transcript's shape, what the model was given, the
calls made, the error that ends a run -- never the model's text.
"""

from __future__ import annotations

import itertools

import httpx
import openai
import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import StreamChunkTimeoutError
from langgraph.errors import GraphRecursionError

from starter.domain.agents.budgets import MODEL_CALLS_PER_RUN
from starter.domain.agents.retries import MODEL_RETRIES
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.models import is_transient_failure
from tests.fakes import answer, propose


def no_retries(failure: Exception) -> bool:
    """For the routes that are not about retrying: no failure is transient."""
    return False


def run(graph, text: str, **config) -> list:
    return graph.invoke({"messages": [HumanMessage(text)]}, config=config or None)["messages"]


def tool_messages(messages: list) -> dict[str, tuple[str, str]]:
    """Each tool message, by the call it answers: (status, content)."""
    return {m.tool_call_id: (m.status, m.content) for m in messages if m.type == "tool"}


class TestToolLoop:
    """ASSISTANT-TOOL-LOOP: The assistant SHALL execute every call the model
    proposes to a tool it was given, with arguments that tool's schema accepts --
    exactly once, with the model's arguments -- hand each result to the model's
    next call as a tool message answering that call, and end the run when the
    model answers without proposing a tool call. A reply carrying only
    `invalid_tool_calls` is outside this rule: its route is OPEN."""

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
    """ASSISTANT-TOOL-ERROR: A call the model proposes to a tool it was not
    given, or with arguments that tool's schema refuses, SHALL execute no tool.
    The model's next call SHALL receive a tool message with status `error`
    answering that call, and the run SHALL go on under the same budget -- the
    model-recoverable class, handed back rather than raised."""

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

    def test_refused_calls_still_spend_the_budget(self, fake_llm, add_tool):
        model = fake_llm(propose(("multiply", {"a": 2, "b": 3})) for _ in itertools.count())

        with pytest.raises(ModelCallLimitExceededError):
            run(build_assistant(model, [add_tool.tool], transient=no_retries), "keep multiplying")

        assert model.calls == 10
        assert add_tool.calls == []

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
            run(build_assistant(model, [explode], transient=no_retries), "explode")

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

        messages = run(build_assistant(model, [explain], transient=no_retries), "explain")

        assert tool_messages(messages) == {
            proposal.tool_calls[0]["id"]: ("success", "error: nothing to explain")
        }
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai"]


class TestModelCallBudget:
    """ASSISTANT-MODEL-CALL-BUDGET: A run of the assistant SHALL make at most
    `MODEL_CALLS_PER_RUN` model turns, a domain budget equal to 10; each turn
    SHALL make at most `1 + MODEL_RETRIES` attempts (ASSISTANT-TRANSIENT-RETRY),
    its retries spending none of the budget. A model still proposing tool calls
    when the budget is spent SHALL end the run with `ModelCallLimitExceededError`
    -- never with a message that reads like an answer, and never at the step
    ceiling first under the ceiling the factory's graph runs with:
    `create_agent`'s 9,999 supersteps, where the budget needs 41."""

    def test_a_model_that_never_stops_proposing_calls_ends_in_the_budget_error(
        self, fake_llm, add_tool
    ):
        model = fake_llm(propose(("add", {"a": 1, "b": 1})) for _ in itertools.count())
        graph = build_assistant(model, [add_tool.tool], transient=no_retries)

        # Not GraphRecursionError: the budget, not the runtime's step ceiling, ends the run.
        with pytest.raises(ModelCallLimitExceededError):
            run(graph, "keep adding")

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

        with pytest.raises(ModelCallLimitExceededError):
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
        [(40, GraphRecursionError), (41, ModelCallLimitExceededError)],
    )
    def test_counter_example_a_callers_step_ceiling_below_41_ends_the_run_first(
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

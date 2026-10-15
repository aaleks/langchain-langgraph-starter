"""Where the assistant goes after each reply -- a pure decision on typed facts."""

from __future__ import annotations

import pytest

from starter.domain.agents.routing import (
    keep_malformed_calls,
    route_after_reply,
    route_after_tools,
    route_after_writes,
)


class TestRouteAfterReply:
    """ASSISTANT-ROUTING: After each reply, the assistant SHALL route by the domain policy
    `route_after_reply`: to `run_tools` when the reply as stored proposes any call,
    well-formed or malformed, and to the end otherwise. The policy
    `keep_malformed_calls` SHALL keep a reply's malformed calls only when every one
    of them has an id; a reply it does not keep them for is stored without them
    (ASSISTANT-TOOL-ERROR). After the tools, `route_after_tools` SHALL go to
    `review_writes` when a write call waits for the owner, and to `call_model`
    otherwise; after the writes, `route_after_writes` SHALL go to `call_model` when
    every decision approved, and to the end when any rejected."""

    @pytest.mark.parametrize(
        ("well_formed", "malformed", "route"),
        [(1, 0, "run_tools"), (0, 1, "run_tools"), (2, 1, "run_tools"), (0, 0, "end")],
    )
    def test_any_call_proposed_goes_to_the_tools_and_none_ends_the_run(
        self, well_formed, malformed, route
    ):
        assert route_after_reply(well_formed=well_formed, malformed=malformed) == route

    @pytest.mark.parametrize(
        ("ids", "kept"),
        [(["a", "b"], True), (["a", None], False), ([None], False), ([], True)],
        ids=["every-id", "one-missing", "none", "no-malformed-call"],
    )
    def test_malformed_calls_are_kept_only_when_every_one_has_an_id(self, ids, kept):
        assert keep_malformed_calls(ids) is kept

    @pytest.mark.parametrize(("waiting", "route"), [(1, "review_writes"), (0, "call_model")])
    def test_after_the_tools_a_waiting_write_goes_to_the_owner(self, waiting, route):
        assert route_after_tools(waiting_writes=waiting) == route

    @pytest.mark.parametrize(
        ("decisions", "route"),
        [
            (["approve", "approve"], "call_model"),
            (["approve", "reject"], "end"),
            ([], "call_model"),
        ],
        ids=["all-approved", "one-rejected", "none"],
    )
    def test_after_the_writes_a_rejection_ends_the_run(self, decisions, route):
        assert route_after_writes(decisions) == route

    def test_counter_example_an_empty_id_is_no_id(self):
        assert keep_malformed_calls(["a", ""]) is False

"""Where the assistant goes after each reply -- a pure decision on typed facts."""

from __future__ import annotations

import pytest

from starter.domain.agents.routing import keep_malformed_calls, route_after_reply


class TestRouteAfterReply:
    """ASSISTANT-ROUTING: After each reply, the assistant SHALL route by the domain
    policy `route_after_reply`: to `run_tools` when the reply proposes any call,
    well-formed or malformed, and to the end otherwise. It SHALL keep a reply's
    malformed calls only when every one of them has an id (`keep_malformed_calls`);
    otherwise the reply is stored without them."""

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

    def test_counter_example_an_empty_id_is_no_id(self):
        assert keep_malformed_calls(["a", ""]) is False

from __future__ import annotations

import pytest

from starter.domain.agents.retries import is_transient


class TestTransientFailures:
    """MODEL-TRANSIENT-FAILURES: A failed model call SHALL be transient exactly
    when it timed out, its connection failed, or the server answered HTTP 408,
    429, 500, 502, 503 or 504."""

    @pytest.mark.parametrize(
        ("status", "timed_out", "connection_failed"),
        [
            (None, True, False),
            (None, False, True),
            *((code, False, False) for code in (408, 429, 500, 502, 503, 504)),
        ],
    )
    def test_a_timeout_a_failed_connection_and_each_listed_status_are_transient(
        self, status, timed_out, connection_failed
    ):
        assert is_transient(status=status, timed_out=timed_out, connection_failed=connection_failed)

    def test_exactly_the_listed_statuses_and_no_other(self):
        transient = {
            status
            for status in range(100, 600)
            if is_transient(status=status, timed_out=False, connection_failed=False)
        }

        assert transient == {408, 429, 500, 502, 503, 504}

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 501, 505, None])
    def test_counter_example_a_failure_that_is_the_same_on_every_try_is_not(self, status):
        assert not is_transient(status=status, timed_out=False, connection_failed=False)

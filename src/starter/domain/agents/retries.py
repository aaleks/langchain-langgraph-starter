"""Which model failures are worth another try, and how many tries."""

from __future__ import annotations

# Starting policy, revisited against real runs (connect-openwebui-model, frame.md).
MODEL_RETRIES = 2

# A request the server may answer next time: a timeout, too many requests, or
# a server-side failure. A 400 or a 401 will be the same on every try.
TRANSIENT_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


def is_transient(*, status: int | None, timed_out: bool, connection_failed: bool) -> bool:
    """Whether a failed model call, described by these facts, should be retried."""
    return timed_out or connection_failed or status in TRANSIENT_STATUSES

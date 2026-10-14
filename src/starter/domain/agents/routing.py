"""Where the assistant goes after a reply -- decided from typed facts, never from text."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

Route = Literal["run_tools", "end"]


def route_after_reply(*, well_formed: int, malformed: int) -> Route:
    """Any call proposed goes to the tools -- a malformed one to be answered
    there, so the model can send it again (ASSISTANT-TOOL-ERROR). A reply
    proposing nothing is the answer, and ends the run."""
    return "run_tools" if well_formed or malformed else "end"


def keep_malformed_calls(ids: Iterable[str | None]) -> bool:
    """Whether a reply keeps its malformed calls: only when each has an id. One
    without could not be answered, and the endpoint refuses a call left
    unanswered -- so the reply is stored without them all."""
    return all(ids)

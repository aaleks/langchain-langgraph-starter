"""Where the assistant goes after a reply -- decided from typed facts, never from text."""

from __future__ import annotations

from collections.abc import Iterable, Sequence, Set
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


def unanswered_calls(proposed: Iterable[str], answered: Set[str]) -> list[str]:
    """The calls a reply proposed that no tool message answers, in order: what an
    earlier run left when it ended between the reply and its tools. Each needs an
    answer before the model is called again -- the endpoint refuses a call left
    unanswered (ASSISTANT-NO-CALL-LEFT-UNANSWERED)."""
    return [call_id for call_id in proposed if call_id not in answered]


def route_after_tools(*, waiting_writes: int) -> Literal["review_writes", "call_model"]:
    """A write the checks accepted waits for the owner (ASSISTANT-WRITE-APPROVAL);
    with none, the tools' answers go to the model."""
    return "review_writes" if waiting_writes else "call_model"


def route_after_writes(
    decisions: Iterable[str], *, waiting: int
) -> Literal["apply_writes", "call_model", "end"]:
    """One write is decided per step, so the next waits its turn. When none is
    left: any the owner rejected ends the run, the model not called again -- the
    owner's rule; otherwise the model goes on (ASSISTANT-WRITE-DECISIONS)."""
    if waiting:
        return "apply_writes"
    return "end" if any(decision == "reject" for decision in decisions) else "call_model"


def calls_to_rename(ids: Sequence[str | None], taken: Set[str]) -> list[int]:
    """The positions of a reply's well-formed calls whose id is missing, or used
    already -- by an earlier call of the reply, or in `taken`: each gets an id of
    its own, so no answer, decision or key can be another call's
    (ASSISTANT-STATE-CONTRACT)."""
    seen = set(taken)
    renamed = []
    for position, call_id in enumerate(ids):
        if not call_id or call_id in seen:
            renamed.append(position)
        else:
            seen.add(call_id)
    return renamed

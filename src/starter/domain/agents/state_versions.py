"""What a checkpoint's state version means to the code reading it
(ASSISTANT-CHECKPOINT-VERSION, docs/decisions/0010).

A checkpoint carries the version of the state contract that wrote it. Code reads
its own version and every one before it -- the state contract migrates them, and
a checkpoint written before the stamp carries none -- but never a newer one: a
rollback would read fields it does not know as if they were its own.
"""

from __future__ import annotations


class CheckpointVersionError(ValueError):
    """A thread's checkpoint this code must not read."""


def checkpoint_version_refusal(found: object, current: int) -> str | None:
    """Why a checkpoint stamped `found` is refused by code at `current`, or None
    to read it. `found` is None for a checkpoint written before the stamp."""
    if found is None:
        return None
    # A boolean is an int to Python, never a version.
    if isinstance(found, bool) or not isinstance(found, int) or found < 1:
        return f"its state version {found!r} is not a version"
    if found > current:
        return f"its state version is {found}, newer than {current}, this code's"
    return None

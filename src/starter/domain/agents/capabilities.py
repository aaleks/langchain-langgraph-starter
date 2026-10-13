"""What a tool may do, declared beside it -- and whether the assistant can honour it.

The fields are `.claude/rules/langgraph/graphs.md`'s ("Tools"); the input's
schema is the tool's own. What holds each one: `side_effect` here, a write
refused until slice 4 gives it an approval; `timeout_seconds` the store's own
wait; `calls_per_run` the run's tool-call budget; `retry` "none" -- a tool's
failure propagates. `idempotent` and `audit_event` are declared now and held
with the first write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SideEffect = Literal["read", "write"]
RetryClass = Literal["none", "transient"]


@dataclass(frozen=True)
class Capability:
    name: str
    output: type
    errors: tuple[type[Exception], ...]
    idempotent: bool
    timeout_seconds: float
    retry: RetryClass
    calls_per_run: int
    side_effect: SideEffect
    audit_event: str | None


def check_capability(tool_name: str, capability: Capability | None) -> None:
    """Refuse, naming the tool, a manifest the assistant cannot honour."""
    if capability is None:
        raise ValueError(f"tool {tool_name!r} has no capability manifest")
    if capability.name != tool_name:
        raise ValueError(f"tool {tool_name!r} carries the manifest of {capability.name!r}")
    if capability.side_effect != "read":
        raise ValueError(
            f"tool {tool_name!r} declares the side effect {capability.side_effect!r}: "
            "no write has an approval route yet"
        )

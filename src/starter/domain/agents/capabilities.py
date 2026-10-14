"""What a tool may do, declared beside it -- and whether the assistant can honour it.

The fields are `.claude/rules/langgraph/graphs.md`'s ("Tools"); the input's
schema is the tool's own. What holds each one:

- `side_effect` -- here: a write is refused until slice 4 gives it an approval.
  A tool declaring `read` reads through a view of its store that refuses a
  write, so the declaration is not the only guard.
- `retry` -- here: only `"none"`, since a tool's failure propagates.
- `calls_per_run` -- here: only the run's budget, the one limit the factory
  enforces (`ToolCallLimitMiddleware`, every tool together).
- `timeout_seconds` -- the store's own wait, which the tool takes from it.
- `idempotent` and `audit_event` -- declared now, held with the first write.

Checked once, when the graph is composed: its tools are fixed then, and each
is a read. A write's check, immediately before it runs, arrives with slice 4.
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


def check_capability(tool_name: str, capability: object, calls_per_run: int) -> None:
    """Refuse, naming the tool, a manifest the assistant cannot honour.
    `calls_per_run` is the run's tool-call budget, the one limit enforced."""
    if not isinstance(capability, Capability):
        raise ValueError(f"tool {tool_name!r} has no capability manifest")
    if capability.name != tool_name:
        raise ValueError(f"tool {tool_name!r} carries the manifest of {capability.name!r}")
    if capability.side_effect != "read":
        raise ValueError(
            f"tool {tool_name!r} declares the side effect {capability.side_effect!r}: "
            "no write has an approval route yet"
        )
    if capability.retry != "none":
        raise ValueError(
            f"tool {tool_name!r} declares the retry class {capability.retry!r}: "
            "a tool's failure propagates, never retried"
        )
    if capability.calls_per_run != calls_per_run:
        raise ValueError(
            f"tool {tool_name!r} declares {capability.calls_per_run} calls a run: the "
            f"one limit enforced is the run's {calls_per_run}, every tool together"
        )

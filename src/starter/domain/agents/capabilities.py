"""What a tool may do, declared beside it -- and whether the assistant can honour it.

The fields are `.claude/rules/langgraph/graphs.md`'s ("Tools"); the input's
schema is the tool's own. What holds each one:

- `side_effect` -- here: `read`, or `write` -- a write only with the task
  list's writer, idempotent, with an audit event, and run only after the
  owner approves it (ASSISTANT-WRITE-APPROVAL). A tool declaring `read` is
  given a view of its store that refuses a write, so the declaration is not
  the only guard.
- `retry` -- here: only `"none"`, since a tool's failure propagates.
- `calls_per_run` -- here: only the run's budget, the one limit enforced
  (`check_tool_calls` in `run_tools`, every tool together).
- `timeout_seconds` -- the store's own wait, which the tool takes from it.
- `idempotent` and `audit_event` -- a write's, held by the writer: once per
  key, each decision recorded (docs/decisions/0008).

Checked once, when the graph is composed: its tools are fixed then. A write's
values are checked again immediately before it runs, by the writer.
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


def check_capability(
    tool_name: str,
    capability: object,
    calls_per_run: int,
    *,
    writer_given: bool,
    builder_given: bool = False,
) -> None:
    """Refuse, naming the tool, a manifest the assistant cannot honour.
    `calls_per_run` is the run's tool-call budget, the one limit enforced;
    `writer_given`, whether the task list's writer was composed with the tools;
    `builder_given`, whether the tool says how its arguments become a write."""
    if not isinstance(capability, Capability):
        raise ValueError(f"tool {tool_name!r} has no capability manifest")
    if capability.name != tool_name:
        raise ValueError(f"tool {tool_name!r} carries the manifest of {capability.name!r}")
    if capability.side_effect not in ("read", "write"):
        raise ValueError(
            f"tool {tool_name!r} declares the side effect {capability.side_effect!r}: "
            "a tool reads, or writes after the owner's approval"
        )
    if capability.side_effect == "write":
        _check_write(tool_name, capability, writer_given, builder_given)
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


def _check_write(
    tool_name: str, capability: Capability, writer_given: bool, builder_given: bool
) -> None:
    """A write runs once per key and is recorded, through the writer, after the
    owner approves: a manifest that promises less, or a write with no writer to
    apply it, is refused."""
    if not writer_given:
        raise ValueError(
            f"tool {tool_name!r} declares a write, and no writer was given to apply it"
        )
    if not capability.idempotent:
        raise ValueError(f"tool {tool_name!r} declares a write that is not idempotent")
    if capability.audit_event is None:
        raise ValueError(f"tool {tool_name!r} declares a write with no audit event")
    if not builder_given:
        raise ValueError(f"tool {tool_name!r} declares a write with no builder for it")

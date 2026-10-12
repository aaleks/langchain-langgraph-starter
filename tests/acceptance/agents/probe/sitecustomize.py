"""A connection probe, loaded into every Python process the local server starts.

`tests/localserver.py` puts this directory on PYTHONPATH and names a log file in
PROBE_LOG; `scripts/serve.sh` passes both on. Python imports `sitecustomize`
at start-up, and this one installs an audit hook (PEP 578) that appends, per
process: a `start` record with its argv, then every connect, name lookup and
datagram send the `socket` module makes.

What it cannot see, and why that is acceptable here:
- An asyncio connect to a *literal IP* raises no `socket.connect` event on
  Windows' Proactor loop (measured). Every target the local-only environment
  guards against is a hostname, recorded at its lookup.
- Native code that opens sockets itself (grpcio's C core) and processes that
  are not Python (`uv`) raise no audit events at all. Neither is how LangSmith,
  the CLI's analytics or the version check is reached; `strace` (Linux) is the
  tool that sees everything, and runtime.md keeps it for that.
"""

import json
import os
import sys

_LOG = os.environ.get("PROBE_LOG")

_LOOKUPS = {
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyname_ex",
    "socket.gethostbyaddr",
    "socket.getnameinfo",
}
_SENDS = {"socket.sendto", "socket.sendmsg"}


def _record(kind: str, detail: object) -> None:
    try:
        with open(_LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"pid": os.getpid(), "kind": kind, "detail": detail}) + "\n")
    except Exception:  # noqa: BLE001 -- a probe must never break what it watches
        pass


def _host(value: object) -> object:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, tuple):
        return [_host(part) for part in value]
    return value if value is None or isinstance(value, (str, int)) else repr(value)


def _hook(event: str, args: tuple) -> None:
    if event == "socket.connect":
        _record("connect", _host(args[1]))
    elif event in _LOOKUPS:
        # getnameinfo's first argument is a (host, port) address; the rest, a host.
        target = args[0][0] if event == "socket.getnameinfo" else args[0]
        _record("lookup", _host(target))
    elif event in _SENDS and len(args) > 1 and args[-1] is not None:
        _record("connect", _host(args[-1]))


if _LOG:
    _record("start", sys.argv)
    sys.addaudithook(_hook)

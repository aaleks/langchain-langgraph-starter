"""A connection probe, loaded into every Python process the local server starts.

`tests/localserver.py` puts this directory on PYTHONPATH and names a log file in
PROBE_LOG; `scripts/serve.sh` passes both on. Python imports `sitecustomize`
at start-up, and this one installs an audit hook (PEP 578) that appends, per
process: one `start` record with its argv, then every `socket.connect` and
`socket.getaddrinfo`.

Blind spot, measured on Windows: an asyncio connect to a literal IP raises no
`socket.connect` event on the Proactor loop. Every target the local-only
environment guards against -- LangSmith, the CLI's analytics, PyPI -- is a
hostname, and its lookup is recorded, synchronous or not.
"""

import json
import os
import sys

_LOG = os.environ.get("PROBE_LOG")


def _record(kind: str, detail: object) -> None:
    try:
        with open(_LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"pid": os.getpid(), "kind": kind, "detail": detail}) + "\n")
    except Exception:  # noqa: BLE001 -- a probe must never break what it watches
        pass


def _hook(event: str, args: tuple) -> None:
    if event == "socket.connect":
        address = args[1]
        _record("connect", list(address) if isinstance(address, tuple) else repr(address))
    elif event == "socket.getaddrinfo":
        host = args[0]
        _record("lookup", host.decode() if isinstance(host, bytes) else host)


if _LOG:
    _record("start", sys.argv)
    sys.addaudithook(_hook)

"""Who may change anything through the local server -- the owner's choice
(approve-task-writes, docs/decisions/0009): no web page but Agent Chat UI's.

CORS limits what a page may read. It never stops a page sending a "simple"
request -- a POST with a `text/plain` body -- which a browser sends without
asking first, and which the server would run. These rules refuse it before any
route sees it.
"""

from __future__ import annotations

# The one origin a page may change anything from: Agent Chat UI's default.
BROWSER_ORIGINS = frozenset({"http://localhost:3000"})
# This machine, by name: a Host naming anything else is a page that rebound a
# name of its own to 127.0.0.1 (DNS rebinding), whose requests count as
# same-origin to the browser.
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})
# Methods that change nothing on this server; CORS answers the preflights.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# A body a browser cannot send to another origin without asking first.
JSON = "application/json"
# The development server's own routes, which nothing here uses: `/deploy` runs
# a LangSmith deployment (docs/decisions/0004 forbids one), `/internal/truncate`
# wipes every thread, paused approvals included.
NOT_SERVED = ("/deploy/", "/internal/")


def request_refusal(
    *,
    socket: bool,
    method: str,
    path: str,
    host: str | None,
    origin: str | None,
    content_type: str | None,
    has_body: bool,
) -> str | None:
    """Why a request to the local server is refused, or None to let it through.

    `socket`: a WebSocket handshake. CORS never applies to one, and the server's
    event stream starts and resumes runs over it, so it is never "safe", though
    its handshake is a GET (approve-task-writes, verify finding 31). `has_body`:
    whether a body was sent -- the SDK's cancel sends none, and a page's empty
    POST still carries its `Origin`. `path`: the route's -- the development
    server's own `/deploy` and `/internal/` routes are never served."""
    if host is None or _hostname(host) not in LOCAL_HOSTS:
        return "the Host is not this machine"
    if path == "/deploy" or path.startswith(NOT_SERVED):
        return f"the route {path} is not served here"
    if not socket and method.upper() in SAFE_METHODS:
        return None
    if origin is not None and origin not in BROWSER_ORIGINS:
        return f"the origin {origin!r} may not change anything here"
    if (
        has_body
        and method.upper() in {"POST", "PUT", "PATCH"}
        and _media_type(content_type) != JSON
    ):
        return f"a request body must be {JSON}"
    return None


def _hostname(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0] if ":" in host else host


def _media_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()

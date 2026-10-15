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


def request_refusal(
    *, method: str, host: str | None, origin: str | None, content_type: str | None
) -> str | None:
    """Why a request to the local server is refused, or None to let it through."""
    if host is None or _hostname(host) not in LOCAL_HOSTS:
        return "the Host is not this machine"
    if method.upper() in SAFE_METHODS:
        return None
    if origin is not None and origin not in BROWSER_ORIGINS:
        return f"the origin {origin!r} may not change anything here"
    if method.upper() in {"POST", "PUT", "PATCH"} and _media_type(content_type) != JSON:
        return f"a request body must be {JSON}"
    return None


def _hostname(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0] if ":" in host else host


def _media_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()

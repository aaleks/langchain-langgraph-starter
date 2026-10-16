"""Who may change anything through the local server -- a pure decision on a
request's kind, method, path and headers."""

from __future__ import annotations

import pytest

from starter.domain.access import request_refusal

# Each row: (WebSocket?, method, path, Host, Origin, Content-Type, a body sent?)
REFUSED = [
    (
        False,
        "POST",
        "/threads",
        "127.0.0.1:2024",
        "https://evil.example",
        "text/plain",
        True,
        "origin",
    ),
    (
        False,
        "POST",
        "/threads",
        "127.0.0.1:2024",
        "https://evil.example",
        "application/json",
        True,
        "origin",
    ),
    (False, "POST", "/threads", "127.0.0.1:2024", "https://evil.example", None, False, "origin"),
    (
        False,
        "POST",
        "/threads",
        "127.0.0.1:2024",
        None,
        "text/plain;charset=UTF-8",
        True,
        "application/json",
    ),
    (False, "PATCH", "/threads/t1", "127.0.0.1:2024", None, "text/plain", True, "application/json"),
    (False, "PUT", "/store/items", "127.0.0.1:2024", None, "text/plain", True, "application/json"),
    (False, "DELETE", "/threads/t1", "127.0.0.1:2024", "null", None, False, "origin"),
    (False, "GET", "/threads/t1", "evil.example:2024", None, None, False, "Host"),
    (False, "POST", "/threads", None, None, "application/json", True, "Host"),
    (False, "POST", "/deploy", "127.0.0.1:2024", None, "application/json", True, "not served"),
    (False, "GET", "/deploy/d1/stream", "127.0.0.1:2024", None, None, False, "not served"),
    (False, "POST", "/internal/truncate", "127.0.0.1:2024", None, None, False, "not served"),
    (
        True,
        "GET",
        "/threads/t1/stream/events",
        "127.0.0.1:2024",
        "https://evil.example",
        None,
        False,
        "origin",
    ),
    (True, "GET", "/threads/t1/stream/events", "127.0.0.1:2024", "null", None, False, "origin"),
    (True, "GET", "/threads/t1/stream/events", "evil.example:2024", None, None, False, "Host"),
]
REFUSED_IDS = [
    "page-text",
    "page-json",
    "page-empty",
    "body-text",
    "patch-body-text",
    "put-body-text",
    "null-origin",
    "rebound-host",
    "no-host",
    "deploy",
    "deploy-stream",
    "truncate",
    "page-socket",
    "null-origin-socket",
    "rebound-host-socket",
]

LET_THROUGH = [
    (False, "POST", "/threads", "127.0.0.1:2024", None, "application/json", True),
    (False, "POST", "/threads/t1/runs/r1/cancel", "127.0.0.1:2024", None, None, False),
    (
        False,
        "POST",
        "/threads",
        "localhost:2024",
        "http://localhost:3000",
        "application/json; charset=utf-8",
        True,
    ),
    (False, "GET", "/threads/t1", "[::1]:2024", "https://evil.example", None, False),
    (False, "OPTIONS", "/threads", "127.0.0.1:2024", "https://evil.example", None, False),
    (False, "DELETE", "/threads/t1", "localhost", None, None, False),
    (False, "GET", "/deployments", "127.0.0.1:2024", None, None, False),
    (True, "GET", "/threads/t1/stream/events", "127.0.0.1:2024", None, None, False),
    (
        True,
        "GET",
        "/threads/t1/stream/events",
        "localhost:2024",
        "http://localhost:3000",
        None,
        False,
    ),
]
LET_THROUGH_IDS = [
    "the-sdk",
    "the-sdk-cancel",
    "agent-chat-ui",
    "a-read",
    "a-preflight",
    "a-delete-no-body",
    "a-path-only-like-deploy",
    "the-sdk-socket",
    "agent-chat-ui-socket",
]


class TestRequestGuard:
    """LOCAL-SERVER-REQUEST-GUARD: The local server SHALL refuse, before any route sees
    it, a request the domain policy `request_refusal` refuses -- an HTTP request with
    403, a WebSocket handshake by closing it unaccepted: one whose `Host` is not this
    machine -- `127.0.0.1`, `localhost` or `[::1]`, any port -- whatever it is; one to
    or under `/deploy`, or under `/internal/` -- the route's path, a mount prefix
    aside -- the development server's own routes, which deploy through LangSmith or
    wipe every thread; a WebSocket whose `Origin` is
    present and not `http://localhost:3000`, since CORS never applies to one and the
    server's event stream starts and resumes runs over it; and an HTTP request other
    than `GET`, `HEAD` or `OPTIONS` whose `Origin` is present and not
    `http://localhost:3000`, or that sends a body, for `POST`, `PUT` or `PATCH`, that
    is not `application/json`. Nothing but HTTP, WebSockets and the server's own
    lifespan SHALL reach the server. CORS limits what a page may read; this refuses
    what a page may send."""

    @pytest.mark.parametrize(
        ("socket", "method", "path", "host", "origin", "content_type", "has_body", "because"),
        REFUSED,
        ids=REFUSED_IDS,
    )
    def test_requests_refused(
        self, socket, method, path, host, origin, content_type, has_body, because
    ):
        refusal = request_refusal(
            socket=socket,
            method=method,
            path=path,
            host=host,
            origin=origin,
            content_type=content_type,
            has_body=has_body,
        )

        assert refusal is not None and because in refusal

    @pytest.mark.parametrize(
        ("socket", "method", "path", "host", "origin", "content_type", "has_body"),
        LET_THROUGH,
        ids=LET_THROUGH_IDS,
    )
    def test_counter_example_requests_let_through(
        self, socket, method, path, host, origin, content_type, has_body
    ):
        assert (
            request_refusal(
                socket=socket,
                method=method,
                path=path,
                host=host,
                origin=origin,
                content_type=content_type,
                has_body=has_body,
            )
            is None
        )

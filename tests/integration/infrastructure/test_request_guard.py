"""The request guard in front of the local server's routes: the domain's
`request_refusal` acted on, before anything behind it sees the request.

Driven with hand-built ASGI scopes, so each header -- none included -- is exactly
the row's; the live tests send the same through `scripts/serve.sh`.
"""

from __future__ import annotations

import asyncio

import pytest

from starter.infrastructure.server.guard import LocalRequestGuard
from tests.unit.domain.test_access import (
    LET_THROUGH,
    LET_THROUGH_IDS,
    REFUSED,
    REFUSED_IDS,
)

BODY = b'{"assistant_id": "assistant"}'


def scope_for(socket, method, host, origin, content_type, has_body) -> dict:
    headers = []
    if host is not None:
        headers.append((b"host", host.encode()))
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if content_type is not None:
        headers.append((b"content-type", content_type.encode()))
    if has_body:
        headers.append((b"content-length", str(len(BODY)).encode()))
    elif method in ("POST", "PUT", "PATCH"):
        headers.append((b"content-length", b"0"))  # as the SDK's cancel sends it
    return {
        "type": "websocket" if socket else "http",
        "method": method,
        "path": "/threads",
        "headers": headers,
    }


def through_the_guard(scope: dict) -> tuple[list[str], list[dict]]:
    """What reached the route behind the guard, and what was sent back."""
    seen: list[str] = []
    sent: list[dict] = []

    async def route(scope, receive, send):
        seen.append(scope["type"])
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})
        elif scope["type"] == "websocket":
            await send({"type": "websocket.accept"})

    first = (
        {"type": "websocket.connect"}
        if scope["type"] == "websocket"
        else {"type": "http.request", "body": BODY, "more_body": False}
    )
    messages = iter([first])

    async def receive():
        return next(messages, {"type": "http.disconnect"})

    async def send(message):
        sent.append(message)

    asyncio.run(LocalRequestGuard(route)(scope, receive, send))
    return seen, sent


class TestGuardInFrontOfEveryRoute:
    """LOCAL-SERVER-REQUEST-GUARD: The local server SHALL refuse, before any route sees
    it, a request the domain policy `request_refusal` refuses -- an HTTP request with
    403, a WebSocket handshake by closing it unaccepted: one whose `Host` is not this
    machine -- `127.0.0.1`, `localhost` or `[::1]`, any port -- whatever it is; a
    WebSocket whose `Origin` is present and not `http://localhost:3000`, since CORS
    never applies to one and the server's event stream starts and resumes runs over
    it; and an HTTP request other than `GET`, `HEAD` or `OPTIONS` whose `Origin` is
    present and not `http://localhost:3000`, or that sends a body, for `POST`, `PUT` or
    `PATCH`, that is not `application/json`. Nothing but HTTP, WebSockets and the
    server's own lifespan SHALL reach the server. CORS limits what a page may read;
    this refuses what a page may send."""

    @pytest.mark.parametrize(
        ("socket", "method", "host", "origin", "content_type", "has_body", "because"),
        REFUSED,
        ids=REFUSED_IDS,
    )
    def test_refused_before_any_route(
        self, socket, method, host, origin, content_type, has_body, because
    ):
        seen, sent = through_the_guard(
            scope_for(socket, method, host, origin, content_type, has_body)
        )

        assert seen == []
        if socket:
            assert [m["type"] for m in sent] == ["websocket.close"]
        else:
            assert sent[0]["type"] == "http.response.start" and sent[0]["status"] == 403
            assert because.encode() in b"".join(m.get("body", b"") for m in sent)

    @pytest.mark.parametrize(
        ("socket", "method", "host", "origin", "content_type", "has_body"),
        LET_THROUGH,
        ids=LET_THROUGH_IDS,
    )
    def test_counter_example_let_through_to_the_route(
        self, socket, method, host, origin, content_type, has_body
    ):
        seen, _ = through_the_guard(scope_for(socket, method, host, origin, content_type, has_body))

        assert seen == ["websocket" if socket else "http"]

    def test_a_body_sent_in_chunks_is_still_a_body(self):
        scope = scope_for(False, "POST", "127.0.0.1:2024", None, "text/plain", False)
        scope["headers"] = [
            (b"host", b"127.0.0.1:2024"),
            (b"content-type", b"text/plain"),
            (b"transfer-encoding", b"chunked"),
        ]

        seen, sent = through_the_guard(scope)

        assert seen == [] and sent[0]["status"] == 403

    def test_the_lifespan_passes_and_nothing_else_does(self):
        assert through_the_guard({"type": "lifespan"})[0] == ["lifespan"]
        local = [(b"host", b"127.0.0.1:2024")]
        assert through_the_guard({"type": "webtransport", "headers": local}) == ([], [])

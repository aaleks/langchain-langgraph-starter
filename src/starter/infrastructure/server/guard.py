"""The local server's request guard: `http.app` in langgraph.json, so it runs
before CORS and every route (docs/decisions/0009, LOCAL-SERVER-REQUEST-GUARD).

Loaded by the server as a file, not as a package module, so every import here
is absolute.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketClose

from starter.domain.access import request_refusal


class LocalRequestGuard:
    """Refuses a request the domain's `request_refusal` refuses -- a write or a
    WebSocket from a page other than Agent Chat UI's, a body a browser could send
    without asking, or a Host that is not this machine: an HTTP request with 403,
    a WebSocket handshake closed before it is accepted. Nothing but HTTP,
    WebSockets and the server's lifespan reaches the server: what this guard does
    not know, it does not let through."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] not in ("http", "websocket"):
            return
        headers = {
            name.decode("latin-1"): value.decode("latin-1") for name, value in scope["headers"]
        }
        socket = scope["type"] == "websocket"
        refusal = request_refusal(
            socket=socket,
            method=scope.get("method", "GET"),
            host=headers.get("host"),
            origin=headers.get("origin"),
            content_type=headers.get("content-type"),
            has_body=headers.get("content-length", "0") != "0" or "transfer-encoding" in headers,
        )
        if refusal is None:
            await self.app(scope, receive, send)
        elif socket:
            # Closed before it is accepted: the server answers the handshake 403.
            await WebSocketClose(code=1008, reason=refusal)(scope, receive, send)
        else:
            await JSONResponse({"detail": refusal}, status_code=403)(scope, receive, send)


app = Starlette(middleware=[Middleware(LocalRequestGuard)])

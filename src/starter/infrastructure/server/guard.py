"""The local server's request guard: `http.app` in langgraph.json, so it runs
before CORS and every route (docs/decisions/0009, LOCAL-SERVER-REQUEST-GUARD).

Loaded by the server as a file, not as a package module, so every import here
is absolute.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse

from starter.domain.access import request_refusal


class LocalRequestGuard:
    """Refuses, with 403, a request the domain's `request_refusal` refuses: a
    write from a page other than Agent Chat UI's, a body a browser could send
    without asking, or a Host that is not this machine."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            name.decode("latin-1"): value.decode("latin-1") for name, value in scope["headers"]
        }
        refusal = request_refusal(
            method=scope["method"],
            host=headers.get("host"),
            origin=headers.get("origin"),
            content_type=headers.get("content-type"),
        )
        if refusal is None:
            await self.app(scope, receive, send)
            return
        await JSONResponse({"detail": refusal}, status_code=403)(scope, receive, send)


app = Starlette(middleware=[Middleware(LocalRequestGuard)])

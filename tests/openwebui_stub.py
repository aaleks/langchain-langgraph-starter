"""A stand-in for Open WebUI's OpenAI-compatible chat endpoint, on 127.0.0.1.

It answers `POST /api/chat/completions` the way Open WebUI does -- an OpenAI
chat completion, or first the HTTP failures it was told to give -- and records
each request's path, Authorization header and JSON body, so a test can see what
the real client sent. It is not a model: its replies are scripted -- a tool
call, or text -- then fixed, and a test asserts the request, never the
answer's text.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

STUB_ANSWER = "stubbed reply"


def tool_call(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """A scripted reply proposing one call of `name`, as Open WebUI sends it."""
    return {"name": name, "arguments": arguments or {}}


Reply = str | dict[str, Any] | list[dict[str, Any]]


def _message(reply: Reply, number: int) -> dict[str, Any]:
    """Text, one `tool_call(...)`, or a list of them proposed in one turn."""
    if isinstance(reply, str):
        return {"role": "assistant", "content": reply}
    calls = reply if isinstance(reply, list) else [reply]
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_stub_{number}_{index}",
                "type": "function",
                "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
            }
            for index, call in enumerate(calls)
        ],
    }


@dataclass
class Stub:
    url: str
    requests: list[dict] = field(default_factory=list)


@contextmanager
def openwebui_stub(failures: Iterable[int] = (), replies: Iterable[Reply] = ()) -> Iterator[Stub]:
    """`failures`: HTTP statuses to answer the first requests with, in order.
    `replies`: what the requests after them are answered with, in order -- text,
    or a `tool_call(...)` -- then `STUB_ANSWER` for every one after those."""
    stub = Stub(url="")
    pending = list(failures)
    scripted = list(replies)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 -- the http.server API
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            stub.requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": body,
                }
            )
            if self.path != "/api/chat/completions":
                self.send_error(404)
                return
            if pending:
                self.send_error(pending.pop(0))
                return
            message = _message(scripted.pop(0) if scripted else STUB_ANSWER, len(stub.requests))
            reply = {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if "tool_calls" in message else "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            payload = json.dumps(reply).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args) -> None:  # quiet
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    stub.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield stub
    finally:
        server.shutdown()
        server.server_close()

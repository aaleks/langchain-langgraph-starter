"""A stand-in for Open WebUI's OpenAI-compatible chat endpoint, on 127.0.0.1.

It answers `POST /api/chat/completions` the way Open WebUI does -- an OpenAI
chat completion, or first the HTTP failures it was told to give -- and records
each request's path, Authorization header and JSON body, so a test can see what
the real client sent. It is not a model: its answer is fixed, and a test
asserts the request, never the answer's text.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STUB_ANSWER = "stubbed reply"


@dataclass
class Stub:
    url: str
    requests: list[dict] = field(default_factory=list)


@contextmanager
def openwebui_stub(failures: Iterable[int] = ()) -> Iterator[Stub]:
    """`failures`: HTTP statuses to answer the first requests with, in order."""
    stub = Stub(url="")
    pending = list(failures)

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
            reply = {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": STUB_ANSWER},
                        "finish_reason": "stop",
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

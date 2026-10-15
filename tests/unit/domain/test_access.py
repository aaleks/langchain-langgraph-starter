"""Who may change anything through the local server -- a pure decision on a
request's method and headers."""

from __future__ import annotations

import pytest

from starter.domain.access import request_refusal


class TestRequestGuard:
    """LOCAL-SERVER-REQUEST-GUARD: The local server SHALL refuse with 403, before any route
    sees it, a request the domain policy `request_refusal` refuses: one whose `Host`
    is not this machine -- `127.0.0.1`, `localhost` or `[::1]`, any port -- whatever
    its method; and one other than `GET`, `HEAD` or `OPTIONS` whose `Origin` is
    present and not `http://localhost:3000`, or whose body, for `POST`, `PUT` or
    `PATCH`, is not `application/json`. CORS limits what a page may read; this
    refuses what a page may send."""

    @pytest.mark.parametrize(
        ("method", "host", "origin", "content_type", "because"),
        [
            ("POST", "127.0.0.1:2024", "https://evil.example", "text/plain", "origin"),
            ("POST", "127.0.0.1:2024", "https://evil.example", "application/json", "origin"),
            ("POST", "127.0.0.1:2024", None, "text/plain;charset=UTF-8", "application/json"),
            ("DELETE", "127.0.0.1:2024", "null", None, "origin"),
            ("GET", "evil.example:2024", None, None, "Host"),
            ("POST", None, None, "application/json", "Host"),
        ],
        ids=["page-text", "page-json", "body-text", "null-origin", "rebound-host", "no-host"],
    )
    def test_requests_refused(self, method, host, origin, content_type, because):
        refusal = request_refusal(
            method=method, host=host, origin=origin, content_type=content_type
        )

        assert refusal is not None and because in refusal

    @pytest.mark.parametrize(
        ("method", "host", "origin", "content_type"),
        [
            ("POST", "127.0.0.1:2024", None, "application/json"),
            ("POST", "localhost:2024", "http://localhost:3000", "application/json; charset=utf-8"),
            ("GET", "[::1]:2024", "https://evil.example", None),
            ("OPTIONS", "127.0.0.1:2024", "https://evil.example", None),
            ("DELETE", "localhost", None, None),
        ],
        ids=["the-sdk", "agent-chat-ui", "a-read", "a-preflight", "a-delete-no-body"],
    )
    def test_counter_example_requests_let_through(self, method, host, origin, content_type):
        assert (
            request_refusal(method=method, host=host, origin=origin, content_type=content_type)
            is None
        )

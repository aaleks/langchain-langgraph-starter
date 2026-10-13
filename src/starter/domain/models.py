"""Which model the assistant uses -- decided from the settings, as plain values."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

ModelChoice = Literal["openwebui", "offline"]


def choose_model(url: str, key: str, model: str) -> ModelChoice:
    """Open WebUI when all three are set, the offline model when none is.

    Partly configured is a mistake the owner should hear about at start, not a
    silent offline assistant: refused, naming each one missing. So is a URL that
    is not Open WebUI's address, `http(s)://host[:port][/path]`: without a
    scheme it would surface as a nameless connection error, retried as if the
    network were at fault; with a query or a fragment, as a 404 at the first
    run. The refusal never quotes the value: two lines swapped would put the
    key there.
    """
    given = {"OPENWEBUI_URL": url, "OPENWEBUI_API_KEY": key, "OPENWEBUI_MODEL": model}
    missing = [name for name, value in given.items() if not value]
    if len(missing) == len(given):
        return "offline"
    if missing:
        raise ValueError(
            "Open WebUI is partly configured (.env.example lists all three) -- "
            f"missing: {', '.join(missing)}"
        )
    if not _is_open_webui_address(url):
        raise ValueError(
            "OPENWEBUI_URL is not an http(s) URL of Open WebUI -- a host, a valid "
            "port if any, and no query; e.g. http://localhost:3000"
        )
    return "openwebui"


def api_base(url: str) -> str:
    """Open WebUI's API, under its address: `<url>/api`. A URL already ending in
    `/api` is taken as the API itself: an owner who copies the API's address
    rather than the site's means the same server."""
    root = url.rstrip("/")
    return root if root.endswith("/api") else root + "/api"


def _is_open_webui_address(url: str) -> bool:
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 -- raises on a port out of range or not a number
    except ValueError:  # `http://[::1` included
        return False
    return (
        parts.scheme in ("http", "https")
        and bool(parts.hostname)
        # "?" and "#", not the parsed parts: an empty query still breaks the address.
        and "?" not in url
        and "#" not in url
    )

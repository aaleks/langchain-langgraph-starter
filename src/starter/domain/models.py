"""Which model the assistant uses -- decided from the settings, as plain values."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

ModelChoice = Literal["openwebui", "offline"]


def choose_model(url: str, key: str, model: str) -> ModelChoice:
    """Open WebUI when all three are set, the offline model when none is.

    Partly configured is a mistake the owner should hear about at start, not a
    silent offline assistant: refused, naming each one missing. So is a URL that
    is not `http(s)://host` -- `localhost:3000` would otherwise surface as a
    nameless connection error, retried as if the network were at fault.
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
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(
            f"OPENWEBUI_URL is not an http(s) URL with a host -- {url!r}; "
            "e.g. http://localhost:3000"
        )
    return "openwebui"

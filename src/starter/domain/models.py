"""Which model the assistant uses -- decided from the settings, as plain values."""

from __future__ import annotations

from typing import Literal

ModelChoice = Literal["openwebui", "offline"]


def choose_model(url: str, key: str, model: str) -> ModelChoice:
    """Open WebUI when all three are set, the offline model when none is.

    Partly configured is a mistake the owner should hear about at start, not a
    silent offline assistant: refused, naming each one missing.
    """
    given = {"OPENWEBUI_URL": url, "OPENWEBUI_API_KEY": key, "OPENWEBUI_MODEL": model}
    missing = [name for name, value in given.items() if not value]
    if not missing:
        return "openwebui"
    if len(missing) == len(given):
        return "offline"
    raise ValueError(
        "Open WebUI is partly configured (.env.example lists all three) -- "
        f"missing: {', '.join(missing)}"
    )

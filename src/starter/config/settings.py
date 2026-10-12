"""The owner's settings: from the process environment, then `.env` for the rest.

`.env` is read into a dictionary and never written into `os.environ` -- loading
it there would hand its contents to every library that reads the environment,
LangSmith's among them. The environment wins, an empty value included: that is
how the test suite keeps the owner's `.env` out of every default test.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# The repository's .env, found from this file -- not from the working directory,
# which differs between a terminal, the server and a test.
DOTENV = Path(__file__).resolve().parents[3] / ".env"

NAMES = ("OPENWEBUI_URL", "OPENWEBUI_API_KEY", "OPENWEBUI_MODEL")


@dataclass(frozen=True)
class Settings:
    openwebui_url: str
    openwebui_api_key: str
    openwebui_model: str

    def __repr__(self) -> str:
        # Never the key: a settings object ends up in tracebacks and logs.
        key = "set" if self.openwebui_api_key else "empty"
        return (
            f"Settings(openwebui_url={self.openwebui_url!r}, openwebui_api_key=<{key}>, "
            f"openwebui_model={self.openwebui_model!r})"
        )


def read_settings(environ: Mapping[str, str], dotenv: Path) -> Settings:
    """Each setting from `environ` when it holds the name, else from `dotenv`."""
    from_file = dotenv_values(dotenv) if dotenv.is_file() else {}

    def value(name: str) -> str:
        if name in environ:
            return environ[name]
        return from_file.get(name) or ""

    url, key, model = (value(name).strip() for name in NAMES)
    return Settings(openwebui_url=url, openwebui_api_key=key, openwebui_model=model)


def settings_from_process() -> Settings:
    """The settings this process runs with: its environment, then the repository's `.env`."""
    return read_settings(os.environ, DOTENV)

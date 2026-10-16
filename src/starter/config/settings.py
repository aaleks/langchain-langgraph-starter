"""The owner's settings: from the process environment, then `.env` for the rest.

`.env` is read into a dictionary and never written into `os.environ` -- loading
it there would hand its contents to every library that reads the environment,
LangSmith's among them. The environment wins, an empty value included: that is
how the test suite keeps the owner's `.env` out of every default test -- and
when the environment holds every setting, the file is not even opened.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# The repository's .env, found from this file -- not from the working directory,
# which differs between a terminal, the server and a test. Right for the
# editable install `uv sync` makes; a non-editable install finds no .env here.
REPO = Path(__file__).resolve().parents[3]
DOTENV = REPO / ".env"
# The task list when TASKS_DB is empty: in the repository, ignored by git.
DEFAULT_TASKS_DB = REPO / ".data" / "tasks.sqlite3"
# The threads' checkpoints when CHECKPOINTS_DB is empty: beside the task list.
DEFAULT_CHECKPOINTS_DB = REPO / ".data" / "checkpoints.sqlite3"

NAMES = ("OPENWEBUI_URL", "OPENWEBUI_API_KEY", "OPENWEBUI_MODEL", "TASKS_DB", "CHECKPOINTS_DB")


@dataclass(frozen=True)
class Settings:
    openwebui_url: str
    openwebui_api_key: str
    openwebui_model: str
    # No default: a settings object built in code names its task list, or it
    # would open the repository's own -- a test among them (task-store-read-only).
    tasks_db: str
    # A default, unlike the task list's: only the local server's checkpointer
    # opens this file, from the process's own settings (durable-approvals).
    checkpoints_db: str = ""

    def __repr__(self) -> str:
        # Never the key: a settings object ends up in tracebacks and logs.
        key = "set" if self.openwebui_api_key else "empty"
        return (
            f"Settings(openwebui_url={self.openwebui_url!r}, openwebui_api_key=<{key}>, "
            f"openwebui_model={self.openwebui_model!r}, tasks_db={self.tasks_db!r}, "
            f"checkpoints_db={self.checkpoints_db!r})"
        )

    __str__ = __repr__


def read_settings(environ: Mapping[str, str], dotenv: Path) -> Settings:
    """Each setting from `environ` when it holds the name, else from `dotenv`.

    Values are stripped: a value of only spaces reads as empty.
    """
    needs_file = any(name not in environ for name in NAMES)
    from_file = _read_dotenv(dotenv) if needs_file else {}

    def value(name: str) -> str:
        if name in environ:
            return environ[name]
        return from_file.get(name) or ""

    url, key, model, tasks_db, checkpoints_db = (value(name).strip() for name in NAMES)
    return Settings(
        openwebui_url=url,
        openwebui_api_key=key,
        openwebui_model=model,
        tasks_db=tasks_db,
        checkpoints_db=checkpoints_db,
    )


def tasks_db_path(settings: Settings) -> Path:
    """The task list's file: `TASKS_DB`, a relative path taken from the repository
    -- never the working directory, which differs between a terminal, the server
    and a test -- or the repository's `.data/tasks.sqlite3` when it is empty."""
    if not settings.tasks_db:
        return DEFAULT_TASKS_DB
    return REPO / settings.tasks_db  # an absolute path replaces REPO


def checkpoints_db_path(settings: Settings) -> Path:
    """The threads' checkpoint file: `CHECKPOINTS_DB`, taken as `TASKS_DB` is, or
    the repository's `.data/checkpoints.sqlite3` when it is empty. Never the task
    list's own file, which only the task store opens (docs/decisions/0006)."""
    path = (
        REPO / settings.checkpoints_db  # an absolute path replaces REPO
        if settings.checkpoints_db
        else DEFAULT_CHECKPOINTS_DB
    )
    if path.resolve() == tasks_db_path(settings).resolve():
        raise ValueError(
            f"the checkpoint file, {path}, is the task list's own (TASKS_DB): "
            "set CHECKPOINTS_DB to a file of its own"
        )
    return path


def _read_dotenv(dotenv: Path) -> dict[str, str | None]:
    if not dotenv.is_file():
        return {}
    try:
        # As written: expanding ${NAME} would read os.environ behind `environ`'s back.
        return dotenv_values(dotenv, encoding="utf-8", interpolate=False)
    except UnicodeDecodeError as error:
        # A .env saved as UTF-16 (Windows PowerShell's `>`) fails here; say where.
        raise ValueError(f"{dotenv} is not UTF-8 text -- save it as UTF-8") from error


def settings_from_process() -> Settings:
    """The settings this process runs with: its environment, then the repository's `.env`."""
    return read_settings(os.environ, DOTENV)

"""The task list: one SQLite file, the only module that opens it
(docs/decisions/0006-the-task-store.md)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from starter.domain.agents.budgets import TASK_READ_TIMEOUT_SECONDS
from starter.domain.tasks import NewTask, TaskPage, TaskRow

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE tasks (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT NOT NULL CHECK (length(trim(title)) > 0),
  assignee   TEXT NOT NULL DEFAULT '',
  notes      TEXT NOT NULL DEFAULT '',
  status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class TaskStore:
    """The task list at `path`. Each operation opens its own connection: the
    local server runs tools on worker threads, and a connection is not shared
    across them."""

    def __init__(self, path: Path, timeout: float = TASK_READ_TIMEOUT_SECONDS) -> None:
        self.path = path
        self.timeout = timeout

    def open(self) -> None:
        """Create the list at version 1 when the file is missing or empty; use a
        version-1 list as it is; refuse anything else, naming the file, before
        writing a byte to it."""
        if self.path.is_file() and self.path.stat().st_size > 0:
            version, tables = self._inspect()
            if version == SCHEMA_VERSION and "tasks" in tables:
                return
            if version != 0 or tables:
                raise ValueError(
                    f"{self.path} is not a task list this version reads: schema version "
                    f"{version}, tables {sorted(tables)} -- version {SCHEMA_VERSION} expected"
                )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(SCHEMA)
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def add(self, task: NewTask) -> int:
        """Add an open task; its id, which orders the list."""
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO tasks (title, assignee, notes) VALUES (?, ?, ?)",
                (task.title, task.assignee, task.notes),
            )
        return cursor.lastrowid

    def open_tasks(self, limit: int) -> TaskPage:
        """The open tasks in the order they were added: the first `limit`, and a
        count of the rest."""
        return self._page("status = 'open'", (), limit)

    def search(self, query: str, limit: int) -> TaskPage:
        """The open tasks whose title or notes contain `query` -- ASCII letters in
        any case, as SQLite's LIKE matches them; `%`, `_` and `\\` as themselves."""
        pattern = "%" + _escape_like(query) + "%"
        return self._page(
            "status = 'open' AND (title LIKE ? ESCAPE '\\' OR notes LIKE ? ESCAPE '\\')",
            (pattern, pattern),
            limit,
        )

    def _page(self, where: str, params: tuple[str, ...], limit: int) -> TaskPage:
        # A read never writes: the connection is read-only.
        with closing(self._connect(read_only=True)) as db:
            rows = db.execute(
                f"SELECT id, title, assignee, notes FROM tasks WHERE {where} ORDER BY id LIMIT ?",
                (*params, limit),
            ).fetchall()
            matched = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
        tasks: list[TaskRow] = [
            {"id": id_, "title": title, "assignee": assignee, "notes": notes}
            for id_, title, assignee, notes in rows
        ]
        return {"tasks": tasks, "more": matched - len(tasks)}

    def _inspect(self) -> tuple[int, set[str]]:
        """The file's schema version and tables, read without writing to it."""
        try:
            with closing(self._connect(read_only=True)) as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                tables = {
                    row[0]
                    for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' "
                        "AND name NOT LIKE 'sqlite_%'"
                    )
                }
        except sqlite3.DatabaseError as error:
            raise ValueError(f"{self.path} is not a task list: {error}") from error
        return version, tables

    def _connect(self, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            uri = self.path.resolve().as_uri() + "?mode=ro"
            return sqlite3.connect(uri, uri=True, timeout=self.timeout)
        return sqlite3.connect(self.path, timeout=self.timeout)


def _escape_like(text: str) -> str:
    """`text` matched as itself by `LIKE ... ESCAPE`: a query is data, never a pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

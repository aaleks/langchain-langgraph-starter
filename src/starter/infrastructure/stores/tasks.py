"""The task list: one SQLite file, the only module that opens it
(docs/decisions/0006-the-task-store.md)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from starter.domain.tasks import (
    ASSIGNEE_MAX,
    NOTES_MAX,
    TASK_STORE_TIMEOUT_SECONDS,
    TITLE_MAX,
    NewTask,
    TaskPage,
    TaskRow,
    readable,
)

SCHEMA_VERSION = 1
SCHEMA = f"""
CREATE TABLE tasks (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT NOT NULL CHECK (length(trim(title)) > 0 AND length(title) <= {TITLE_MAX}),
  assignee   TEXT NOT NULL DEFAULT '' CHECK (length(assignee) <= {ASSIGNEE_MAX}),
  notes      TEXT NOT NULL DEFAULT '' CHECK (length(notes) <= {NOTES_MAX}),
  status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class TaskStore:
    """The task list at `path`. Each operation opens its own connection: the
    local server runs tools on worker threads, and a connection is not shared
    across them."""

    def __init__(self, path: Path, timeout: float = TASK_STORE_TIMEOUT_SECONDS) -> None:
        self.path = path
        self.timeout = timeout

    def open(self) -> None:
        """Create the list at version 1 when the file is missing or holds no table
        at version 0; use a version-1 list as it is; refuse anything else, naming
        the file, before writing a byte to it."""
        if self.path.is_file() and self.path.stat().st_size > 0:
            version, tables = self._inspect()
            if _is_task_list(version, tables):
                return
            _refuse_unless_blank(self.path, version, tables)
        self._create()

    def add(self, task: NewTask) -> int:
        """Add an open task; its id, which orders the list."""
        with closing(_connect(self.path, self.timeout)) as db, db:
            cursor = db.execute(
                "INSERT INTO tasks (title, assignee, notes) VALUES (?, ?, ?)",
                (task.title, task.assignee, task.notes),
            )
        return cursor.lastrowid

    def reader(self, timeout: float) -> TaskReader:
        """A view of this list that reads and cannot write -- what a tool is given."""
        return TaskReader(self.path, timeout)

    def _inspect(self) -> tuple[int, set[str]]:
        """The file's schema version and tables, read without changing them.

        Read-write but `query_only`: a read-only connection cannot roll back a
        write that was interrupted -- its journal left beside the file -- and
        would call a list of tasks "not a task list" (verify pass 1, finding 2).
        """
        try:
            with _reading(self.path, self.timeout) as db:
                return _version_and_tables(db)
        except sqlite3.DatabaseError as error:
            if error.sqlite_errorname == "SQLITE_NOTADB":
                raise ValueError(f"{self.path} is not a task list: {error}") from error
            raise

    def _create(self) -> None:
        """The schema at version 1, in one transaction, the file looked at again
        inside it: another process may have opened it first."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(_connect(self.path, self.timeout, isolation_level=None)) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                version, tables = _version_and_tables(db)
                if not _is_task_list(version, tables):
                    _refuse_unless_blank(self.path, version, tables)
                    db.execute(SCHEMA)
                    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise


class TaskReader:
    """Reads the task list, through connections that refuse a write: a tool
    declaring `read` holds this, never the store (TOOLS-MANIFEST)."""

    def __init__(self, path: Path, timeout: float) -> None:
        self.path = path
        self.timeout = timeout

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with _reading(self.path, self.timeout) as db:
            yield db

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
        # One read transaction: the rows and the count see one state of the
        # list, and a lock is waited on once.
        with self.connection() as db:
            db.execute("BEGIN")
            rows = db.execute(
                f"SELECT id, {_cut('title', TITLE_MAX)}, {_cut('assignee', ASSIGNEE_MAX)}, "
                f"{_cut('notes', NOTES_MAX)} FROM tasks WHERE {where} ORDER BY id LIMIT ?",
                (*params, limit),
            ).fetchall()
            matched = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
            db.execute("COMMIT")
        tasks: list[TaskRow] = [
            {
                "id": id_,
                "title": readable(title, "title"),
                "assignee": readable(assignee, "assignee"),
                "notes": readable(notes, "notes"),
            }
            for id_, title, assignee, notes in rows
        ]
        return {"tasks": tasks, "more": matched - len(tasks)}


def _connect(path: Path, timeout: float, **options) -> sqlite3.Connection:
    return sqlite3.connect(path, timeout=timeout, **options)


@contextmanager
def _reading(path: Path, timeout: float) -> Iterator[sqlite3.Connection]:
    """A connection to an existing file that refuses every write but SQLite's own
    recovery of an interrupted one. `mode=rw`: a missing file is an error, never
    a new empty one."""
    uri = path.resolve().as_uri() + "?mode=rw"
    with closing(sqlite3.connect(uri, uri=True, timeout=timeout, isolation_level=None)) as db:
        db.execute("PRAGMA query_only = ON")
        # query_only is a pragma its holder could switch off; the authorizer
        # cannot be removed from SQL, and lets nothing but reading through.
        db.set_authorizer(_reads_only)
        # Text another program stored as text but not UTF-8 reads with U+FFFD:
        # without this, one such row makes the whole list unreadable.
        db.text_factory = lambda raw: raw.decode("utf-8", "replace")
        yield db


def _cut(column: str, limit: int) -> str:
    """A column as the read fetches it: text only, and never whole -- a file
    written without the limits could hold megabytes. Cut in bytes, not
    characters: SQLite counts text that is not UTF-8 as few characters however
    long it is. Sixteen times the limit in bytes is at least four times it in
    characters of UTF-8; the domain's `readable` then drops control characters
    and makes the final cut. Text past that is never read, so a field made
    mostly of control characters reads shorter than its limit, or empty."""
    # coalesce: `substr` of an empty blob is NULL, not an empty one.
    return (
        f"CASE WHEN typeof({column}) = 'text' "
        f"THEN coalesce(CAST(substr(CAST({column} AS BLOB), 1, {16 * limit}) AS TEXT), '') "
        "ELSE '' END"
    )


_READING = frozenset(
    {
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_FUNCTION,
    }
)


def _reads_only(action: int, first: str | None, second: str | None, *_: object) -> int:
    """Reading, and reading a pragma (`PRAGMA user_version`); nothing else --
    no write, no `PRAGMA query_only = OFF`, no `ATTACH`."""
    if action in _READING or (action == sqlite3.SQLITE_PRAGMA and second is None):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _version_and_tables(db: sqlite3.Connection) -> tuple[int, set[str]]:
    version = db.execute("PRAGMA user_version").fetchone()[0]
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    return version, tables


def _is_task_list(version: int, tables: set[str]) -> bool:
    return version == SCHEMA_VERSION and "tasks" in tables


def _refuse_unless_blank(path: Path, version: int, tables: set[str]) -> None:
    """A file at version 0 with no table is blank, and becomes the list; any
    other is someone else's, and is left alone."""
    if version != 0 or tables:
        raise ValueError(
            f"{path} is not a task list this version reads: schema version "
            f"{version}, tables {sorted(tables)} -- version {SCHEMA_VERSION} expected"
        )


def _escape_like(text: str) -> str:
    """`text` matched as itself by `LIKE ... ESCAPE`: a query is data, never a pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

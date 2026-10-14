# 6. The task list is one SQLite file, through the standard library, its schema versioned from the first

Date: 2026-10-13
Status: Accepted

## Context

The product is a task assistant (`docs/roadmap.md`). Slice 3 gives it the
task list to read, and slice 4 lets it propose writes. Three things settled
now are expensive to reverse:

- **The store.** Every later slice reads or writes it, and so does every
  owner's existing file.
- **The schema.** A file written by this version must still open under the
  next one, or be refused in words the owner can act on.
- **Who writes.** The product's rule is that every write the model proposes
  waits for the owner's approval. A store the model can write to by any other
  path breaks that rule.

The owner chose the library on 2026-10-13: the standard library's `sqlite3`,
over sqlite-utils, SQLAlchemy and LangChain's SQL toolkit
(`openspec/changes/archive/*-task-store-read-only/frame.md`).

## Decision

- **One SQLite file**, at the setting `TASKS_DB`. Its default is
  `.data/tasks.sqlite3` under the repository, and `.data/` is ignored by git.
  A relative path is taken from the repository's root, never from the working
  directory.
- **Through `sqlite3`** in `infrastructure/stores/tasks.py`, the only module
  that opens the file. Each operation opens its own connection, because the
  local server runs tools on worker threads. A busy file is waited on for
  `TASK_STORE_TIMEOUT_SECONDS`, which the tools' manifests declare and their
  readers take from them.
- **A tool is given a reader, never the store.** Its connections are
  read-write, for one reason: a read-only connection cannot roll back an
  interrupted write's journal, and would refuse a list of tasks. Two guards
  keep them reading:
  - an authorizer, which SQL cannot remove, lets through reading and reading
    a pragma only;
  - `query_only` refuses every write except SQLite's own recovery.

  A read is one transaction, so its rows and its count see one state of the
  list. Each field is cut to its limit and stripped of control characters at
  the read, whatever wrote the file.
- **Not on a network share.** SQLite refuses the authority in a share's URI,
  so a list there is created once, then refused.
- **Schema version 1**, held in `PRAGMA user_version`:

  ```sql
  CREATE TABLE tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL CHECK (length(trim(title)) > 0 AND length(title) <= 200),
    assignee   TEXT NOT NULL DEFAULT '' CHECK (length(assignee) <= 100),
    notes      TEXT NOT NULL DEFAULT '' CHECK (length(notes) <= 1000),
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  );
  ```

  The order of addition is `id`: `AUTOINCREMENT` never reuses an id. The
  `status` column exists before anything can close a task, so slice 4 adds
  behaviour, not a migration.
- **Field lengths are bounded** (`TITLE_MAX`, `ASSIGNEE_MAX`, `NOTES_MAX`).
  They are refused before a write and held by the schema. With
  `TASK_RESULTS_LIMIT`, they bound what one read hands the model.
- **Opening decides on the version.**
  - A missing file, or one with no table at version 0, is created at
    version 1. This happens in one transaction, which looks at the file again
    inside it.
  - A version-1 file is used as it is, once SQLite has recovered any
    interrupted write.
  - Anything else is refused,
  naming the file, and nothing is written: a newer version, a file with
  another schema, or a file that is not SQLite at all. A later version adds
  its own forward migration from 1, in the change that needs it.
- **The model never writes SQL.** The tools are fixed queries with bound
  parameters. Until slice 4, the only write is the owner's
  `starter tasks add`.

## Consequences

**Good:**

- No dependency.
- The file can be inspected with any SQLite tool.
- Every file ever written says which schema it holds.
- A file from a newer version is refused before anything reads from it or
  writes to it.

**Costly:**

- Migrations are hand-written SQL in the change that needs one.
- No ORM types: a row becomes a dictionary in one function.
- Search is `LIKE`, so letters outside ASCII match only in their exact case.

**Reversal:** moving to a library or a server database is a migration of every
owner's file. The version in each file is what such a migration starts from.

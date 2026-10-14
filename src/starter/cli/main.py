"""`starter`: the owner's command line. `starter tasks add` adds to the task list
the assistant reads -- the owner's own write, not a proposal the model makes."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Sequence

from starter.config.settings import settings_from_process, tasks_db_path
from starter.domain.tasks import TaskRefused, new_task
from starter.infrastructure.stores.tasks import TaskStore

# Exit statuses: 2 is a usage error, as argparse has it; 1 settings or a task
# list that cannot be read or written.
USAGE, UNREADABLE = 2, 1
# How the command line names each field the domain refuses.
ARGUMENT = {"title": "TITLE", "assignee": "--assignee", "notes": "--notes"}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        task = new_task(args.title, args.assignee, args.notes)
    except TaskRefused as refused:
        _say(f"{ARGUMENT[refused.field]}: {refused}")
        return USAGE
    try:
        path = tasks_db_path(settings_from_process())
    except ValueError as unreadable:  # the message names the .env
        _say(str(unreadable))
        return UNREADABLE
    try:
        store = TaskStore(path)
        store.open()
        print(store.add(task))
    except ValueError as refused:  # TASKS-SCHEMA's refusal names the file
        _say(str(refused))
        return UNREADABLE
    except (sqlite3.Error, OSError) as failed:
        _say(f"{path}: {failed}")
        return UNREADABLE
    return 0


def run() -> None:
    """The `starter` script: the one place a process exits."""
    sys.exit(main())


def _say(message: str) -> None:
    print(f"starter tasks add: {message}", file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="starter")
    commands = parser.add_subparsers(dest="noun", required=True)
    tasks = commands.add_parser("tasks", help="the task list the assistant reads")
    verbs = tasks.add_subparsers(dest="verb", required=True)
    add = verbs.add_parser("add", help="add an open task; prints its id")
    add.add_argument("title", metavar="TITLE")
    add.add_argument("--assignee", default="", metavar="NAME")
    add.add_argument("--notes", default="", metavar="TEXT")
    return parser

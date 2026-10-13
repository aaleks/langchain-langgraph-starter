"""`starter`: the owner's command line. `starter tasks add` adds to the task list
the assistant reads -- the owner's own write, not a proposal the model makes."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from starter.config.settings import settings_from_process, tasks_db_path
from starter.domain.tasks import new_task
from starter.infrastructure.stores.tasks import TaskStore

# Exit statuses: 2 is a usage error, as argparse has it; 1 a task list that
# cannot be opened.
USAGE, UNREADABLE = 2, 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        task = new_task(args.title, args.assignee, args.notes)
    except ValueError as refused:
        print(f"starter tasks add: {refused}", file=sys.stderr)
        return USAGE
    try:
        store = TaskStore(tasks_db_path(settings_from_process()))
        store.open()
    except ValueError as refused:
        print(f"starter tasks add: {refused}", file=sys.stderr)
        return UNREADABLE
    print(store.add(task))
    return 0


def run() -> None:
    """The `starter` script: the one place a process exits."""
    sys.exit(main())


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

"""The task list's writes, through `infrastructure/stores/tasks.py` -- a real SQLite
file in a temporary directory, never the owner's."""

from __future__ import annotations

import json
import sqlite3

import pytest

from starter.domain.tasks import (
    WriteOutcome,
    new_task,
    task_closing,
    task_creation,
    task_reassignment,
)
from starter.infrastructure.stores.tasks import TaskStore


@pytest.fixture
def store(tmp_path):
    """A list holding task 1, `Renew passport`, open, assigned to `sam`."""
    store = TaskStore(tmp_path / "tasks.sqlite3")
    store.open()
    store.add(new_task("Renew passport", "sam"))
    return store


def tasks(store: TaskStore) -> list[tuple]:
    db = sqlite3.connect(store.path)
    rows = db.execute("SELECT id, title, assignee, notes, status FROM tasks ORDER BY id").fetchall()
    db.close()
    return rows


def records(store: TaskStore) -> list[tuple]:
    db = sqlite3.connect(store.path)
    rows = db.execute(
        "SELECT write_key, action, arguments, decision, outcome, task_id, reason, recorded_at "
        "FROM task_writes ORDER BY id"
    ).fetchall()
    db.close()
    return rows


def close_directly(store: TaskStore, task_id: int) -> None:
    db = sqlite3.connect(store.path)
    db.execute("UPDATE tasks SET status = 'closed' WHERE id = ?", (task_id,))
    db.commit()
    db.close()


class TestTaskWrites:
    """TASKS-WRITES: The task list's writer SHALL apply a write in one transaction and
    return its outcome: a creation SHALL add an open task -- `applied`, with the new
    task's id; a closing SHALL set an open task closed, and a reassignment an open
    task's assignee -- `applied`, with the task's id. A closing or reassignment of a
    task that does not exist, or is closed, SHALL change nothing -- `refused`, with
    the reason `no task 7` or `task 7 is closed`. A writer SHALL write only to a
    list at schema version 2, as `open()` makes or migrates it: on a missing file it
    SHALL raise `sqlite3.OperationalError`, and on any other file -- a list at
    version 1 or 3 -- `ValueError` naming the file, creating and changing nothing."""

    @pytest.mark.parametrize(
        ("write", "task_id", "after"),
        [
            (
                task_creation("Call the plumber", "", "after 5pm"),
                2,
                [
                    (1, "Renew passport", "sam", "", "open"),
                    (2, "Call the plumber", "", "after 5pm", "open"),
                ],
            ),
            (task_closing(1), 1, [(1, "Renew passport", "sam", "", "closed")]),
            (task_reassignment(1, "ana"), 1, [(1, "Renew passport", "ana", "", "open")]),
            (task_reassignment(1, ""), 1, [(1, "Renew passport", "", "", "open")]),
        ],
        ids=["create", "close", "reassign", "unassign"],
    )
    def test_each_write_is_applied(self, store, write, task_id, after):
        outcome = store.writer().apply(write, "k1")

        assert outcome == WriteOutcome("applied", task_id, "")
        assert tasks(store) == after

    def test_a_closed_task_is_no_longer_listed(self, store):
        store.writer().apply(task_closing(1), "k1")

        assert store.reader(1.0).open_tasks(50) == {"tasks": [], "more": 0}

    @pytest.mark.parametrize(
        ("write", "closed", "reason"),
        [
            (task_closing(7), False, "no task 7"),
            (task_reassignment(7, "ana"), False, "no task 7"),
            (task_closing(1), True, "task 1 is closed"),
            (task_reassignment(1, "ana"), True, "task 1 is closed"),
        ],
        ids=["close-missing", "reassign-missing", "close-closed", "reassign-closed"],
    )
    def test_counter_example_refused_nothing_changed(self, store, write, closed, reason):
        if closed:
            close_directly(store, 1)
        before = tasks(store)

        outcome = store.writer().apply(write, "k1")

        assert outcome == WriteOutcome("refused", write.task_id, reason)
        assert tasks(store) == before

    def test_counter_example_a_writer_on_a_missing_file_creates_nothing(self, tmp_path):
        path = tmp_path / "tasks.sqlite3"

        with pytest.raises(sqlite3.OperationalError):
            TaskStore(path).writer().apply(task_closing(1), "k1")

        assert not path.exists()

    def test_counter_example_a_writer_on_a_list_not_migrated_changes_nothing(self, tmp_path):
        from tests.integration.infrastructure.test_task_store import version_1_list

        path = version_1_list(tmp_path / "tasks.sqlite3", "Renew passport")
        before = path.read_bytes()

        with pytest.raises(ValueError) as refused:
            TaskStore(path).writer().apply(task_closing(1), "k1")

        assert str(path) in str(refused.value)
        assert path.read_bytes() == before

    def test_counter_example_a_writer_on_a_newer_list_changes_nothing(self, store):
        db = sqlite3.connect(store.path)
        db.execute("PRAGMA user_version = 3")
        db.commit()
        db.close()
        before = store.path.read_bytes()

        with pytest.raises(ValueError) as refused:
            store.writer().apply(task_closing(1), "k1")

        assert str(store.path) in str(refused.value)
        assert store.path.read_bytes() == before


class TestWriteOnce:
    """TASKS-WRITE-ONCE: A write SHALL be applied at most once under its key:
    applying it, or rejecting it, under a key the task list already records SHALL
    change nothing and return the outcome recorded for that key. A key already
    recording a different write SHALL be refused with `ValueError`, nothing
    written. A key SHALL be 1 to `WRITE_KEY_MAX` (300) characters."""

    KEY = "t1:4:call_1"

    def test_a_creation_applied_twice_adds_one_task(self, tmp_path):
        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        write = task_creation("Renew passport", "", "")

        first = store.writer().apply(write, self.KEY)
        second = store.writer().apply(write, self.KEY)

        assert first == second == WriteOutcome("applied", 1, "")
        assert len(tasks(store)) == 1
        assert len(records(store)) == 1

    def test_a_closing_applied_twice_closes_once(self, store):
        first = store.writer().apply(task_closing(1), self.KEY)
        second = store.writer().apply(task_closing(1), self.KEY)

        assert first == second == WriteOutcome("applied", 1, "")
        assert len(records(store)) == 1

    def test_a_refusal_is_recorded_and_returned_again(self, store):
        store.writer().apply(task_closing(7), self.KEY)
        for title in ["two", "three", "four", "five", "six", "seven"]:
            store.add(new_task(title))

        again = store.writer().apply(task_closing(7), self.KEY)

        assert again == WriteOutcome("refused", 7, "no task 7")
        assert tasks(store)[6] == (7, "seven", "", "", "open")

    def test_a_rejection_then_an_approval_stays_rejected(self, tmp_path):
        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        write = task_creation("Renew passport", "", "")

        rejected = store.writer().reject(write, self.KEY)
        applied = store.writer().apply(write, self.KEY)

        assert rejected == applied == WriteOutcome("rejected", None, "")
        assert tasks(store) == []

    @pytest.mark.parametrize(
        ("first", "second", "outcome", "status"),
        [("apply", "reject", "applied", "closed"), ("reject", "reject", "rejected", "open")],
        ids=["applied-then-rejected", "rejected-twice"],
    )
    def test_a_rejection_under_a_recorded_key_returns_what_it_records(
        self, store, first, second, outcome, status
    ):
        getattr(store.writer(), first)(task_closing(1), self.KEY)

        again = getattr(store.writer(), second)(task_closing(1), self.KEY)

        assert again == WriteOutcome(outcome, 1, "")
        assert tasks(store)[0][4] == status
        assert len(records(store)) == 1

    @pytest.mark.parametrize("decide", ["apply", "reject"])
    def test_counter_example_a_key_reused_for_another_write_is_refused(self, store, decide):
        store.add(new_task("Call the plumber"))
        store.writer().apply(task_closing(1), self.KEY)
        before = (tasks(store), records(store))

        with pytest.raises(ValueError):
            getattr(store.writer(), decide)(task_closing(2), self.KEY)

        assert (tasks(store), records(store)) == before

    @pytest.mark.parametrize("key", ["", "k" * 301], ids=["empty", "301"])
    def test_counter_example_a_key_out_of_bounds_is_refused(self, store, key):
        before = (tasks(store), records(store))

        with pytest.raises(ValueError):
            store.writer().apply(task_closing(1), key)

        assert (tasks(store), records(store)) == before

    def test_counter_example_a_key_of_300_is_within_bounds(self, store):
        from starter.domain.tasks import WRITE_KEY_MAX

        outcome = store.writer().apply(task_closing(1), "k" * 300)

        assert WRITE_KEY_MAX == 300
        assert outcome == WriteOutcome("applied", 1, "")


class TestAudit:
    """TASKS-AUDIT: Every decision on a write SHALL be recorded in the table
    `task_writes`, in the same transaction as its effect: its key, its action --
    `create`, `close` or `reassign` -- its arguments as JSON, the decision --
    `approve` when applied, `reject` when rejected -- the outcome -- `applied`,
    `refused` or `rejected` -- the task's id when there is one, the reason, and when
    it was recorded. A write whose transaction fails SHALL leave neither its effect
    nor its record. The owner's own `starter tasks add` SHALL NOT be recorded: the
    record is of decisions on proposed writes."""

    def test_one_row_per_decision(self, store):
        store.writer().apply(task_creation("Call the plumber", "sam", ""), "k1")
        store.writer().apply(task_closing(7), "k2")
        store.writer().reject(task_reassignment(1, "ana"), "k3")

        rows = records(store)
        # The arguments as JSON objects, below: equal content, whatever the spacing.
        assert [(r[0], r[1], r[3], r[4], r[5], r[6]) for r in rows] == [
            ("k1", "create", "approve", "applied", 2, ""),
            ("k2", "close", "approve", "refused", 7, "no task 7"),
            ("k3", "reassign", "reject", "rejected", 1, ""),
        ]
        assert [json.loads(r[2]) for r in rows] == [
            {"title": "Call the plumber", "assignee": "sam", "notes": ""},
            {"task_id": 7},
            {"task_id": 1, "assignee": "ana"},
        ]
        assert all(r[7] for r in rows)
        assert tasks(store)[0] == (1, "Renew passport", "sam", "", "open")

    def test_counter_example_a_write_that_fails_leaves_nothing(self, tmp_path, monkeypatch):
        from starter.infrastructure.stores import tasks as stores

        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()

        def fails(db, *args, **kwargs):
            # The effect is in, and is what the failure must take back with it.
            assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
            raise sqlite3.OperationalError("failed before the record")

        monkeypatch.setattr(stores, "_record", fails)

        with pytest.raises(sqlite3.OperationalError):
            store.writer().apply(task_creation("Renew passport", "", ""), "k1")

        assert tasks(store) == []
        assert records(store) == []

    def test_counter_example_a_full_disk_propagates_its_own_error(self, tmp_path, monkeypatch):
        from starter.infrastructure.stores import tasks as stores

        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()
        # Records only, no task: the record's page all but full, the tasks' empty,
        # so the task is written and its record is what the disk cannot take.
        for n in range(3):
            store.writer().reject(task_creation(f"t{n}", "", "n" * 1000), f"k{n}")
        before = (tasks(store), records(store))
        real = stores._writing

        def full(path, timeout):
            db = real(path, timeout)
            db.execute(f"PRAGMA max_page_count = {db.execute('PRAGMA page_count').fetchone()[0]}")
            return db

        monkeypatch.setattr(stores, "_writing", full)

        # SQLite rolls this failure back itself; a second ROLLBACK would raise
        # "no transaction is active" in its place.
        written = []
        record = stores._record

        def recording(db, *args, **kwargs):
            written.append(db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            return record(db, *args, **kwargs)

        monkeypatch.setattr(stores, "_record", recording)

        with pytest.raises(sqlite3.OperationalError, match="database or disk is full"):
            store.writer().apply(task_creation("t3", "", "n" * 1000), "k3")

        assert written == [1]  # the task was in when its record failed

        assert (tasks(store), records(store)) == before

    def test_counter_example_the_owners_own_add_is_not_recorded(self, tmp_path):
        store = TaskStore(tmp_path / "tasks.sqlite3")
        store.open()

        store.add(new_task("Renew passport"))

        assert [row[:2] for row in tasks(store)] == [(1, "Renew passport")]
        assert records(store) == []

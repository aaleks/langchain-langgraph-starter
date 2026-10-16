"""What a checkpoint's version means to the code reading it -- a pure decision."""

from __future__ import annotations

import pytest

from starter.domain.agents.state_versions import checkpoint_version_refusal


class TestCheckpointVersion:
    """ASSISTANT-CHECKPOINT-VERSION: Every checkpoint the durable checkpointer writes SHALL
    carry the state's version in its metadata, `state_version`,
    `ASSISTANT_STATE_VERSION`: the version of the code that wrote it. A thread whose
    latest checkpoint carries a version newer than the code's SHALL be refused before
    any node runs -- `CheckpointVersionError`, naming both versions, nothing written to
    the task list or the checkpoint file and the model not called -- and its state
    cannot be read through the checkpointer either; its history is listed as stored. One
    that carries no version -- written before the stamp -- or an older one SHALL be
    loaded as it is, the state contract deciding the rest (ASSISTANT-STATE-CONTRACT). A
    thread's copy SHALL hold the source's checkpoints, their parents and pending writes
    -- a paused thread copied still asks the owner -- each checkpoint keeping its stamp
    and the copy's metadata its own thread id; a thread holding any checkpoint the code
    refuses SHALL not be copied, nothing written to the file. What a version found means
    is the domain's `checkpoint_version_refusal`."""

    @pytest.mark.parametrize(
        "found", [None, 1, 2], ids=["written-before-the-stamp", "older", "the-same"]
    )
    def test_loaded_as_it_is(self, found):
        assert checkpoint_version_refusal(found, current=2) is None

    @pytest.mark.parametrize(
        ("found", "because"),
        [
            (3, "3, newer than 2"),
            ("2", "not a version"),
            (True, "not a version"),
            (0, "not a version"),
        ],
        ids=["newer", "text", "a-boolean", "zero"],
    )
    def test_counter_example_refused(self, found, because):
        refusal = checkpoint_version_refusal(found, current=2)

        assert refusal is not None and because in refusal

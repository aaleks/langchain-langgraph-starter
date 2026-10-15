"""The registered assistant answered by the owner's Open WebUI -- a real model.

`live`: it needs Open WebUI running and configured in `.env`. It reads `.env`
alone -- the suite's environment sets the three settings empty on purpose, to
keep every other test offline -- and is skipped, saying so, when `.env` does not
configure Open WebUI. It asserts the shape of the answer, never its text.

The owner's key is an argument of the frames below this test, and pytest prints
a failing frame's arguments: so a failure here is reported by its message alone
-- a message SETTINGS-KEY-NEVER-SHOWN keeps free of the key. Measured: a refused
URL printed the key in the traceback before this.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import replace

import pytest
from langchain_core.messages import HumanMessage

from starter.config.settings import DOTENV, read_settings
from starter.domain.models import choose_model
from starter.infrastructure.models import OFFLINE_ANSWER


@contextmanager
def reported_by_message_only() -> Iterator[None]:
    try:
        yield
    except Exception as failure:  # a skip is not an Exception: it passes through
        pytest.fail(f"{type(failure).__name__}: {failure}", pytrace=False)


class TestAnsweredByOpenWebUI:
    """MODEL-OPENWEBUI-LIVE: With Open WebUI configured in `.env`, a run of the
    registered assistant SHALL be answered by that Open WebUI model: a transcript
    that begins with the human message and ends with a model answer calling no
    tool, every tool call on the way answered, nothing written to the task list,
    and an answer that is not empty and is not the offline model's."""

    @pytest.mark.live
    def test_a_real_answer_through_open_webui(self, tmp_path):
        from starter.infrastructure.agents.registry import registered_assistant

        with reported_by_message_only():
            settings = read_settings({}, DOTENV)
            if (
                choose_model(
                    settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model
                )
                != "openwebui"
            ):
                pytest.skip(f"{DOTENV} does not configure Open WebUI -- see .env.example")

            # The owner's model, never the owner's task list: a run creates one
            # where TASKS_DB points, so it points at a temporary one.
            tasks_db = tmp_path / "tasks.sqlite3"
            graph = registered_assistant(replace(settings, tasks_db=str(tasks_db)))
            messages = graph.invoke({"messages": [HumanMessage("Reply with one word.")]})[
                "messages"
            ]

            # The route between is the model's: it may read the list first.
            assert messages[0].type == "human" and messages[-1].type == "ai"
            assert messages[-1].tool_calls == []
            called = {c["id"] for m in messages if m.type == "ai" for c in m.tool_calls}
            assert called == {m.tool_call_id for m in messages if m.type == "tool"}
            with closing(sqlite3.connect(tasks_db)) as db:
                written = db.execute(
                    "SELECT (SELECT count(*) FROM tasks) + (SELECT count(*) FROM task_writes)"
                ).fetchone()
            assert written == (0,)
            assert isinstance(messages[-1].content, str) and messages[-1].content.strip()
            assert messages[-1].content != OFFLINE_ANSWER

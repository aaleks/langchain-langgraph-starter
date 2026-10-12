"""The registered assistant answered by the owner's Open WebUI -- a real model.

`live`: it needs Open WebUI running and configured in `.env`. It reads `.env`
alone -- the suite's environment sets the three settings empty on purpose, to
keep every other test offline -- and is skipped, saying so, when `.env` does not
configure Open WebUI. It asserts the shape of the answer, never its text.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from starter.config.settings import DOTENV, read_settings
from starter.domain.models import choose_model
from starter.infrastructure.models import OFFLINE_ANSWER


class TestAnsweredByOpenWebUI:
    """MODEL-OPENWEBUI-LIVE: With Open WebUI configured in `.env`, a run of the
    registered assistant SHALL be answered by that Open WebUI model: one model
    call, a transcript of `human, ai`, and an answer that is not empty and is
    not the offline model's."""

    @pytest.mark.live
    def test_a_real_answer_through_open_webui(self):
        from starter.infrastructure.agents.registry import registered_assistant

        settings = read_settings({}, DOTENV)
        if (
            choose_model(
                settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model
            )
            != "openwebui"
        ):
            pytest.skip(f"{DOTENV} does not configure Open WebUI -- see .env.example")

        graph = registered_assistant(settings)
        messages = graph.invoke({"messages": [HumanMessage("Reply with one word.")]})["messages"]

        assert [m.type for m in messages] == ["human", "ai"]
        assert messages[-1].tool_calls == []
        assert isinstance(messages[-1].content, str) and messages[-1].content.strip()
        assert messages[-1].content != OFFLINE_ANSWER

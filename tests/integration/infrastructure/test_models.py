"""The model the settings describe, built in `infrastructure/models.py` --
inspected, never called."""

from __future__ import annotations

import sys

from starter.config.settings import Settings
from starter.domain.agents.budgets import MODEL_CALL_DEADLINE_SECONDS
from starter.infrastructure.models import OFFLINE_ANSWER, build_model


class TestOpenWebUIClient:
    """MODEL-OPENWEBUI-CLIENT: The Open WebUI model SHALL be an OpenAI-compatible
    chat client addressed to `<OPENWEBUI_URL>/api` -- a trailing slash on the URL
    ignored -- with the configured key and model, a deadline of
    `MODEL_CALL_DEADLINE_SECONDS` per call, and no retries of its own: retrying
    is the assistant's policy, not the client's."""

    def test_the_client_the_settings_describe(self, no_network):
        settings = Settings(
            openwebui_url="http://localhost:3000/",
            openwebui_api_key="sk-local",
            openwebui_model="llama3.1:8b",
        )

        model = build_model(settings)

        assert type(model).__name__ == "ChatOpenAI"
        assert model.openai_api_base == "http://localhost:3000/api"
        assert model.openai_api_key.get_secret_value() == "sk-local"
        assert model.model_name == "llama3.1:8b"
        assert MODEL_CALL_DEADLINE_SECONDS == 120
        assert model.request_timeout == MODEL_CALL_DEADLINE_SECONDS
        assert model.max_retries == 0
        # Some model ids switch ChatOpenAI to /responses, which Open WebUI lacks.
        assert model.use_responses_api is False
        assert no_network == []

    def test_counter_example_nothing_configured_builds_the_offline_model(self, monkeypatch):
        # A provider the offline model must not need: importing it now fails.
        monkeypatch.setitem(sys.modules, "langchain_openai", None)

        model = build_model(Settings(openwebui_url="", openwebui_api_key="", openwebui_model=""))

        assert model.invoke("hello").content == OFFLINE_ANSWER

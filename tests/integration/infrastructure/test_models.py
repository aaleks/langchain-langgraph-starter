"""The model the settings describe, built in `infrastructure/models.py` --
inspected, never called."""

from __future__ import annotations

import importlib
import sys

import pytest

from starter.config.settings import Settings
from starter.domain.agents.budgets import MODEL_CALL_TIMEOUT_SECONDS
from starter.infrastructure.models import build_model


class TestOpenWebUIClient:
    """MODEL-OPENWEBUI-CLIENT: The Open WebUI model SHALL be an OpenAI-compatible
    chat-completions client addressed to `<OPENWEBUI_URL>/api` -- a trailing
    slash on the URL ignored, and a URL already ending in `/api` taken as the
    API itself -- with the configured key and model, a timeout of
    `MODEL_CALL_TIMEOUT_SECONDS` on every wait for the model, a streamed chunk
    included, and no retries of its own: retrying is the assistant's policy, not
    the client's."""

    def test_the_client_the_settings_describe(self, no_network, monkeypatch):
        # langchain-openai's own chunk timer, which defaults to 120 too: set
        # elsewhere, so only an explicit setting passes this test.
        monkeypatch.setenv("LANGCHAIN_OPENAI_STREAM_CHUNK_TIMEOUT_S", "7")
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
        assert MODEL_CALL_TIMEOUT_SECONDS == 120
        assert model.request_timeout == MODEL_CALL_TIMEOUT_SECONDS
        # The server streams: langchain-openai's own chunk timer would otherwise apply.
        assert model.stream_chunk_timeout == MODEL_CALL_TIMEOUT_SECONDS
        assert model.max_retries == 0
        # Some model ids switch ChatOpenAI to /responses, which Open WebUI lacks.
        assert model.use_responses_api is False
        assert no_network == []

    @pytest.mark.parametrize(
        ("url", "base"),
        [
            ("http://localhost:3000/", "http://localhost:3000/api"),
            ("http://localhost:3000/api", "http://localhost:3000/api"),
            ("http://localhost:3000/api/", "http://localhost:3000/api"),
            ("https://webui.lan/openwebui", "https://webui.lan/openwebui/api"),
        ],
    )
    def test_the_api_is_addressed_under_open_webuis_address(self, url, base):
        model = build_model(Settings(url, "sk-local", "llama3.1:8b"))

        assert model.openai_api_base == base

    def test_counter_example_nothing_configured_builds_the_offline_model(self, monkeypatch):
        # The models module imported afresh, with the provider and its SDK
        # impossible to import: a module-level import of either would fail here.
        monkeypatch.setitem(sys.modules, "langchain_openai", None)
        monkeypatch.setitem(sys.modules, "openai", None)
        monkeypatch.delitem(sys.modules, "starter.infrastructure.models")
        models = importlib.import_module("starter.infrastructure.models")

        model = models.build_model(Settings("", "", ""))

        assert model.invoke("hello").content == models.OFFLINE_ANSWER

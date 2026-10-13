from __future__ import annotations

import pytest

from starter.domain.models import choose_model


class TestModelChoice:
    """MODEL-CHOICE: The model SHALL be Open WebUI's when `OPENWEBUI_URL`,
    `OPENWEBUI_API_KEY` and `OPENWEBUI_MODEL` are all set, and the offline model
    when none is. When only some are set the choice SHALL be refused, naming
    each one missing -- never a silent fall back to the offline model -- and so
    SHALL a URL that is not Open WebUI's address -- `http` or `https`, a host, a
    port from 1 to 65535 if it names one, no user or password, no query or
    fragment, and no path beyond an `/api` segment -- the refusal naming
    `OPENWEBUI_URL`."""

    @pytest.mark.parametrize(
        ("url", "key", "model", "choice"),
        [
            ("http://localhost:3000", "sk-local", "llama3.1:8b", "openwebui"),
            ("https://webui.lan", "sk-local", "llama3.1:8b", "openwebui"),
            ("http://[::1]:3000", "sk-local", "llama3.1:8b", "openwebui"),
            ("https://webui.lan/openwebui", "sk-local", "llama3.1:8b", "openwebui"),
            ("http://localhost:3000/api", "sk-local", "llama3.1:8b", "openwebui"),
            ("http://localhost:3000/api/", "sk-local", "llama3.1:8b", "openwebui"),
            ("https://webui.lan/tools/openwebui", "sk-local", "llama3.1:8b", "openwebui"),
            ("http://api/openwebui", "sk-local", "llama3.1:8b", "openwebui"),
            ("http://localhost:1", "sk-local", "llama3.1:8b", "openwebui"),
            ("http://localhost:65535", "sk-local", "llama3.1:8b", "openwebui"),
            ("", "", "", "offline"),
        ],
    )
    def test_all_three_choose_open_webui_and_none_the_offline_model(self, url, key, model, choice):
        assert choose_model(url, key, model) == choice

    @pytest.mark.parametrize(
        ("url", "key", "model", "missing"),
        [
            ("http://localhost:3000", "", "", "OPENWEBUI_API_KEY, OPENWEBUI_MODEL"),
            ("http://localhost:3000", "", "llama3.1:8b", "OPENWEBUI_API_KEY"),
            # The URL is not what decides: without it, the rest is still refused.
            ("", "sk-local", "llama3.1:8b", "OPENWEBUI_URL"),
            ("", "", "llama3.1:8b", "OPENWEBUI_URL, OPENWEBUI_API_KEY"),
        ],
        ids=["url-only", "no-key", "no-url", "model-only"],
    )
    def test_counter_example_partly_configured_is_refused_naming_what_is_missing(
        self, url, key, model, missing
    ):
        with pytest.raises(ValueError) as refused:
            choose_model(url, key, model)

        assert str(refused.value).endswith(f"missing: {missing}")

    @pytest.mark.parametrize(
        "url",
        [
            "localhost:3000",
            "http//localhost:3000",
            "ftp://webui.lan",
            "http://:3000",
            "http://localhost:99999",
            "http://localhost:abc",
            "http://localhost:0",
            "http://localhost:",
            "http://[::1",
            "http://localhost:3000/?x=1",
            "http://localhost:3000/#top",
            "http://localhost:3000/api/chat/completions",
            "https://webui.lan/openwebui/api/chat/completions",
            "http://owner:secret@localhost:3000",
            "http://owner@localhost:3000",
            "https://webui.lan/api/openwebui",
        ],
    )
    def test_counter_example_a_url_that_is_not_http_with_a_host_is_refused(self, url):
        with pytest.raises(ValueError) as refused:
            choose_model(url, "sk-local", "llama3.1:8b")

        assert str(refused.value).startswith("OPENWEBUI_URL is not an http(s) URL")

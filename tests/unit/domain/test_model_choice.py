from __future__ import annotations

import pytest

from starter.domain.models import choose_model


class TestModelChoice:
    """MODEL-CHOICE: The model SHALL be Open WebUI's when `OPENWEBUI_URL`,
    `OPENWEBUI_API_KEY` and `OPENWEBUI_MODEL` are all set, and the offline model
    when none is. When only some are set the choice SHALL be refused, naming
    each one missing -- never a silent fall back to the offline model."""

    @pytest.mark.parametrize(
        ("url", "key", "model", "choice"),
        [
            ("http://localhost:3000", "sk-local", "llama3.1:8b", "openwebui"),
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
        ],
    )
    def test_counter_example_partly_configured_is_refused_naming_what_is_missing(
        self, url, key, model, missing
    ):
        with pytest.raises(ValueError) as refused:
            choose_model(url, key, model)

        assert str(refused.value).endswith(f"missing: {missing}")

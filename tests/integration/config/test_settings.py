"""Settings: the process environment first, `.env` for the rest -- read from a
`.env` in a temporary directory, never the owner's."""

from __future__ import annotations

import os

import pytest

from starter.config.settings import read_settings


def dotenv(tmp_path, text: str):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


class TestEnvironmentWins:
    """SETTINGS-ENVIRONMENT-WINS: A setting SHALL be read from the process
    environment when the environment holds it -- an empty value included -- and
    from `.env` only when the environment does not. A missing `.env` SHALL read
    as empty, and reading SHALL change neither the environment nor the file."""

    @pytest.mark.parametrize(
        ("environ", "expected"),
        [
            ({"OPENWEBUI_MODEL": "qwen3:8b"}, "qwen3:8b"),
            ({}, "llama3.1:8b"),
            ({"OPENWEBUI_MODEL": ""}, ""),
        ],
        ids=["environment-wins", "dotenv-fills", "empty-is-set"],
    )
    def test_the_environment_wins_and_dotenv_fills_only_what_it_lacks(
        self, tmp_path, environ, expected
    ):
        settings = read_settings(environ, dotenv(tmp_path, "OPENWEBUI_MODEL=llama3.1:8b\n"))

        assert settings.openwebui_model == expected

    def test_no_dotenv_reads_every_setting_as_empty(self, tmp_path):
        settings = read_settings({}, tmp_path / ".env")

        assert (settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model) == (
            "",
            "",
            "",
        )

    def test_counter_example_reading_leaves_the_environment_and_the_file_as_they_were(
        self, tmp_path
    ):
        environ: dict[str, str] = {}
        path = dotenv(tmp_path, "OPENWEBUI_URL=http://localhost:3000\n")
        process_before = os.environ.get("OPENWEBUI_URL")

        settings = read_settings(environ, path)

        assert settings.openwebui_url == "http://localhost:3000"
        assert environ == {}
        assert os.environ.get("OPENWEBUI_URL") == process_before
        assert path.read_text(encoding="utf-8") == "OPENWEBUI_URL=http://localhost:3000\n"

"""Settings: the process environment first, `.env` for the rest -- read from a
`.env` in a temporary directory, never the owner's."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from starter.config import settings as settings_module
from starter.config.settings import (
    Settings,
    read_settings,
    settings_from_process,
    tasks_db_path,
)
from starter.domain.models import choose_model

REPO = Path(__file__).resolve().parents[3]
# Every setting the specification names, spelled out: NAMES is what is tested.
SPECIFIED = ("OPENWEBUI_URL", "OPENWEBUI_API_KEY", "OPENWEBUI_MODEL", "TASKS_DB")
EVERY_SETTING = dict.fromkeys(SPECIFIED, "")


def dotenv(tmp_path, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding=encoding)
    return path


class TestEnvironmentWins:
    """SETTINGS-ENVIRONMENT-WINS: A setting SHALL be read from the process
    environment when the environment holds it -- an empty value included -- and
    from the repository's `.env` only when the environment does not, as written
    there: `${NAME}` is not expanded. Every value SHALL be read with the spaces
    around it removed, so a value of only spaces reads as empty. A missing `.env`
    SHALL read as empty, a
    `.env` that is not UTF-8 SHALL be refused naming the file, and reading SHALL
    change neither the environment nor the file -- nor open the file when the
    environment holds every setting."""

    @pytest.mark.parametrize(
        ("environ", "line", "expected"),
        [
            ({"OPENWEBUI_MODEL": "qwen3:8b"}, "OPENWEBUI_MODEL=llama3.1:8b", "qwen3:8b"),
            ({}, "OPENWEBUI_MODEL=llama3.1:8b", "llama3.1:8b"),
            ({"OPENWEBUI_MODEL": ""}, "OPENWEBUI_MODEL=llama3.1:8b", ""),
            ({"OPENWEBUI_MODEL": "   "}, "OPENWEBUI_MODEL=llama3.1:8b", ""),
            # Quoted: python-dotenv strips an unquoted value itself, a quoted one not.
            ({}, 'OPENWEBUI_MODEL="   "', ""),
        ],
        ids=[
            "environment-wins",
            "dotenv-fills",
            "empty-is-set",
            "spaces-in-the-environment-are-set-and-empty",
            "quoted-spaces-in-dotenv-are-empty",
        ],
    )
    def test_the_environment_wins_and_dotenv_fills_only_what_it_lacks(
        self, tmp_path, environ, line, expected
    ):
        settings = read_settings(environ, dotenv(tmp_path, line + "\n"))

        assert settings.openwebui_model == expected

    def test_a_dotenv_value_is_read_as_written_not_expanded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROBE", "leaked")

        settings = read_settings({}, dotenv(tmp_path, "OPENWEBUI_MODEL=${PROBE}\n"))

        assert settings.openwebui_model == "${PROBE}"

    @pytest.mark.parametrize("name", SPECIFIED)
    @pytest.mark.parametrize(
        ("given", "read"), [("   ", ""), ("  sk-local\t", "sk-local")], ids=["spaces", "padded"]
    )
    def test_every_setting_is_read_without_the_spaces_around_it(self, tmp_path, name, given, read):
        settings = read_settings({**EVERY_SETTING, name: given}, tmp_path / ".env")

        assert getattr(settings, name.lower()) == read

    def test_the_process_reads_its_environment_then_the_repositorys_dotenv(
        self, tmp_path, monkeypatch
    ):
        assert settings_module.DOTENV == REPO / ".env"
        monkeypatch.setattr(
            settings_module, "DOTENV", dotenv(tmp_path, "OPENWEBUI_URL=http://localhost:3000\n")
        )
        monkeypatch.delenv("OPENWEBUI_URL")
        monkeypatch.delenv("OPENWEBUI_API_KEY")
        monkeypatch.setenv("OPENWEBUI_MODEL", "qwen3:8b")

        settings = settings_from_process()

        assert (settings.openwebui_url, settings.openwebui_model) == (
            "http://localhost:3000",
            "qwen3:8b",
        )

    def test_no_dotenv_reads_every_setting_as_empty(self, tmp_path):
        settings = read_settings({}, tmp_path / ".env")

        assert (settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model) == (
            "",
            "",
            "",
        )

    def test_a_dotenv_that_is_not_utf8_is_refused_naming_the_file(self, tmp_path):
        path = dotenv(tmp_path, "OPENWEBUI_MODEL=llama3.1:8b\n", encoding="utf-16")

        with pytest.raises(ValueError) as refused:
            read_settings({}, path)

        assert str(path) in str(refused.value)

    def test_a_dotenv_is_not_opened_when_the_environment_holds_every_setting(self, tmp_path):
        path = dotenv(tmp_path, "OPENWEBUI_MODEL=llama3.1:8b\n", encoding="utf-16")

        settings = read_settings(EVERY_SETTING, path)

        assert settings.openwebui_model == ""

    def test_counter_example_reading_leaves_the_environment_and_the_file_as_they_were(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("OPENWEBUI_URL")
        path = dotenv(tmp_path, "OPENWEBUI_URL=http://localhost:3000\n")
        monkeypatch.setattr(settings_module, "DOTENV", path)

        # The process's own reading: os.environ itself, never a copy of it.
        settings = settings_from_process()

        assert settings.openwebui_url == "http://localhost:3000"
        assert "OPENWEBUI_URL" not in os.environ
        assert path.read_text(encoding="utf-8") == "OPENWEBUI_URL=http://localhost:3000\n"


class TestTasksDb:
    """SETTINGS-TASKS-DB: The task list's file SHALL be the setting `TASKS_DB` --
    a relative path taken from the repository's root, an absolute one as it is --
    and `.data/tasks.sqlite3` under the repository's root when the setting is
    empty."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("", REPO / ".data" / "tasks.sqlite3"),
            ("lists/home.sqlite3", REPO / "lists" / "home.sqlite3"),
        ],
        ids=["empty-is-the-default", "relative-from-the-repository"],
    )
    def test_where_the_task_list_is(self, tmp_path, value, expected):
        settings = read_settings({**EVERY_SETTING, "TASKS_DB": value}, tmp_path / ".env")

        assert tasks_db_path(settings) == expected

    def test_an_absolute_path_is_taken_as_it_is(self, tmp_path):
        absolute = tmp_path / "tasks.sqlite3"
        settings = read_settings({**EVERY_SETTING, "TASKS_DB": str(absolute)}, tmp_path / ".env")

        assert tasks_db_path(settings) == absolute

    def test_counter_example_the_working_directory_does_not_decide(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings = read_settings(
            {**EVERY_SETTING, "TASKS_DB": "lists/home.sqlite3"}, tmp_path / ".env"
        )

        assert tasks_db_path(settings) == REPO / "lists" / "home.sqlite3"


class TestKeyNeverShown:
    """SETTINGS-KEY-NEVER-SHOWN: The Open WebUI API key SHALL appear neither in a
    settings object's text nor in the message of a configuration refused."""

    def test_a_settings_object_printed_hides_the_key(self):
        settings = Settings("http://localhost:3000", "sk-secret-123", "llama3.1:8b", "")

        for text in (repr(settings), str(settings), f"{settings}"):
            assert "sk-secret-123" not in text
            assert "<set>" in text

    @pytest.mark.parametrize(
        ("url", "key", "model", "named"),
        [
            ("http://localhost:3000", "sk-secret-123", "", "OPENWEBUI_MODEL"),
            # Two lines swapped: the key is where the URL should be.
            ("sk-secret-123", "http://localhost:3000", "llama3.1:8b", "OPENWEBUI_URL"),
        ],
        ids=["partly-configured", "key-in-the-url-line"],
    )
    def test_a_configuration_refused_does_not_quote_the_key(self, url, key, model, named):
        with pytest.raises(ValueError) as refused:
            choose_model(url, key, model)

        assert named in str(refused.value)
        assert "sk-secret-123" not in str(refused.value)

    def test_counter_example_what_is_not_secret_is_shown(self):
        text = repr(Settings("http://localhost:3000", "sk-secret-123", "llama3.1:8b", ""))

        assert "http://localhost:3000" in text and "llama3.1:8b" in text

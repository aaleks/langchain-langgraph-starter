"""The two conventions imports cannot express: who reads the environment, and who exits."""

from __future__ import annotations

from .contract import (
    REPO,
    build_package,
    environment_reads_outside_config,
    exits_outside_cli,
    root_package,
)

SOURCE = REPO / "src" / root_package()


def test_only_config_reads_the_environment():
    assert environment_reads_outside_config(SOURCE) == []


def test_only_the_cli_exits():
    assert exits_outside_cli(SOURCE) == []


def test_every_way_of_reading_the_environment_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "envfix",
        {
            "domain/a.py": "import os\nx = os.environ['A']\n",
            "application/b.py": "import os\ny = os.getenv('B')\n",
            "infrastructure/c.py": "from os import getenv\n",
            "cli/d.py": "from dotenv import load_dotenv\n",
            "config/settings.py": "import os\nfrom dotenv import load_dotenv\nz = os.environ.get('Z')\n",
        },
    )
    found = environment_reads_outside_config(source)
    assert sorted(f.split(":")[0] for f in found) == ["a.py", "b.py", "c.py", "d.py"]


def test_every_way_of_exiting_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "exitfix",
        {
            "domain/a.py": "import sys\nsys.exit(1)\n",
            "application/b.py": "exit(2)\n",
            "infrastructure/c.py": "raise SystemExit(3)\n",
            "cli/main.py": "import sys\nsys.exit(0)\n",
        },
    )
    assert sorted(f.split(":")[0] for f in exits_outside_cli(source)) == ["a.py", "b.py", "c.py"]


def test_counter_example_raising_a_value_error_is_not_an_exit(tmp_path):
    source = build_package(
        tmp_path, "raisefix", {"domain/a.py": "raise ValueError('fix your input')\n"}
    )
    assert exits_outside_cli(source) == []

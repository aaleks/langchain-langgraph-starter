"""The two conventions imports cannot express: who reads the environment, and who exits."""

from __future__ import annotations

from .contract import (
    REPO,
    build_package,
    databases_opened_outside_stores,
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


def test_only_the_stores_open_a_database():
    assert databases_opened_outside_stores(SOURCE) == []


def test_every_way_of_opening_a_database_outside_the_stores_is_caught(tmp_path):
    source = build_package(
        tmp_path,
        "dbfix",
        {
            "domain/a.py": "import sqlite3\ndb = sqlite3.connect('x')\n",
            "infrastructure/agents/tools/b.py": "import sqlite3 as lite\ndb = lite.connect('x')\n",
            "cli/c.py": "from sqlite3 import connect as opened\ndb = opened('x')\n",
            # bound to another name before the call; a connection's own class;
            # the DB-API module, reached two ways
            "application/f.py": "import sqlite3\nopener = sqlite3.connect\ndb = opener('x')\n",
            "config/g.py": "import sqlite3\ndb = sqlite3.Connection('x')\n",
            "domain/h.py": "import sqlite3.dbapi2\ndb = sqlite3.dbapi2.connect('x')\n",
            "infrastructure/i.py": "from sqlite3 import dbapi2\ndb = dbapi2.connect('x')\n",
            # the C module; every name at once; the DB-API module's opener by name
            "application/j.py": "import _sqlite3\ndb = _sqlite3.connect('x')\n",
            "config/k.py": "from sqlite3 import *\ndb = connect('x')\n",
            "domain/l.py": "from sqlite3.dbapi2 import connect\ndb = connect('x')\n",
            "cli/m.py": "from sqlite3 import Connection as C\ndb = C('x')\n",
            # a connection subclassed, and bound to another name before the call
            "application/o.py": (
                "import sqlite3\nclass Mine(sqlite3.Connection):\n    pass\ndb = Mine('x')\n"
            ),
            "domain/p.py": "import sqlite3\nopen_ = sqlite3.Connection\ndb = open_('x')\n",
            # called inside an annotation, or inside isinstance: Python runs both
            "config/q.py": (
                "import sqlite3\ndef f() -> sqlite3.Connection('x'):\n    pass\n"
                "ok = isinstance(None, sqlite3.Connection('y'))\n"
            ),
            "infrastructure/stores/tasks.py": "import sqlite3\ndb = sqlite3.connect('x')\n",
            # counter-examples: the module imported for its errors; another connect
            "infrastructure/agents/tools/d.py": "import sqlite3\nerrors = (sqlite3.Error,)\n",
            "infrastructure/e.py": "import socket\ns = socket.socket()\ns.connect(('h', 1))\n",
            # a connection named in a type, and tested for: nothing opened
            "infrastructure/agents/tools/n.py": (
                "import sqlite3\nfrom sqlite3 import Connection\n"
                "def use(db: sqlite3.Connection, other: Connection) -> bool:\n"
                "    return isinstance(db, sqlite3.Connection)\n"
            ),
        },
    )
    found = databases_opened_outside_stores(source)
    assert sorted({f.split(":")[0] for f in found}) == [
        "application/f.py",
        "application/j.py",
        "application/o.py",
        "cli/c.py",
        "cli/m.py",
        "config/g.py",
        "config/k.py",
        "config/q.py",
        "domain/a.py",
        "domain/h.py",
        "domain/l.py",
        "domain/p.py",
        "infrastructure/agents/tools/b.py",
        "infrastructure/i.py",
    ], found

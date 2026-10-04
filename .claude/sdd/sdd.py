"""Entry point for the method's tooling. Run it through sdd.sh, which finds a Python.

Standard library only. Needs Python 3.11+ for tomllib -- and says so plainly
rather than failing on an import halfway through a hook.
"""

import sys
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036 -- runs on any machine Python, not the project's
    sys.exit(f"sdd needs Python 3.11 or later; this is {sys.version.split()[0]}")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sddlib.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

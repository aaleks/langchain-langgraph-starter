"""Entry points: argument parsing, output, exit codes.

The only layer that may call sys.exit. Everything below it raises, because a
library that kills the interpreter cannot be used from a test or a notebook.

Enforced by tests/architecture/test_conventions.py.
"""

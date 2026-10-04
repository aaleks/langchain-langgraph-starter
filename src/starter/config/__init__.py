"""Finding and loading configuration. The only reader of os.environ.

Reads the environment once, at the edge, and hands plain values inward. A
domain function never calls os.getenv; it receives the mapping as an argument.

Enforced by tests/architecture/test_conventions.py.
"""

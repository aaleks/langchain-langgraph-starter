"""Pure decisions: precedence, validation, eligibility, routing, budgets.

Imports the standard library and nothing else -- no SDK, no other layer, no
environment, no clock. A function here takes what it needs as arguments, so a
test hands it plain values and asserts the answer with ==.

Enforced by tests/architecture/test_imports.py (an allowlist, not a denylist).
"""

"""A LangChain / LangGraph starter, developed spec-first.

Five layers, dependencies pointing inward:

    cli  ->  infrastructure  ->  (application | config)  ->  domain

The contract is enforced by tests/architecture, not by this docstring. See
docs/architecture/overview.md for what each layer holds and may import.
"""

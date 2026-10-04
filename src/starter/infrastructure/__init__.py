"""Adapters: model builders, tracing, stores, and every LangGraph graph.

Wires domain decisions and application use cases to real services. Holds no
product decision of its own -- an `if` on a threshold belongs in the domain.
Graphs live in infrastructure/agents/, created by the first change that needs
one (docs/decisions/0003).

Raises ValueError for anything a caller can fix; never exits the process.
"""

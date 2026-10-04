"""Use cases, prompts and output contracts.

May import the standard library, langchain_core and pydantic -- the
abstractions every use case builds on -- and the domain. Never a runtime
(langchain, langgraph, deepagents) or a vendor SDK: a use case takes the model
as an argument, which is what lets a test pass a fake.

Enforced by tests/architecture/test_imports.py.
"""

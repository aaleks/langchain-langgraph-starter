"""Every LangGraph graph: compiled by `factory`, exported by `registry`.

The only package that imports a runtime (`langgraph`; `langchain`'s
`create_agent` too, were it used). A model or a tool arrives here as an object, built elsewhere --
so a test can hand in a fake. Rules: .claude/rules/langgraph/graphs.md.
"""

# 3. LangGraph is an adapter, adopted a rung at a time

Date: 2026-10-04
Status: Accepted

## Context

This starter exists to build LangGraph applications. The risk in a LangGraph
codebase is not too little graph but too much: every command turned into a
graph, product rules accumulating in nodes, Studio rendering treated as proof,
and in-memory checkpoints mistaken for durability. A graph used only to call a
model once makes testing and operations heavier and adds no control.

## Decision

- **The orchestration ladder.** One call in a use case; a `create_agent` tool
  loop with its middleware; a hand-written `StateGraph` -- the lowest rung that
  expresses the control flow a requirement needs. The frame records the rung
  and the requirement that needs it.
- **Placement.** `langgraph` and `deepagents` are imported only under
  `infrastructure/agents/` -- `create_agent` included, since it compiles a graph.
  Routing, approval, budget and retry policy are domain functions. Application
  imports no runtime. Enforced at package granularity, because that is all the
  import graph records; there are no submodule exceptions to make or get wrong.
- **Registration.** `langgraph.json` names only compiled graphs exported by
  `infrastructure/agents/registry.py`; graph ids are interfaces.
- **Durability claims need a durable checkpointer.** In-memory is for tests and
  `langgraph dev`.
- **Deep Agents only for work that needs planning, delegation and a virtual
  filesystem**, behind its own capability manifest, starting with no shell, no
  write-capable filesystem, no broad network.
- **Nothing is installed yet.** The dependencies, the registry and the first
  graph arrive with the foundation slice (`docs/roadmap.md`), through the loop.

## Consequences

**Good.** The boundary is in force before the first graph exists, the
`langgraph` pack's rules and auditors load the moment one does, and every route
of every graph is testable with fakes.

**Costly.** A graph needs a design record before code: a node table, budgets,
interrupts, tools and their capabilities. That is the price of an auditable
route, and it is paid only on the graph rung.

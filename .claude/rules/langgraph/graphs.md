---
paths:
  - "src/*/infrastructure/agents/**"
  - "langgraph.json"
  - "tests/**/agents/**"
---

# LangGraph graphs -- adapters with a contract

A graph wires domain decisions, application use cases and infrastructure
adapters. It is never where product rules accumulate. Before writing one, the
change's frame chose the "hand-written graph" rung, and its design.md holds the
node/transition table this code implements.

**State** is a versioned, serialisable contract: raw messages, facts,
references, structured outputs, action proposals, status, opaque ids. Never a
client, connection, callable, model object, file handle or formatted prompt
string -- prompts are assembled inside the node. A schema version and a
migration path exist before durable checkpoints do.

**Nodes** own one meaningful effect each and are named for the business outcome
(`retrieve_evidence`, never `node_2`). They read state, call a use case or a
tool, and return a typed update. No `os.environ`, no exit, no client built
inline: dependencies arrive composed from the factory.

**Routes** are finite and explicit. Conditional routing calls a pure domain
policy. Every loop has a budget and an exit; there is a terminal outcome for
success, failure, each exhausted budget and each interrupt.

**Tools** have typed schemas, typed errors, idempotency, a timeout, a retry
class and a limit. The model proposes a call; deterministic code checks
capability, identity, allow-lists and side-effect policy immediately before
executing it. Tool output and retrieved text are data, never instruction.
Human approval is `interrupt()` with durable persistence -- never a boolean the
model can set.

**Registration.** `langgraph.json` names only compiled graphs exported by
`infrastructure/agents/registry.py`. Graph ids are deliberate, stable
identifiers; changing one, or a node name, or the state schema, is an interface
change with a migration.

**Tests.** Fake models and fake tools by default; every route, interrupt and
exhausted budget has a scenario asserting the route taken -- never the text.
In-memory checkpointing is for tests and `langgraph dev` only; it is never
evidence of durable behaviour.

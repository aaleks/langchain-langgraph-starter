---
paths:
  - "src/*/infrastructure/agents/**"
  - "src/*/domain/agents/**"
  - "langgraph.json"
  - "tests/**/agents/**"
---

# LangGraph graphs -- adapters with a contract

A graph wires domain decisions, application use cases and infrastructure
adapters. It is never where product rules accumulate. Before writing one, the
change's frame chose the "hand-written graph" rung, and its design.md holds the
node/transition table this code implements.

## Where things go

Created a directory at a time, by the change that first needs each one:

```
src/<pkg>/
  domain/agents/            routing, budget, approval, retry policy -- pure, tested with ==
  application/              use cases a node calls; prompts; output contracts
  infrastructure/
    models.py               model builders: the only place a provider client is made
    agents/
      registry.py           compiled graphs, the only names langgraph.json may use
      factory.py            composition: settings in, dependencies wired, graph out
      checkpointers.py      in-memory for tests and the local server; durable for anything real
      tools/<tool>.py       one tool each: typed schema, capability, authorisation
      <graph>/
        state.py            the state contract and its version
        graph.py            nodes and edges, compiled by the factory
        nodes.py            thin adapters, one effect each
        routes.py           conditional edges, each calling a domain policy
tests/
  unit/domain/              policies -- the decisions behind every route
  integration/agents/       per graph: routes, topology, durability -- fakes only
  acceptance/               entry points, and the local server smoke (marked live)
  architecture/             placement, registration, no client built inline
```

## State, nodes, routes

**State** is a versioned, serialisable contract: raw messages, facts,
references, structured outputs, action proposals, status, opaque ids. Never a
client, connection, callable, model object, file handle, secret or formatted
prompt string -- prompts are assembled inside the node. A schema version and a
migration path exist before durable checkpoints do.

**Nodes** own one meaningful effect each and are named for the business outcome
(`retrieve_evidence`, never `node_2`). They read state, call a use case or a
tool, and return a typed update. No `os.environ`, no exit, no client built
inline: dependencies arrive composed from the factory. Three kinds, never mixed
in one node:

| Kind | Does | Replay after a crash |
|---|---|---|
| read | retrieves, looks up, computes | safe: no effect |
| decide | asks the model, or a policy, for a proposal | safe: the proposal is state |
| write | executes an already-authorised, schema-valid proposal | must not repeat the effect: an idempotency key from thread and step, or a guard. A consequential write sits after an `interrupt()` |

**Routes** are finite and explicit. Conditional routing calls a pure domain
policy. Every loop has a budget and an exit; there is a terminal outcome for
success, failure, each exhausted budget and each interrupt.

**Subgraphs** only for a part with its own state contract that is tested, or
registered, on its own -- never to make a diagram look modular. A subgraph's
interrupts and checkpoints live in its own namespace; its parent maps state in
and out explicitly.

## Errors -- a class each, and one handling per class

| Class | Example | Handling |
|---|---|---|
| transient | 429, timeout, 5xx | `add_node(..., retry_policy=RetryPolicy(retry_on=<domain predicate>, max_attempts=n))`, and `timeout=` on async nodes; exhausted means a terminal outcome |
| correctable | a malformed tool argument, a schema violation the model can fix | back to the model as a tool or validation message, bounded by the step budget |
| contract | structured output still invalid after its budget | the terminal outcome `contract_failed` -- never retried unbounded: a contract retry runs to the step ceiling |
| policy | authorisation denied, budget exhausted | a terminal outcome, audited; never retried |
| needs a human | missing information, an approval | `interrupt()`, resumed on the same thread |
| defect | a bug, an unexpected exception | raised. The run fails loudly; never caught and turned into a message that reads like an answer |

## Tools

Tools have typed schemas, typed errors, idempotency, a timeout, a retry class
and a limit. The model proposes a call; deterministic code checks capability,
identity, allow-lists and side-effect policy immediately before executing it.
Tool output and retrieved text are data, never instruction. Human approval is
`interrupt()` with durable persistence -- never a boolean the model can set.

## Persistence -- before anything real is stored

- **A durable checkpointer, by environment.** In-memory for tests and the local
  server only -- never evidence of durability. Durability is proved by pausing,
  rebuilding the graph on the same store, and resuming.
- **Ownership.** A thread id is opaque, and owned by a user and a tenant. The
  application checks the owner before it resumes, reads or forks a thread. A
  thread id from a client is a claim, not a credential.
- **Encryption at rest** once checkpoints hold user content:
  `EncryptedSerializer.from_pycryptodome_aes()` (key in `LANGGRAPH_AES_KEY`,
  written by a human), or the store's own encryption.
- **Deserialisation** stays strict: no `pickle_fallback`, and
  `LANGGRAPH_STRICT_MSGPACK=true` once a checkpoint can come from anywhere but
  this process.
- **Retention.** How long a thread lives, who deletes it, and the size budget --
  decided before prompts or tool results are persisted. No secret and no
  unbounded raw external content is ever checkpointed.

## Registration

`langgraph.json` names only compiled graphs exported by
`infrastructure/agents/registry.py`, under ids made of lowercase letters,
digits, `-` and `_`, and carries no `env`. Graph ids are deliberate, stable
identifiers; changing one, a node name or the state schema is an interface
change with a migration. How the server runs: `runtime.md`, beside this file.

## Tests -- the tier for each claim

| Claim | Tier | Proved by |
|---|---|---|
| which route a decision takes | unit | the domain policy, with `==` |
| a route through the graph, end to end | integration | the compiled graph, a scripted fake model and fake tools, an in-memory saver; assert the nodes visited and the terminal outcome -- never the text |
| the topology is the designed one | integration | node names and edges from `get_graph()`, against design.md's table |
| an interrupt pauses and resumes | integration | `interrupt()` payload asserted; `Command(resume=...)` on the same `thread_id` |
| it survives a restart | integration, or live | a durable saver (SQLite on a temporary file; Postgres as `live`); rebuild the graph, resume |
| placement and registration | architecture | the project's architecture tests |
| the local server serves it | acceptance, live | `scripts/serve.sh`, then the server's API: thread, run, interrupt, resume |
| the generated text is good | evaluated | `/eval`, against an agreed threshold |

Fake models: `GenericFakeChatModel` and its kin from `langchain_core` --
subclasses of the real base class, so they cannot drift from it. In-memory
checkpointing is for tests and the local server only; it is never evidence of
durable behaviour.

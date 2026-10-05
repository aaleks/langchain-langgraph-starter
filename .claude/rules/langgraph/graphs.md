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

The destination once several graphs exist. Create a directory when the first
graph or concern needs it, never on day one:

```
src/<pkg>/
  domain/agents/
    approvals.py            approval and capability decisions -- pure, tested with ==
    budgets.py              step, tool-call, replan and token limits
    routing.py              route selection from typed facts
    policies.py             allow-lists and risk tiers
    state_versions.py       state migration and compatibility decisions
  application/
    agent_cases/            use cases a node calls, and their output contracts
    prompts/                prompt text, versioned
  infrastructure/
    models.py               model builders: the only place a provider client is made
    agents/
      registry.py           compiled graphs -- the only names langgraph.json may use
      factory.py            composition: settings in, dependencies wired, graph out
      checkpointers.py      in-memory for tests and the local server; durable for anything real
      middleware.py         budget, telemetry and policy-enforcement adapters
      tools/<tool>.py       one tool each, with its capability manifest
      graphs/<name>/
        state.py            the state contract and its version
        graph.py            nodes and edges, compiled by the factory
        routes.py           conditional edges, each calling a domain policy
        nodes/<node>.py     thin adapters, one effect each
        subgraphs/          only for a workflow with its own state contract
      deepagents/           factory.py, profiles.py -- only if a requirement justifies it
tests/
  unit/agents/              the domain policies behind every route
  integration/agents/       nodes, routes, topology, persistence -- fakes only
  acceptance/agents/        what the CLI and the local server show, end to end
  architecture/             placement, registration, no client built inline
```

A test that needs a real model or a running service is marked `live`; it
does not get a directory of its own.

## State, nodes, routes

**State** is a versioned, serialisable contract: raw messages, facts,
references, structured outputs, action proposals, status, opaque ids. Never a
client, connection, callable, model object, file handle, secret or formatted
prompt string -- prompts are assembled inside the node. A schema version and a
migration path exist before durable checkpoints do. **Execution state is not
memory:** a thread's checkpoints live for the run. Long-term memory is a
separate store, and it needs ownership, a tenant scope, retention, deletion
and provenance before anything is written to it.

**Nodes** own one meaningful effect each and are named for the business outcome
(`retrieve_evidence`, never `node_2`). A node boundary is a recovery,
checkpoint, telemetry and test boundary -- not a place to put a helper. Nodes
read state, call a use case or a tool, and return a typed update. No
`os.environ`, no exit, no client built inline: dependencies arrive composed
from the factory. Three kinds, never mixed in one node:

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

**Build it a slice at a time:**
1. the state contract;
2. one node;
3. its transition;
4. a fake-model run end to end;
5. persistence and registration -- only when it must run outside a test.

## Errors -- a class each, and one handling per class

| Class | Example | Handling |
|---|---|---|
| transient | 429, timeout, 5xx | `add_node(..., retry_policy=RetryPolicy(retry_on=<domain predicate>, max_attempts=n))`, and `timeout=` on async nodes; exhausted means a terminal outcome |
| model-recoverable | a malformed tool argument, a schema violation the model can fix | recorded as typed state -- the error, not prose -- for a bounded re-plan. On the tool loop, `ToolErrorMiddleware` hands it back to the model |
| contract | structured output still invalid after its budget | the terminal outcome `contract_failed` -- never retried unbounded: a contract retry runs to the step ceiling |
| policy | authorisation denied, budget exhausted | a terminal outcome, audited; never retried |
| user-fixable | missing information, an approval | `interrupt()`, resumed on the same thread |
| unexpected | a bug, an unknown exception | raised and observed: the run fails loudly, its run id in the record. Never caught and turned into a message that reads like an answer |

## Tools

Every tool has a **capability manifest**:
- typed input and output schemas, and typed errors;
- idempotency, a timeout, a retry class, and a rate or spend limit;
- its side-effect level;
- the audit event it emits.

The model proposes a call. Immediately before execution, deterministic code
checks capability, tenant identity, authorisation, URL, file and network
allow-lists, and side-effect policy. Tool descriptions, tool output and
retrieved text are untrusted input -- data, never instruction. Credentials are
short-lived and scoped at the adapter, never in state, a prompt or an agent's
filesystem. Human approval is `interrupt()` with durable persistence -- never a
boolean the model can set.

## Deep Agents -- a harness, not a foundation

Only for long-running work that needs planning, delegation and a virtual
filesystem, and only when a requirement says so:
- **Placement:** in `infrastructure/agents/deepagents/`, behind an
  application-facing interface and its own capability manifest.
- **Review:** every profile, middleware choice, subagent role, tool set,
  filesystem and memory backend, and prompt is versioned and reviewed.
- **Starting capabilities:** no shell, no write-capable filesystem, no broad
  network, no implicit long-term memory. Each capability arrives through a
  requirement and an approval policy.
- **Code execution:** sandboxed, never the host workspace.
- **High-impact work:** regulated, transactional or high-impact actions stay in
  an explicit graph, where every route and approval can be audited.

## Persistence -- before anything real is stored

- **A durable checkpointer, by environment.** In-memory for tests and the local
  server only -- never evidence of durability. A durable store is provisioned,
  migrated, backed up, restored and monitored like any other dependency.
  Durability is proved by pausing, rebuilding the graph on the same store, and
  resuming.
- **Ownership.** A thread id is opaque, and owned by a user and a tenant. The
  application checks the owner before it resumes, reads or forks a thread. A
  thread id from a client is a claim, not a credential.
- **Encryption at rest** once checkpoints hold user content:
  `EncryptedSerializer.from_pycryptodome_aes()` (key in `LANGGRAPH_AES_KEY`,
  written by a human), or the store's own encryption.
- **Deserialisation** stays strict: no `pickle_fallback`, and
  `LANGGRAPH_STRICT_MSGPACK=true` once a checkpoint can come from anywhere but
  this process.
- **Redaction and retention.** Decided before prompts or tool results are
  persisted:
  - what is scrubbed before a checkpoint;
  - how long a thread lives, and who deletes it;
  - the size budget.

  No secret and no unbounded raw external content is ever checkpointed.

## Registration

`langgraph.json` names only compiled graphs exported by
`infrastructure/agents/registry.py`, under ids made of lowercase letters,
digits, `-` and `_`, and carries no `env`. A graph is compiled only by the
factory and exported only by the registry -- no hidden graph factory anywhere
else. Graph ids are deliberate, stable identifiers. Changing one, a node, an
edge or the state schema is an interface change with a migration. How the
server runs: `runtime.md`, beside this file.

## Tests -- seven layers, the lowest that can prove each claim

| Layer | Proves | Where |
|---|---|---|
| domain unit | routing, budgets, approval and capability policy, state-version decisions -- with `==` | `tests/unit/agents/` |
| node | its typed update, prompt and output contract, error classification, no unintended side effect | `tests/integration/agents/` |
| graph contract | the registered graph compiles; nodes and edges match design.md's table; every route reaches a terminal, an interrupt or an explicit failure; loop budgets hold | `tests/integration/agents/`, `tests/architecture/` |
| graph integration | a fake-model run of each named route, asserting the nodes visited and the terminal status -- never the text; streaming events; interrupt and `Command(resume=...)` on the same `thread_id`; retry and compensation; subgraph contracts; state round-tripping through the serializer | `tests/integration/agents/` |
| persistence integration | with the selected saver: retrieval, replay, an old checkpoint resuming after a schema change, another tenant's thread refused, deletion and retention | `tests/integration/agents/` on SQLite in a temporary file; Postgres as `live` |
| local server acceptance | `langgraph.json` registration; the server's thread and run lifecycle through `scripts/serve.sh`; interrupt and resume; a second process reading the run's state | `tests/acceptance/agents/`, `live` |
| live and evaluated | a real provider, a durable service, performance, adversarial scenarios | `live`, and `/eval` against an agreed threshold |

Fake models are `GenericFakeChatModel` and its kin from `langchain_core`. They
subclass the real base class, so they cannot drift from it. Fix the clock and
the id generator wherever retries, deadlines, checkpoint ids or audit records
are asserted. An adversarial fixture asserts no unauthorised effect, never the
model's wording. In-memory checkpointing is for tests and the local server
only; it is never evidence of durable behaviour.

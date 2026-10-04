# Architecture

```
cli  ->  infrastructure  ->  (application | config)  ->  domain
```

| Layer | Holds | May import | Enforced by |
|---|---|---|---|
| `domain/` | pure decisions: precedence, validation, routing, budgets, approval and retry policy | the standard library | `tests/architecture/test_imports.py` (allowlist) |
| `config/` | locating and loading configuration; the only reader of `os.environ` | `domain` | `test_layers.py`, `test_conventions.py` |
| `application/` | use cases, prompts, output contracts | `domain`, `langchain_core`, `pydantic` | `test_imports.py` (allowlist), `test_layers.py` |
| `infrastructure/` | adapters: model builders, stores, tracing; graphs in `agents/` | `domain`, `config`, `application` | `test_layers.py`; `langgraph` only in `agents/` by `test_imports.py` |
| `cli/` | arguments, output, exit codes; the only `sys.exit` | everything | `test_conventions.py` |

Every rule above is also run against a fixture package built to break it, and
must fail there. A check that passes while checking nothing is believed, which
is worse than having no check.

## Where a decision goes

The question is never "which layer is closest to where I am typing". It is
"could `assert result == expected` prove this with plain values?" If yes, it is
a domain function, and the adapter calls it. The most common decay in an LLM
codebase is a threshold, a precedence choice or a retry count written inline in
an adapter, where no unit test can reach it -- `architecture-guardian` looks
for exactly that.

## When graphs arrive

The intended shape once several graphs exist -- created a directory at a time,
by the change that first needs each one, never on day one:

```
src/starter/
  domain/agents/          routing, budgets, approvals, policies: pure, tested with ==
  application/            use cases a node calls; output contracts; prompts
  infrastructure/agents/
    registry.py           the only import surface langgraph.json may name
    factory.py            dependency composition -- no process exit
    checkpointers.py      in-memory for tests and dev; a durable store for anything real
    tools/                each with typed schemas, a capability, an authorisation check
    graphs/<name>/        state.py, graph.py, routes.py, nodes/ -- thin adapters
```

Nodes read serialisable state, call a use case or a tool, and return a typed
update. Conditional routes call a domain policy. See
`docs/decisions/0003-langgraph-is-an-adapter.md` and
`.claude/rules/langgraph/graphs.md`.

# Architecture

```
cli  ->  infrastructure  ->  (application | config)  ->  domain
```

| Layer | Holds | May import | Enforced by |
|---|---|---|---|
| `domain/` | pure decisions: precedence, validation, routing, budgets, approval and retry policy | the standard library | `tests/architecture/test_imports.py` (allowlist) |
| `config/` | locating and loading configuration; the only reader of `os.environ` and `.env` | `domain`, `dotenv` | `test_imports.py` (allowlist), `test_layers.py`, `test_conventions.py` |
| `application/` | use cases, prompts, output contracts | `domain`, `langchain_core`, `pydantic` | `test_imports.py` (allowlist), `test_layers.py` |
| `infrastructure/` | adapters: model builders, stores, tracing; graphs in `agents/` | `domain`, `config`, `application` | `test_layers.py`; `langgraph` only in `agents/` by `test_imports.py`; a database opened (`sqlite3.connect`) only in `stores/` by `test_conventions.py` |
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
  domain/agents/          approvals, budgets, routing, policies, state versions: pure, tested with ==
  application/            agent_cases/ (use cases a node calls, output contracts), prompts/
  infrastructure/
    models.py             model builders: the only place a provider client is made
    agents/
      registry.py         the only names langgraph.json may use
      factory.py          composition: settings in, dependencies wired, graph out
      checkpointers.py    in-memory for tests and the local server; durable for anything real
      middleware.py       budget, telemetry and policy-enforcement adapters, for a create_agent loop
      tools/              one per module, each with its capability manifest
      graphs/<name>/      state.py, graph.py, routes.py, nodes/, subgraphs/ -- thin adapters
      deepagents/         only if a requirement justifies a harness
```

The full tree, and the test layout that mirrors it, is in
`.claude/rules/langgraph/graphs.md`.

Nodes read serialisable state, call a use case or a tool, and return a typed
update. Conditional routes call a domain policy. The graphs run on this machine
only: `scripts/serve.sh` starts the development server on 127.0.0.1, from an
environment in which nothing reaches LangSmith. See
`docs/decisions/0003-langgraph-is-an-adapter.md`,
`docs/decisions/0004-langgraph-runs-locally.md` and
`.claude/rules/langgraph/graphs.md`.

| Rule | Enforced by |
|---|---|
| `langgraph.json` names only registry exports, under stable ids, with no `env` | `tests/architecture/test_graphs.py` |
| the agents adapter imports no provider SDK or client | `tests/architecture/test_graphs.py` (allowlist) |
| no model built inline in the agents adapter | `tests/architecture/test_graphs.py` |
| a model -- a chat or completion model, embeddings, a provider SDK's client -- built only in `infrastructure/models.py`. Caught by the names a model goes by, not every way of reaching one: a class passed to `partial`, bound to another name by assignment, built by a classmethod (`ChatOpenAI.model_validate`), or named like no model (`langchain_community`'s `Ollama`) is not seen | `tests/architecture/test_graphs.py` |
| the server starts only through `scripts/serve.sh`; nothing reaches LangSmith | `.claude/settings.json` (deny rules and env), `scripts/serve.sh` |

Each `test_graphs.py` check runs on the registered graph, and each is proved,
on fixtures, to fail when it should.

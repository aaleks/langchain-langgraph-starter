# The langgraph pack

For projects that orchestrate models with LangGraph -- installed with
`--packs langgraph`. Inert until the first graph exists: the rules are scoped to
graph paths, and each auditor says "nothing to audit" until there is. Two
things act from the first day: the agent's settings, and the server wrapper.

| File | Does |
|---|---|
| `skills/discover/references/orchestration-ladder.md` | the frame's **orchestration rung**: one call, a `create_agent` tool loop, or a hand-written `StateGraph` -- the lowest that expresses the control flow a requirement needs; Deep Agents' place; retries as three problems; the tool loop's budgets and their traps (langchain 1.4.3 defaults); the **routes every requirement set names**; the build order; reviewing output before it returns |
| `skills/accept/references/graph-routes.md` | what a test of a graph's route asserts -- nodes visited, terminal status, interrupt and resume on the same thread, an exhausted budget -- with a scripted fake model |
| `rules/langgraph/graphs.md` | loads on graph code, graph tests and `langgraph.json`: the destination tree; state as a versioned contract, apart from long-term memory; read / decide / write nodes; finite routes with budgets; error classes; subgraphs; a vertical slice at a time; tools with capability manifests, authorised at the boundary; Deep Agents as a harness; persistence (ownership, encryption, redaction, retention); the seven test layers |
| `rules/langgraph/runtime.md` | loads on `langgraph.json`, `scripts/serve.sh`, the registry and acceptance tests: the local server, what replaces Studio, and how to re-measure that nothing leaves the machine |
| `sdd/seeds/serve.sh` -> `scripts/serve.sh` | **seeded**: the one way to start the development server -- 127.0.0.1, no browser, an allowlist of flags, the local-only environment |
| `sdd/seeds/settings.langgraph.json` | **merged into the seeded settings**: the same local-only environment for every command the agent runs, and deny rules for every command that would reach LangSmith or expose the server |
| `agents/graph-architecture-guardian.md` | placement, topology, registration, the runtime configuration |
| `agents/durability-auditor.md` | checkpoints, state versions, interrupts and resume, idempotency, ownership, encryption, retention |
| `agents/agent-capability-auditor.md` | tool manifests, least privilege, authorisation, budgets, Deep Agents profiles |
| `agents/graph-eval-auditor.md` | every route proved with fakes, adversarial fixtures, evaluator validity |

`/verify` adds each auditor whose subject the diff touches -- graphs, tools,
durable state, routes; `/quality --graphs` runs all four. The core edit guard
carries two of the pack's rules: it refuses an agent's write to the server's
local state or a data store, and new text that gives `langgraph.json` an `env`
key.

## Local only, by default

LangGraph's own tooling reaches LangSmith unless told not to, in ways tracing
switches alone do not stop: hosted Studio is LangSmith's web app, `langgraph up`
needs a LangSmith key, and the development server reports usage to
`api.smith.langchain.com` whenever a key is in its environment. Measured with
`langgraph-cli 0.4.32` and `langgraph-api 0.15.1`. This pack's default is
therefore local-only:

- the server runs only through `scripts/serve.sh`;
- the agent works in the same environment;
- the agent is denied `smith.langchain.com`, `--studio-url`, `--tunnel`,
  `langgraph deploy`, `langgraph up`, and every way of starting the server but
  the wrapper.

A project that wants LangSmith edits its own settings and wrapper -- both
project-owned once seeded -- and records why in an ADR.

**Installing into a project that already has `.claude/settings.json`**: install
leaves it alone and reports `seeds/settings.langgraph.json`. Merge its `env`
and `deny` entries by hand. **Updating from 0.2.0**: `update` writes no seed;
run `install` again with the same packs to seed `scripts/serve.sh`.

## What the pack assumes

**Graphs are adapters, not the domain.** LangGraph lives in
`infrastructure/agents/`; routing, approval, budget and retry *policy* are pure
functions in the domain; the application layer never imports a runtime --
including `create_agent`, which compiles a graph. With the python pack's
architecture tests, `langgraph` imported anywhere outside
`infrastructure/agents/` fails the build, at package granularity, with no
submodule exceptions. A project built from the starter also has checks that
`langgraph.json` names only registry exports and carries no `env`, that the
agents adapter imports no provider SDK, and that no model is built inline there
(`tests/architecture/test_graphs.py`).

# The langgraph pack

For projects that orchestrate models with LangGraph -- installed with
`--packs langgraph`. Inert until the first graph exists: the rules are scoped to
graph paths, and each auditor says "nothing to audit" until there is.

| File | Does |
|---|---|
| `skills/discover/references/orchestration-ladder.md` | the frame's **orchestration rung**: one call, a `create_agent` tool loop, or a hand-written `StateGraph` -- the lowest that expresses the control flow a requirement needs; retries as three problems; reviewing output before it returns |
| `rules/langgraph/graphs.md` | loads on `src/*/infrastructure/agents/**`, `langgraph.json` and graph tests: state as a versioned contract, thin nodes, finite routes with budgets, tools authorised at the boundary, registration through one registry |
| `agents/graph-architecture-guardian.md` | placement, topology, registration |
| `agents/durability-auditor.md` | checkpoints, state versions, interrupts and resume, idempotency, retention |
| `agents/agent-capability-auditor.md` | tool manifests, least privilege, authorisation, budgets, Deep Agents profiles |
| `agents/graph-eval-auditor.md` | every route proved with fakes, adversarial fixtures, evaluator validity |

`/verify` adds the first and third auditors when a diff touches graphs or tools;
`/quality --graphs` runs all four.

**The architectural rule the pack assumes:** graphs are adapters, not the domain.
LangGraph lives in `infrastructure/agents/`; routing, approval, budget and retry
*policy* are pure functions in the domain; the application layer never imports a
runtime -- including `create_agent`, which compiles a graph. With the python
pack's architecture tests, `langgraph` imported anywhere outside
`infrastructure/agents/` fails the build, at package granularity, with no
submodule exceptions.

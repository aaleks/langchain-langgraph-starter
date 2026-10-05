# 4. LangGraph runs locally, never through LangSmith

Date: 2026-10-05
Status: Accepted

## Context

The owner's constraint: LangGraph is used locally only, never through
smith.langchain.com. LangGraph's own tooling assumes the opposite, and in
ways that are not visible. Measured with `langgraph-cli 0.4.32` and
`langgraph-api 0.15.1`; the evidence is in the change
`langgraph-local-runtime` (`frame.md`):

- **Studio is LangSmith's web app.** `langgraph dev` opens
  `https://smith.langchain.com/studio/?baseUrl=<your local server>`.
  `--studio-url` only swaps in another origin -- a self-hosted LangSmith.
- **`langgraph up` needs LangSmith.** It requires a `LANGSMITH_API_KEY` with
  LangSmith Deployment access, or an enterprise licence key.
- **`langgraph dev` is not local by default.** It posts CLI analytics, asks
  pypi.org for the latest version, and -- with any LangSmith key in its
  environment -- sends usage metadata to `api.smith.langchain.com` every five
  minutes, **even with `LANGSMITH_TRACING=false`**.
- **An empty key does not stop tracing.** With tracing on and no key at all,
  `langsmith` still POSTs each run's inputs and outputs to
  `api.smith.langchain.com`.

## Decision

- **LangSmith is not used**: no hosted Studio, no tracing, no LangSmith
  Deployment, no `langgraph up`.
- **The development server is started only by `scripts/serve.sh`.** It binds
  127.0.0.1, never opens a browser, refuses `--host`, `--tunnel` and
  `--studio-url`, and starts the server from the **local-only environment**:
  - tracing off, through all four switches;
  - every LangSmith credential empty;
  - the LangSmith endpoint pointed at a closed local port;
  - the CLI's analytics and version check off.

  It refuses a `langgraph.json` `env` key, which the server would load over that
  environment, and a `.env` that sets a LangSmith credential or switches
  tracing on.
- **The agent works inside the same environment** (`.claude/settings.json`
  `env`). It is denied commands containing `smith.langchain.com`,
  `--studio-url`, `--tunnel`, `langgraph deploy` or `langgraph up`, and any
  `langgraph dev` other than through the wrapper.
- **Studio's jobs move to local tools.**
  - The topology: `get_graph().draw_mermaid()` and the local server's
    `/assistants/{id}/graph`. Not `draw_mermaid_png()`, whose default posts the
    graph to mermaid.ink.
  - Runs, streams, interrupts and resume: the local server's API.
  - Proof: fake-model route tests, as before.
- **Durability is proved without `langgraph up`**: a durable checkpointer
  composed in the project, paused and resumed across a rebuilt graph.
- **Every entry point the project ships** starts from the local-only
  environment -- a requirement for the foundation slice.
- **Re-measure at every upgrade** of `langgraph-cli` or `langgraph-api`. The
  version-check switch is undocumented, and its source calls it dev-only.
  The probe is in `.claude/rules/langgraph/runtime.md`.

## Consequences

**Good.** A development server, a test run and an agent session make no
connection to LangSmith -- measured, not assumed: zero outbound `connect()`
calls with the environment above, even when the parent shell exports a
LangSmith key. Nothing about a graph, a prompt or a user's data leaves the
machine through LangGraph's tooling.

**Costly.**

- No visual debugger. Topology comes as Mermaid text, runs through an API.
- No managed server: anything served beyond development is the project's own
  work -- a later slice, through build-or-adopt.
- The deny rules are a guard against habit, not a boundary. A shell started
  another way, or a person, can still reach LangSmith. Where that matters, the
  boundary is the network: an egress rule that denies `*.langchain.com`.

**Reversing it** means editing two project-owned files --
`.claude/settings.json` and `scripts/serve.sh` -- and superseding this ADR.
The graphs themselves need no change: nothing in `src/` depends on where the
server runs.

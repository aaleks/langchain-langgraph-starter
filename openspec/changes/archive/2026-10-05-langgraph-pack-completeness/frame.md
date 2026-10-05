# Frame

## Outcome

Someone starting a graph from this starter finds every requirement of the
source plan in the place they will read it:
- the rules loaded on graph code;
- the references `/discover` and `/accept` read;
- the stage templates;
- the auditors' checklists;
- for the cheap, reliable cases, a guard that refuses.

The observable signals:

- Each line of the gap trace below points at the file, and the place in it,
  that now holds the source's requirement -- or at the roadmap slice that
  owns it, and why.
- An agent's write that adds `env` to `langgraph.json`, or edits the
  server's local state or a checkpoint store, is refused at write time. Each
  refusal is proved by a test that was red first.

## Existing options considered

None to build: this change amends the method's own rules. One adopt decision
sits inside it. For budgets and failure handling on the tool-loop rung, the
ladder names LangChain's maintained middleware rather than inviting
hand-written loops. Checked against `langchain 1.4.3`:

| Option | Covers | Its default, and why that matters |
|---|---|---|
| `ModelCallLimitMiddleware(run_limit=, exit_behavior=)` | a step budget on model calls | **no limit** unless set. On exhaustion `"end"` injects an AI message saying so, which reads like an answer; `"error"` raises `ModelCallLimitExceededError` |
| `ToolCallLimitMiddleware(run_limit=, exit_behavior=)` | a tool-call budget | **no limit** unless set. `"continue"` lets the model decide when to stop; `"error"` raises `ToolCallLimitExceededError` |
| `ModelRetryMiddleware`, `ToolRetryMiddleware` | transient failures | both default to `on_failure="continue"`, which turns the failure into a message |
| `ToolErrorMiddleware(on_error=)` | errors the model can correct | the handler returns content for an error `ToolMessage`, or `None` to re-raise |

**Decision:** adopt the middleware, with explicit limits and the
`"error"` behaviours, so that an exhausted budget is a terminal outcome and
never prose. Chosen by the agent; it follows the inherited lesson already in
CLAUDE.md.

## Orchestration rung

N-A -- no graph is built.

## The gap trace -- the source plan, line by line

Source: `langchain-playground/langgraph-adaptation.md`, read on 2026-10-05.

| Source | Requirement | Before this change | This change |
|---|---|---|---|
| 143-215 | the destination package tree: `domain/agents/{approvals,budgets,routing,policies,state_versions}`, `application/agent_cases`, `infrastructure/agents/{middleware,graphs/<name>/{nodes/,subgraphs/},deepagents/}`, `tests/*/agents` | a reduced tree | the source's tree, adapted, in `graphs.md` and the architecture overview |
| 237-238 | short-lived execution state separate from long-term memory; memory has ownership, tenant scope, retention, deletion, provenance | absent | `graphs.md`, State |
| 242-243 | node boundaries are recovery, checkpoint, telemetry and test boundaries | implicit | `graphs.md`, Nodes |
| 255-257 | model-recoverable failures become typed state for re-planning; unexpected ones surface and are observed | reworded | `graphs.md`, Errors |
| 261-266 | tools: audit events; tool descriptions are untrusted | partial | `graphs.md`, Tools |
| 271-287 | the Deep Agents position | ADR 0003 and an auditor only | `graphs.md`, and the ladder |
| 338-340 | the smoke run: a second process can query the run's state | missing | roadmap slice 1 |
| 358-360 | redaction; provision, migrate, back up, restore, monitor | partial | `graphs.md`, Persistence |
| 370-378 | seven test layers: domain unit, node, graph contract, graph integration, persistence integration, server acceptance, live/evaluated | five rows | the seven layers in `graphs.md` |
| 405-406 | a write-capable tool without a manifest fails an architecture check | absent; deferred, with the user's agreement | a required, fixture-proven check in roadmap slice 4, where the manifest format is decided with the first tool |
| 407-408 | `langgraph.json` names an absent or **non-compiled** export | absent export only | the compiled-graph check in roadmap slice 1, once `langgraph` is installed |
| 420-423 | scenario fixtures include forbidden cross-tenant access and timeouts | missing from the auditor | `graph-eval-auditor` |
| 437, 445-447 | the design record: non-goals; the local and production runtime plan; tests for security, operations and migration | partial | the frame's Outcome slot asks for non-goals; the design template's Runtime and Test plan slots |
| 455-457 | acceptance criteria name the routes: completion, refusal, approval, rejection, retry exhaustion, interruption, resume, limit exhaustion | how to test a route, not a duty to name them | the schema's specs instruction, `/discover`, and a route checklist in the ladder |
| 461-463 | a graph is built a vertical slice at a time | absent | `graphs.md` and the ladder |
| 473, 478 | `/verify`: each state field justified, serialisable, classified and owned; `langgraph.json`, the registry and the checkpointer agree | partial | the auditors |
| 481-490 | the four auditors at review | two in `/verify` | `/verify` adds the durability and graph-evaluation auditors when their subject changes |
| 484 | no hidden graph factories | absent | `graph-architecture-guardian` |
| 502-504 | the edit guard for generated checkpoint data and live server credentials | gitignore and a build-time check only | the guard refuses both at write time |

The consolidated feedback (`consolidated_feedback_sdd_final.md`) was re-read the
same day. Every item is in the method, or deliberately different and
documented:
- **archive inside the branch rather than after the merge** -- METHOD §9;
- **`sdd.toml` rather than `.sddrc.yaml`** -- TOML is in Python's standard library;
- **`tasks.md` for every class** -- OpenSpec's apply needs it;
- **the invariants in the schema rather than in `config.yaml` `rules:`** -- the schema ships with the method.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | the trace table; two guard refusals with tests |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | the two guard rules are requirements with counter-examples. The rest is prose a reader applies, so no test can prove it |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | deterministic only |
| Data -- provenance, freshness, what happens when a source is withdrawn | Clear | the source plan is cited by line; the middleware facts are pinned to langchain 1.4.3 |
| Untrusted input -- anything ingested that this project did not write | N-A | nothing ingested |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Partial | the guard now refuses three file patterns and one key. A project that keeps a hand-written `*.db` fixture in the repository will be asked to write it some other way |
| Failure -- what the user sees when a dependency is down | N-A | no runtime dependency |
| Cost -- tokens, time, money and storage per run | N-A | |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | the repository owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Should the guard refuse every `*.db`, or only paths that look like checkpoints? | answered | every `*.db`, `*.sqlite` and `*.sqlite3`. A checkpoint store can sit anywhere; refusing an edit costs a person a retry, and a hand-edited store corrupts threads. The edit guard only sees the agent's edit tools, which never write a binary store on purpose |

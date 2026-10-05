# Design

Why: `frame.md`. The decision that is expensive to reverse is recorded in
`docs/decisions/0004-langgraph-runs-locally.md`.

## Context

The langgraph pack (0.2.0) said where graphs live and how they are built. It
did not say how they run, and its only runtime story -- Studio, then
`langgraph up` -- goes through LangSmith. The user's constraint rules that
out. Measuring the local development server showed that "local" is not its
default: it reaches out three ways, and one of them (usage metadata to
`api.smith.langchain.com`) survives `LANGSMITH_TRACING=false`. So local-only
has to be built into the commands the project uses, not left to habit.

The same release closes the pack's other gaps from the gap analysis: the folder
structure as a rule, graph test tiers, route-based acceptance, error classes,
read and write nodes, the subgraph criterion, persistence security, and the
design record's missing slots.

## Decisions

### 1. Local-only in three layers, each covering what the next cannot

| Layer | Covers | Mechanism |
|---|---|---|
| the agent's commands | anything the agent runs | settings `permissions.deny` -- `smith.langchain.com`, `--studio-url`, `--tunnel`, `langgraph deploy`, `langgraph up`, and `langgraph dev` other than through the wrapper -- and settings `env`, the local-only environment below |
| the server | whoever starts it: the agent, a person, a script | `scripts/serve.sh`: 127.0.0.1, no browser, an allowlist of flags, the local-only environment; refuses a `langgraph.json` `env` key and a `.env` that sets a credential or switches tracing on |
| people | what no setting reaches | CLAUDE.md, `.claude/rules/langgraph/runtime.md`, ADR 0004 |

Alternatives considered:

- **A PreToolUse hook on Bash** that would show its reason when it refuses.
  Refused: the native rules already match every subcommand, skip leading
  variable assignments, and need no shell parsing in bash 3.2.
- **Telling people only.** Refused: `langgraph dev`'s defaults open
  smith.langchain.com, and a LangSmith key exported in a developer's shell is
  common. The default must be safe.
- **Blocking at the network** (a firewall or proxy). Out of a method's reach;
  recorded in the ADR as the real boundary for anyone who needs one.

**The local-only environment** -- twelve variables, each there because a
measurement in `frame.md` needed it:

| Variables | Value | Because |
|---|---|---|
| `LANGSMITH_TRACING`, `LANGSMITH_TRACING_V2`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_TRACING` | `false` | the server reads `LANGSMITH_TRACING` first, `langsmith` reads `*_TRACING_V2` first: only all four agree |
| `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, `LANGSMITH_CONTROL_PLANE_API_KEY`, `LANGGRAPH_CLOUD_LICENSE_KEY` | empty | a key starts the server's metadata loop and switches tracing on when unset. **Emptied, not unset**: `python-dotenv`'s default never overrides a variable that is present, and both libraries read a blank key as none |
| `LANGSMITH_ENDPOINT`, `LANGCHAIN_ENDPOINT` | `http://127.0.0.1:9` | the backstop: tracing switched back on reaches a closed local port, loudly, instead of `api.smith.langchain.com` -- measured |
| `LANGGRAPH_CLI_NO_ANALYTICS` | `1` | every `langgraph` command otherwise posts usage analytics |
| `LANGGRAPH_NO_VERSION_CHECK` | `true` | the server otherwise asks pypi.org for the latest version |

Tracing switched on in one command is therefore harmless rather than denied: it
meets the closed port. Pointing the endpoint back at LangSmith needs the text
`smith.langchain.com`, which is denied.

### 2. `langgraph.json` carries no `env`

The server loads that file **over** its environment (`run_server` patches
`os.environ` with it), so it would undo the wrapper. It would also be a
second loader of `.env` beside `config/`, the layer that owns configuration.
The graphs get their settings from `config/`, through the registry's
composition. The wrapper refuses an `env` key, and an architecture check fails
the build on one.

### 3. A pack can seed files and add to the seeded settings

`install --packs langgraph` seeds `scripts/serve.sh` and merges
`seeds/settings.langgraph.json` into the settings it seeds. Settings the
project already has are never touched: the additions are reported, to merge by
hand. `update` writes no seed, as before. It reports a pack seed the project
lacks, and running `install` again with the same packs writes it, since
install never overwrites.

The merge accepts only `env` and the `permissions` lists, and refuses
anything else -- including an `env` key that conflicts with the core seed. A
merge that silently dropped a key would make a pack look installed when it was
not.

The seed files themselves ship in **core**, though only the langgraph pack
seeds them. The method's own `test_serve.py` reads them, and the selftest runs
in every installed copy. A copy without the pack would otherwise fail its own
tests -- or, used as a source, have nothing to seed from.

Alternatives considered:

- **Put the LangGraph rules in the core seed.** Refused: deny rules about a
  stack the project does not use are noise.
- **Hand-merge instructions only.** Refused: a fresh install would then not be
  local-only, which is the outcome.

### 4. What replaces Studio, and `langgraph up`

| Job | Hosted tool | Local replacement |
|---|---|---|
| see the topology | Studio's graph view | `graph.get_graph().draw_mermaid()` -- never `draw_mermaid_png()`, whose default posts the graph to mermaid.ink -- and `GET /assistants/{id}/graph` on the local server |
| run, stream, interrupt, resume | Studio's run panel | `scripts/serve.sh` with `langgraph_sdk` or `curl` against 127.0.0.1 |
| prove a route | (Studio proves nothing) | fake-model scenario tests -- the evidence that was always required |
| prove durability | `langgraph up` | a durable checkpointer composed in the project: SQLite on a temporary file in the default suite, Postgres as `live` -- pause, rebuild the graph on the same store, resume |

The architecture overview already says Studio rendering a graph is not
evidence. This replaces its convenience, not its proof.

### 5. Three architecture checks, each proved able to fail

Each check lives in `tests/architecture/` and follows the existing pattern: a
helper in `contract.py`, a test on this package, and fixtures that must fail.
They skip -- visibly, with the reason -- until a graph exists, because a
confinement check over a directory that does not exist would pass while
checking nothing.

- **Registration.** Every `langgraph.json` graph resolves to a name bound at
  the top level of `infrastructure/agents/registry.py`, either as a path or as
  a dotted module. Every graph id is a stable identifier (lowercase, digits,
  `-`, `_`). The file has no `env`.
- **The agents adapter imports an allowlist**: `langgraph`, `deepagents`,
  `langchain`, `langchain_core`, `pydantic`, `typing_extensions`. A provider
  SDK or an HTTP client there is a dependency that did not arrive through
  composition -- and a node no fake can replace.
- **No model built inline.** In `infrastructure/agents/`, `init_chat_model(...)`
  and a string model passed to `create_agent` or `create_deep_agent` are
  refused (the commonest form in LangChain's own quickstarts). The model
  arrives as an object, built by a model builder outside `agents/`.

### 6. The design record gains the slots a production graph needs

Identity (thread, tenant, user, and the ownership check before resume),
streaming, errors by class, observability (local only), runtime, and the test
plan by tier. The persistence slot now asks for encryption, tenancy and
retention.

### 7. Status honours a declared `skip_specs`

`status.py` reads `skip_specs: true` from `.openspec.yaml`. Such a change shows
`specs~` and moves past specs, as `openspec status` does. Without the
declaration a change without delta specs still stops at `specs`.

## Orchestration design

N-A -- no graph is built by this change.

## Risks

- **An undocumented switch disappears in an upgrade.**
  `LANGGRAPH_NO_VERSION_CHECK` is "not in public docs" in its own source ->
  the connection probe in `runtime.md` is re-run at every upgrade of
  `langgraph-cli` or `langgraph-api`, and the versions are pinned at the
  foundation slice.
- **Deny rules match text, so a search can trip them.** For example,
  `grep -rn "langgraph dev"` in Bash -> CLAUDE.md says to use the Grep tool for
  searches; a false refusal costs a retry, not a leak.
- **The deny rules are not a boundary.** A shell started another way, or a
  person, can still reach LangSmith -> the ADR says so, and names the boundary
  for anyone who needs one: the network.
- **Unverified: whether a deny rule sees a leading variable assignment.** The
  documentation says deny rules match "past" one, not whether they also match
  it -> nothing relies on it. Tracing switched on in a command meets the closed
  port, so no rule has to catch it.
- **Entry points a person runs outside the agent.** They do not get the
  agent's settings `env` -> the roadmap's foundation slice adds a product
  requirement: every entry point starts from the local-only environment.
- **No visual debugger.** Studio's convenience is gone -> the local API and
  Mermaid text cover inspection; route tests cover proof.

## Migration and rollback

- **Projects on 0.2.0 with the langgraph pack.** `update` brings the new
  shipped files. Running `install` with the same packs then seeds
  `scripts/serve.sh`. `seeds/settings.langgraph.json` is merged into their
  settings by hand. The CHANGELOG says this.
- **Data.** Nothing persists: no graph, no checkpoint, no thread exists yet.
  `.langgraph_api/`, where the in-memory server stores development threads,
  is gitignored from now on.
- **Rollback.** Revert the PR. The settings additions are project-owned once
  seeded, so a reverted method leaves them in place until removed by hand.

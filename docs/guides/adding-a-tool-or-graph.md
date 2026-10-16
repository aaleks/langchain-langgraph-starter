# Adding a tool, or another agent

Everything new arrives the same way: as an OpenSpec change, through the
method's loop. This guide shows the two most common additions -- a new tool
for the assistant, and a second graph the server serves -- and where each
piece goes.

## The loop, for any change

| Step | You run | It produces |
|---|---|---|
| 1 | `/intake <what you want>` | the class -- bounded or structural -- said out loud; `openspec/changes/<id>/intake.md` |
| 2 | `/discover` | the frame (existing options considered, the orchestration rung), the requirements with real scenarios, a design and an ADR when structural, tasks |
| 3 | `/accept` | one failing test for one requirement, red for the right reason |
| 4 | `/tdd` | the code that turns it green: red, green, refactor, one cycle |
| 5 | `/verify` | fresh-context reviewers; findings only, in `verify.md` |
| 6 | `/land` | the specs archived into `openspec/specs/`, the change merged |

`bash .claude/sdd/sdd.sh status` shows where each change stands.
`bash scripts/check.sh` must pass before every commit.

Two rules decide most of the shape:

- **Challenge the build.** Before a requirement is drafted, name the
  maintained libraries that already do it. Adopting one is not
  over-engineering; writing your own is the thing to justify.
- **Take the lowest rung.** One model call in a use case; a tool loop; a
  hand-written `StateGraph` -- only when a requirement needs the control flow.

## A new tool for the assistant

Say the owner wants tasks searched by assignee. Class: **bounded** (it extends
an existing flow) -- unless it writes, which makes it a new approval route and
**structural**.

### Where each piece goes

| Piece | Where | Holds |
|---|---|---|
| the rule | `src/starter/domain/tasks.py` | validation and limits, pure: a test calls it with plain values |
| the query | `src/starter/infrastructure/stores/tasks.py` | a method on `TaskReader` -- the read-only view, never the store |
| the tool | `src/starter/infrastructure/agents/tools/<tool>.py` | `CAPABILITY` and `build(reader)` |
| the wiring | `tools/__init__.py` | added to `read_tools(reader)` (or `write_tools()`) |
| the prompt | `src/starter/application/prompts.py` | the tool named, a new version, its digest pinned |
| the proof | `tests/unit/`, `tests/integration/agents/` | one class per requirement, the requirement's id in its docstring |

### The tool module

Every tool is one module with its capability manifest beside it -- copy
`search_tasks.py`:

```python
CAPABILITY = Capability(
    name="search_by_assignee",
    output=TaskPage,
    errors=(sqlite3.Error,),  # what may propagate
    idempotent=True,
    timeout_seconds=TASK_STORE_TIMEOUT_SECONDS,
    retry="none",
    calls_per_run=TOOL_CALLS_PER_RUN,
    side_effect="read",  # "write" sends it down the approval route
    audit_event=None,  # a write names its audit event
)


def build(reader: TaskReader) -> BaseTool:
    @tool
    def search_by_assignee(assignee: Assignee) -> str:
        """The open tasks assigned to `assignee`, oldest first."""
        return json.dumps(reader.by_assignee(assignee, TASK_RESULTS_LIMIT), ensure_ascii=False)

    search_by_assignee.metadata = {"capability": CAPABILITY}
    return search_by_assignee
```

The factory checks every manifest before it compiles anything
(`check_capability`): a tool without one, a manifest naming another tool, or a
write without the writer, an audit event and a builder is refused at start.

### A write tool

A write tool is a **proposal only**: its function raises if called, and its
metadata carries a domain builder that turns checked arguments into a write --
see `add_task.py`. The graph sends every `side_effect="write"` tool through
`review_writes` and `apply_writes`, so the owner approves it and the store
applies it once under its key. Adding one means a new action in the store's
writer and in `task_writes`' `CHECK`, with a schema migration: structural.

## A second agent -- another graph

Say you want a `planner` graph beside `assistant`. Class: **structural** -- a
new graph id is a public interface.

1. **`/discover` chooses the rung.** If a `create_agent` tool loop expresses
   it, use that; it still lives under `infrastructure/agents/` and is compiled
   by the factory.
2. **Design first.** `design.md` holds its node table -- node, kind (read,
   decide, write), what it reads and writes, where it routes, which domain
   policy decides. The table is the contract a test holds the graph equal to.
3. **Build it a slice at a time**, under
   `src/starter/infrastructure/agents/graphs/planner/`:
   - `state.py` -- the state contract and its version;
   - `nodes.py` -- one effect each, named for the outcome;
   - `routes.py` -- each conditional edge calls a domain policy in
     `domain/agents/`;
   - `graph.py` -- nodes and edges, uncompiled.
4. **Compose and register.**
   - `factory.py`: `build_planner(...)` -- the only place a graph is compiled.
   - `registry.py`: `planner = registered_planner()` -- the only names the server
     may load.
   - `langgraph.json`: `"planner": "./src/starter/infrastructure/agents/registry.py:planner"`.
     Ids are lowercase letters, digits, `-` and `_`. No `env` key, ever.
5. **Prove the routes with fakes.** A fake model (`fake_llm` in
   `tests/conftest.py`) drives each route; the test asserts the nodes visited
   and the terminal status, never the text. A `live` test through
   `scripts/serve.sh` proves the server serves it.

`tests/architecture/` refuses a graph compiled outside the factory, a
`langgraph.json` entry that is not a registry export, `langgraph` imported
outside `infrastructure/agents/`, and a model built anywhere but
`infrastructure/models.py`.

## Seeing it run -- without Studio

This project does not use hosted LangGraph Studio (ADR 0004). What replaces
it:

| Job | Use |
|---|---|
| the topology | `print(graph.get_graph().draw_mermaid())` -- text; paste it into any Mermaid viewer |
| a run, its state, its history | the local server's API: `langgraph_sdk.get_sync_client(url="http://127.0.0.1:2024")` -- `threads.create()`, `runs.wait()`, `threads.get_history()` |
| an approval | Agent Chat UI on `localhost:3000`, or `command={"resume": ...}` from the SDK |
| the API | `GET http://127.0.0.1:2024/openapi.json` |
| proof | a fake-model test. Watching a run is debugging, never evidence |

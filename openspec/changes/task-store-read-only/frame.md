# Frame

## Outcome

**For the owner**: tasks added from the command line
(`uv run starter tasks add "Renew passport" --assignee sam`) are what the
served `assistant` sees. Asked "what is open?" or "anything about the
passport?", the model calls `list_tasks` or `search_tasks` and answers from
the rows those return. The signals:

- a stand-in model's tool call, run through the registered graph against a
  task file the CLI wrote, returns those rows (the default suite, no model);
- every tool the graph is given carries a capability manifest, and a graph
  given a tool without one, or a tool that writes, is refused at start;
- no run executes more than `TOOL_CALLS_PER_RUN` tool calls.

**Non-goals** (slice 3b and later):

- Writes through the model: create, close and reassign are slice 4, behind
  `interrupt()`. The CLI's `add` is the owner's own write, not the model's.
- Task text as untrusted data, with an adversarial case; the decision on
  `invalid_tool_calls`; `MODEL_CALLS_PER_RUN` and `TOOL_CALLS_PER_RUN`
  re-measured against real runs. All are slice 3b, which needs the owner's
  Open WebUI answering.
- Full-text search, ranking, due dates, priorities, several lists, several
  users. No requirement asks for them.

## Existing options considered

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| stdlib `sqlite3` | Ships with Python 3.13 | The file, the queries, `PRAGMA user_version` for the schema's version, `LIKE` for search | We own the schema and two read queries, about 60 lines |
| sqlite-utils 4.x | 4.0 shipped 2026-07-07, point releases through August (search: the author's weblog, Debian's tracker) | Table creation, migrations, FTS helpers, a CLI to inspect the file | A dependency to bound and re-check; its migrations cover a schema of one table |
| SQLAlchemy 2.x with Alembic | 2.1 in release candidates in September 2026; 2.0 current (sqlalchemy.org blog) | An ORM, typed models, migrations | The heaviest option, for one table and one database |
| LangChain's SQL toolkit (`langchain_community`) | Current reference pages | Tools that let the model list tables and run SQL | Rejected: the model writes the SQL, so a write could reach the list without the approval slice 4 requires |

**Decision:** build on the stdlib's `sqlite3`. One table and two read queries
do not repay a dependency. The schema carries its version from the first file
written, so a later move to a library has something to migrate from. Chosen by
the owner, 2026-10-13 ("stdlib sqlite3 (Recommended)").

The **capability manifest** is this project's format (`.claude/rules/langgraph/graphs.md`
lists its fields). Nothing maintained defines one for LangChain tools. A
tool's `args_schema` already gives the typed input, so the manifest adds what
LangChain has no field for.

## Orchestration rung

The tool loop, unchanged (ADR 0005): `create_agent` and its middleware.
`ToolCallLimitMiddleware(run_limit=TOOL_CALLS_PER_RUN, exit_behavior="error")`
bounds tool calls the way `ModelCallLimitMiddleware` bounds model calls. Reads
need no interrupt and no routing policy, so nothing here needs a hand-written
graph. Slice 4 decides the rung for writes.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | Above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | Each requirement has its counter-example: a blank title, a `%` in a query, a newer schema, a tool without a manifest, a writing tool, the call past the budget |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | All deterministic. Tools return rows, never prose, and a fake model proposes the calls |
| Data -- provenance, freshness, what happens when a source is withdrawn | Partial | Written by the owner's CLI only. A file whose schema is newer than the code is refused at start. A missing file is created empty. No backup: slice 5 (durability) owns it |
| Untrusted input -- anything ingested that this project did not write | Partial | Task text reaches the model as tool output. Its treatment as data, with an adversarial case, is slice 3b. Here, a search query is only ever a bound parameter, `%` and `_` matched literally |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | The CLI `starter tasks add`, the first `[project.scripts]` entry. The setting `TASKS_DB`. The tool names and their output shape. The manifest format. `TOOL_CALLS_PER_RUN`. Each one is a requirement |
| Failure -- what the user sees when a dependency is down | Clear | An unreadable or newer task file: refused at start, naming the file. A locked file: the manifest's timeout, then the error propagates (ASSISTANT-ERRORS-PROPAGATE) |
| Cost -- tokens, time, money and storage per run | Partial | Each result is capped at `TASK_RESULTS_LIMIT` rows, and says how many more matched. Both bounds are starting policies, re-measured in 3b |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | The owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Which store library? | Asked | stdlib `sqlite3` (the owner, 2026-10-13) |
| 2 | How do tasks get in before slice 4? | Asked | The owner's CLI, `starter tasks add` |
| 3 | What does search match? | Asked | A case-insensitive substring of the title or the notes |
| 4 | One change or two? | Asked | Two: 3a here, and 3b |
| 5 | `TOOL_CALLS_PER_RUN` and `TASK_RESULTS_LIMIT` | OPEN | Starting policies (20 and 50), like `MODEL_CALLS_PER_RUN` before them. Re-measured in 3b against real runs through the owner's Open WebUI |

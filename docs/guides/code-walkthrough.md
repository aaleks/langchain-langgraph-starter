# A walk through the code

The order a request travels, from the server's front door to the task list,
then how to watch it -- locally, without Studio. Paths are under
`src/starter/` unless they say otherwise.

## 1. The front door: `langgraph.json` and `scripts/serve.sh`

```json
{
  "dependencies": ["."],
  "graphs": { "assistant": "./src/starter/infrastructure/agents/registry.py:assistant" },
  "python_version": "3.13",
  "http": { "app": "./src/starter/infrastructure/server/guard.py:app" }
}
```

- `graphs` names one id, `assistant`, and one export of the registry. There is
  no `env` key: the server loads it over its own environment, which would undo
  the local-only one.
- `http.app` is the request guard, which runs before CORS and every route.
- `scripts/serve.sh` is the only way the server starts: 127.0.0.1, the
  local-only environment, one browser origin (`http://localhost:3000`).

## 2. The guard: `infrastructure/server/guard.py` and `domain/access.py`

The adapter reads the request's method and headers, and asks the domain:

```python
def request_refusal(*, socket, method, path, host, origin, content_type, has_body) -> str | None:
```

It refuses:

- a `Host` that is not this machine (DNS rebinding);
- the development server's own `/deploy` and `/internal/` routes;
- a WebSocket from another page's `Origin` -- the server's event stream starts
  and resumes runs over one, and CORS never applies to it;
- a write from another page's `Origin`, or with a body that is not
  `application/json`.

Anything but HTTP, WebSockets and the server's lifespan reaches nothing.
CORS limits what a page may read; this refuses what it may send.
The pattern repeats everywhere: **the adapter acts, the domain decides.**

## 3. Composition: `infrastructure/agents/registry.py` and `factory.py`

```python
def registered_assistant(settings=None):
    settings = settings if settings is not None else settings_from_process()
    model = build_model(settings)
    store = TaskStore(tasks_db_path(settings))
    store.open()
    tools = [*read_tools(store.reader(TASK_STORE_TIMEOUT_SECONDS)), *write_tools()]
    return build_assistant(
        model, tools=tools, transient=is_transient_failure, writer=store.writer()
    )
```

- `config/settings.py` is the only reader of the environment and `.env`; the
  environment wins, and `.env` never enters it.
- `infrastructure/models.py` is the only place a model is built: Open WebUI's
  OpenAI-compatible API when `.env` configures it, an offline fixed-answer model
  otherwise.
- `factory.build_assistant` checks every tool's capability manifest, then
  compiles -- the only place a graph is compiled -- with the step ceiling set.

## 4. The graph: `infrastructure/agents/graphs/assistant/`

| File | Holds |
|---|---|
| `state.py` | `AssistantState`, version 2: `messages`, `model_calls`, `tool_calls`, `write_decisions` |
| `graph.py` | the five nodes and their edges, uncompiled |
| `nodes.py` | one effect each: `start_run`, `call_model`, `run_tools`, `review_writes`, `apply_writes` |
| `routes.py` | each conditional edge, calling a domain policy |

The topology, as text:

```python
from starter.infrastructure.agents.registry import assistant

print(assistant.get_graph().draw_mermaid())
```

Paste the output into any Mermaid viewer. Never `draw_mermaid_png()` with its
default: it posts the graph to a web service.

## 5. The decisions: `domain/`

| Module | Decides |
|---|---|
| `domain/agents/routing.py` | where each edge goes: `route_after_reply`, `route_after_tools`, `route_after_writes` |
| `domain/agents/budgets.py` | model calls and tool calls per run, the step ceiling |
| `domain/agents/approvals.py` | what the owner is shown, what a resume means, the write's key |
| `domain/agents/capabilities.py` | the manifest, and whether the assistant can honour it |
| `domain/tasks.py` | a task's rules, a write's values, the store's limits |
| `domain/access.py` | who may change anything through the server |

Standard library only, deterministic, inputs as arguments: each is proved by a
unit test with `==`.

## 6. Tools and the store: `infrastructure/agents/tools/`, `infrastructure/stores/tasks.py`

- Each tool is a module with its `CAPABILITY` and a `build(...)`.
- Read tools hold a `TaskReader` -- a read-only connection; it cannot write.
- Write tools are proposals: called directly they raise. `apply_writes` applies
  an approved write through `TaskWriter`, once per key, in the same
  transaction as its `task_writes` record.

## 7. The method's own files

| Where | What |
|---|---|
| `openspec/specs/` | the living requirements, each naming its test |
| `openspec/changes/` | changes in flight: intake, frame, specs, design, tasks, verify |
| `docs/decisions/` | the ADRs |
| `tests/architecture/` | the layer and registration contracts, each proved to fail on a fixture |
| `.claude/` | the method: skills, reviewer agents, rules, hooks |

## 8. Watching it run -- the local replacement for Studio

Start the server (`bash scripts/serve.sh`), then from Python:

```python
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://127.0.0.1:2024")
print(client.assistants.get_graph("assistant"))  # the topology, as JSON

thread = client.threads.create()
client.runs.wait(
    thread["thread_id"],
    "assistant",
    input={"messages": [{"role": "human", "content": "What is on my list?"}]},
)

for snapshot in client.threads.get_history(thread["thread_id"]):
    print(snapshot["next"], len(snapshot["values"]["messages"]))
```

| Studio would show | Here |
|---|---|
| the graph | `draw_mermaid()` text, or `GET /assistants/assistant/graph` |
| a run's state and history | `threads.get(...)`, `threads.get_history(...)` |
| an interrupt, and resuming it | Agent Chat UI on `localhost:3000`, or `runs.wait(..., command={"resume": ...})` |
| the API | `GET /openapi.json` |

Inspecting a run is debugging. What proves a route is a fake-model test.

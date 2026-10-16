# Getting started

From a fresh clone to an approved write, on your own machine. Nothing here
needs a LangSmith account, and nothing leaves the machine but the calls to
your own Open WebUI, if you configure one.

## 1. What you need

- **Python 3.13 and [uv](https://docs.astral.sh/uv/).** `uv sync` installs
  everything else.
- **Node 20.19 or later**, for the pinned OpenSpec CLI that `check.sh` runs.
- **Bash.** On Windows, Git Bash.
- **Optional: Open WebUI**, with API keys switched on, for a real model.
  Without it an offline model answers with a fixed sentence, and every step
  below still works except a write being proposed.

## 2. Install and check

```bash
git clone <this repository>
cd langchain-langgraph-starter
uv sync
bash scripts/check.sh
```

`check.sh` runs everything CI runs, in one list: format, lint, the
architecture contracts, `sdd check` (every requirement names its test, every
test is claimed), OpenSpec validation and the suite. It ends with
`all checks passed`. No test in it calls a model or needs a service.

## 3. Connect your model (optional)

```bash
cp .env.example .env
```

Then edit `.env` yourself and set all three, or none:

```bash
OPENWEBUI_URL=http://localhost:8080      # the address you open in a browser
OPENWEBUI_API_KEY=sk-...                 # Open WebUI: Settings > Account > API Keys
OPENWEBUI_MODEL=gpt-5.4-mini             # the model id exactly as Open WebUI lists it
```

- `.env` is yours: the project's agents are refused both reading and writing
  it. Never put a LangSmith key or a tracing switch in it -- `serve.sh` refuses
  to start while it holds one.
- Run Open WebUI on a port other than 3000: Agent Chat UI needs 3000 (step 6).
- A partial configuration is refused at start, naming what is missing and
  never quoting a value.

Check it with the live tests, which reach your Open WebUI:

```bash
bash scripts/check.sh live
```

## 4. Add a task

```bash
uv run starter tasks add "Renew passport" --assignee sam --notes "photos first"
```

It prints the new task's id. The list is a SQLite file at `TASKS_DB`,
`.data/tasks.sqlite3` unless `.env` says otherwise.

## 5. Start the local server

```bash
bash scripts/serve.sh          # http://127.0.0.1:2024
```

This is the only way the server starts:

- it binds 127.0.0.1;
- it runs in an environment in which nothing reaches LangSmith -- tracing
  off, every LangSmith key empty, its endpoint a closed port;
- it allows one browser origin, `http://localhost:3000`, and a request guard
  refuses any other page's writes.

The banner prints a "Studio UI" link. It is printed, never opened: this project
does not use hosted Studio (ADR 0004).

## 6. Talk to it, and approve a write

**In Agent Chat UI** (LangChain's open-source chat for LangGraph servers):

1. Run it on `http://localhost:3000` -- see its README; `npx create-agent-chat-app`
   or a clone of `langchain-ai/agent-chat-ui`, then `pnpm dev`.
2. Deployment URL `http://127.0.0.1:2024`, graph id `assistant`. Leave the
   LangSmith key empty.
3. Ask *"What is on my list?"* -- it reads freely.
4. Ask *"Add a task to call the plumber."* -- the run pauses, and the approval
   request shows the action and its description. Approve or reject.

**Or from Python**, with the SDK the dev group installs:

```python
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://127.0.0.1:2024")
thread = client.threads.create()
client.runs.wait(
    thread["thread_id"],
    "assistant",
    input={"messages": [{"role": "human", "content": "Add a task to call the plumber"}]},
)

state = client.threads.get(thread["thread_id"])  # status: interrupted
print(state["interrupts"])  # the approval request

client.runs.wait(
    thread["thread_id"], "assistant", command={"resume": {"decisions": [{"type": "approve"}]}}
)
```

The list now holds the new task, and its `task_writes` table records your
decision.

## 7. What happens on a write

1. The model proposes `add_task`. Its arguments are checked by the tool's
   schema and the list's rules before you see anything.
2. The run pauses in `review_writes` with LangChain's approval request.
3. You resume with `approve` or `reject`. Anything but an exact approval
   rejects.
4. `apply_writes` applies it once, under the key `[thread, reply, call]`, and
   records it in `task_writes`. A replay cannot write twice.
5. A rejection ends the run, with no further model call.

## Where next

- `docs/guides/adding-a-tool-or-graph.md` -- extend it, through the method.
- `docs/guides/code-walkthrough.md` -- the code, file by file.
- `CLAUDE.md` -- the one-page map; `docs/decisions/` -- why it is this way.

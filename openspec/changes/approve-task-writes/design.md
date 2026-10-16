# Design

Why: frame.md. What: the delta specs. This is how.

## Context

The graph is ADR 0007's: `start_run`, `call_model`, `run_tools`. The store
is ADR 0008's: a writer that applies a write once per key, and records each
decision. This change joins them through the owner's approval.

## Decisions

1. **Two nodes, and one more route.**
   - `review_writes` is a decide node. It builds the approval request from
     the reply's waiting write calls, and `interrupt()`s. On resume it
     returns the decisions as state.
   - `apply_writes` is a write node. It decides one waiting write a step
     through the writer, and answers it, then routes back to itself while
     another waits. A write's answer is stored with it, in the same step
     (verify pass 1, finding 3). The store's commit and the step's
     checkpoint are still two transactions: a run cancelled or killed
     between them loses the answer, never the write. So `start_run`
     answers a write call left unanswered with what the store recorded
     under its key, and "not run" only when nothing is (pass 2, N1).
   - The answer and the route follow the outcome the writer returns -- the
     one recorded under the key -- never a later decision: a replay that
     decides otherwise is told what was done (finding 4).
   - They are separate nodes, so the write sits after the interrupt in its
     own step, and the interrupt's node, re-run on resume, writes nothing.
2. **`run_tools` splits the reply's calls:**
   - Reads and unknown tools go through `ToolNode`, as before. It is given a
     copy of the reply holding only those calls.
   - Write calls are checked:
     - by the tool's schema (pydantic, strict, so `true` or `"1"` is no task
       id);
     - by the domain's builder (TASKS-WRITE-VALUES);
     - for a thread to pause on -- a thread id and a checkpointer, read
       from the run's config, since a thread id alone is nothing to come
       back to (pass 2);
     - for a key short enough to record.

     A refused one is answered then and there; an accepted one is left
     unanswered, waiting.
   - Malformed calls are answered as before.
   - The tool-call budget counts every well-formed call, writes included.

   The domain's `route_after_tools`, on the number of writes waiting, goes
   to `review_writes` or `call_model`.
3. **The approval request is LangChain's** `HITLRequest` shape, built as
   plain data. No import from `langchain.agents.middleware` is needed: the
   shape is the interface, and the test pins it.
   - `action_requests`: one per waiting call, in the reply's order -- the
     tool's name, the checked arguments, and a description from the
     domain's `describe_write`. Every waiting call is asked about, so the
     owner's decisions meet the actions they were given for, by position,
     on the resume too: one the rules refuse by then is described `Not
     valid: <why>`, and `apply_writes` answers it (pass 2: a list rebuilt
     shorter on resume once turned an approval into a rejection, or onto
     the wrong write).
     - A task named by its id is described by its title and status, read
       from the list by the writer's `task()`. The model's word for it
       never reaches the owner: task text could steer it (finding 5).
     - Text from the list or the model is quoted as JSON, so a quote or a
       line break cannot read as another action (finding 6); every
       control, format, line- and paragraph-separator character is
       escaped too, so a direction override or U+2028 cannot (pass 2).
     - A status other than `open` is shown as the fixed word `closed`,
       never the file's text (pass 2).
   - `review_configs`: one per tool named, in first-named order, each
     allowing `approve` and `reject`.

   The resume is read by the domain's `read_decisions(resume, count)`.
   - Each action gets `approve` only for an exact `{"type": "approve"}`;
     any other decision rejects it.
   - A resume that is not `{"decisions": [...]}` of the right length
     rejects every action.
4. **The key is `["<thread id>", "<reply id>", "<call id>"]`**, a JSON
   array from the domain's `write_key`, so a `:` in one part never makes it
   another's (finding 8). It is checked against `WRITE_KEY_MAX` with the
   proposal, before the owner is asked (finding 9).
   - The thread id is `config["configurable"]["thread_id"]`.
   - The reply id is the stored id of the AI message that proposed the
     call. It is unique in the transcript (ASSISTANT-STATE-CONTRACT), and
     the same on every replay.
   - The call id is unique in its reply: `call_model` gives a well-formed
     call whose id is missing, or used already in the reply, a new one
     (`calls_to_rename`). Two calls under one id once let the owner's
     rejection of one become an approval of both (finding 1).
   - The superstep was the first design, and is wrong. Measured: a replay
     from the checkpoint before `apply_writes` ran it at step 6 where the
     first run used 5, and the write was applied twice. The roadmap's "per
     thread and step" is met by the reply, which names the step's proposal.
   - A replay or a continue after `apply_writes` failed part-way re-runs it
     under the same keys, so the writes it already made are not made again
     (ADR 0008).
5. **The outcome as the model reads it is JSON**, from the domain's
   `outcome_message`:
   - `{"outcome": "applied", "task_id": 8}`, status `success`;
   - refused: the same keys plus a `reason`, status `error`;
   - rejected: the fixed sentence `REJECTED_ANSWER` in `application/prompts.py`,
     status `error`.
6. **After a write**, the domain's `route_after_writes` goes back to
   `apply_writes` while a write of the reply waits. Then it goes to
   `call_model` when none was rejected, and to the end when one was -- the
   owner's rule. A write the rules refuse by the time it is decided -- they
   changed while it waited -- is answered as not proposed, recorded as
   `refused`, and does not end the run.
7. **State version 2** adds `write_decisions: dict[str, str]`, by call id.
   - `start_run` resets it to `{}`.
   - `review_writes` writes it whole, the channel being last-value.
   - The version moves with the field, pinned in the test.
   - No v1 checkpoint can be paused at a node that reads it, so no
     migration is needed (Risks).
8. **The write tools** -- `infrastructure/agents/tools/add_task.py`,
   `close_task.py` and `reassign_task.py` -- are proposals only.
   - Their function raises `RuntimeError`.
   - Their manifest declares `write`, idempotent, audit event `task_writes`.
   - `metadata["write"]` is the domain builder that turns checked arguments
     into a write.
9. **The factory takes the writer**: `build_assistant(model, tools, *,
   transient, initial_delay, writer=None)`.
   - Refused when the graph is composed (TOOLS-MANIFEST):
     - a write tool given without a writer;
     - a write manifest that is not idempotent, or names no audit event;
     - a write tool with no builder in `metadata["write"]`.
   - The registry passes `store.writer()`.
   - Reads are built over `store.reader(...)`, never the store (4b1's
     finding 4): `read_tools(reader)` and `write_tools()`.
10. **Prompt version 2** names the five tools and says each write waits for
    the owner's approval. Its digest is pinned.
11. **Browsers: only `http://localhost:3000`.** LangGraph's server allows
    every origin by default, so a page in the owner's browser could read a
    paused run and approve it (finding 2). The owner chose, 2026-10-15, to
    allow only Agent Chat UI's default origin.
    - `scripts/serve.sh` starts the server with `CORS_ALLOW_ORIGINS` set to
      that origin, on the `exec` line, outside the local-only environment's
      `export`s, which the method holds equal to the session's settings.
      It unsets `CORS_CONFIG`, which would replace it, and refuses a
      `langgraph.json` holding a `"cors"` key.
    - The SDK is not a browser, and is unaffected.
12. **A request guard in front of every route** (pass 2's BLOCKER). CORS
    limits what a page may read, never what it may send: a `text/plain`
    POST is sent without a preflight, and the server parses its body as
    JSON whatever its type -- so a page could create a thread, propose and
    approve a write without reading a byte. The owner chose, 2026-10-15,
    the guard.
    - The policy is the domain's `request_refusal` (`domain/access.py`):
      a `Host` that is not this machine is refused (DNS rebinding); a
      request other than `GET`, `HEAD` or `OPTIONS` is refused when its
      `Origin` is another page's, or the body it sends, for `POST`, `PUT`
      or `PATCH`, is not `application/json` -- which a browser cannot send
      to another origin without a preflight CORS refuses. A request with no
      body passes the media-type rule: the SDK's `runs.cancel` and
      `threads.copy` send none, and a page's empty POST still carries its
      `Origin` (pass 3).
    - **A WebSocket is never "safe"** (pass 3's BLOCKER). The server's v2
      event stream, on by default in `langgraph-api` 0.16, serves
      `/threads/{id}/stream/events` as a WebSocket that starts and resumes
      runs; CORS never applies to one, and its handshake is a GET. A
      handshake is refused for the `Host` and for any `Origin` but
      `http://localhost:3000` -- closed before it is accepted, so the server
      answers 403. Measured in-process before the fix: a page's socket read
      the approval request and approved it.
    - **Fail closed.** The adapter lets through the server's lifespan, and
      HTTP and WebSockets it has checked; any other kind of connection
      reaches nothing.
    - **The development server's own routes are not served** (pass 4):
      `/deploy` runs a LangSmith deployment from the repository -- ADR 0004
      forbids one, and a deny rule on the command's text cannot see a POST --
      and `/internal/truncate` wipes every thread, paused approvals with them.
      Nothing here uses either.
    - The adapter is `LocalRequestGuard`, ASGI middleware in
      `infrastructure/server/guard.py`, named in `langgraph.json` as
      `http.app`; the server runs it before CORS and every route
      (`langgraph_api/server.py`, with no `middleware_order` set). Its own
      test drives it with hand-built scopes, every row of the policy's
      tables; the live tests send the same through `serve.sh`.
    - `starlette` is the server's, which arrives with `langgraph-cli[inmem]`
      in the dev group: the guard is a server module, and the server is
      dev-only (ADR 0004).
    - `http.app` is the one key of `langgraph.json` beside `graphs` and
      `python_version` that names code; a test pins the `http` block whole,
      so a `middleware_order`, `cors` or `disable_*` key fails it.
    - Alternatives: LangGraph's custom `auth` with a local token -- every
      client, Agent Chat UI included, would need the token; refusing state
      writes alone -- leaves the propose-then-approve path open.

## Orchestration design

| Node (a business outcome) | Kind (read, decide, write) | Reads | Writes or side effect | Routes to | Decided by (domain policy or model) |
|---|---|---|---|---|---|
| `start_run` | read | `messages`, the store's records | counts 0; `write_decisions` `{}`; calls an earlier run left answered as not run, or a write with the outcome recorded under its key | `call_model` | `unanswered_calls` |
| `call_model` | decide | `messages`, `model_calls` | the reply, within the budgets | `run_tools`, `END` | `route_after_reply` |
| `run_tools` | read | the reply, `tool_calls` | reads and malformed calls answered; write calls checked, refused ones answered | `review_writes`, `call_model` | `route_after_tools` |
| `review_writes` | decide | every waiting write call | `interrupt()`; on resume, `write_decisions` | `apply_writes` | the owner (`read_decisions`) |
| `apply_writes` | write | the next waiting write call, `write_decisions` | it applied or rejected by the writer, once per key, and answered from the outcome | `apply_writes`, `call_model`, `END` | `route_after_writes` |

- **State:** `AssistantState` v2: `messages`, `model_calls`, `tool_calls`,
  `write_decisions`.
- **Identity:** the thread id is the server's. There is no owner check yet:
  one owner on 127.0.0.1. Slice 5 adds ownership.
- **Budgets:** as before. Writes count as tool calls. An interrupt spends
  no model call.
- **Errors:**
  - a refused proposal: answered, the run goes on;
  - a refused write after approval: answered with its reason, the run goes
    on;
  - a rejection: answered, the run ends;
  - the store's error at apply: raised. The writes before it are answered
    and stored, and the thread stays at `apply_writes`: a continue re-runs
    the failed one under its key; new input answers it as not run;
  - the store's error in `start_run`, reading a left write's record: raised,
    the thread left at `start_run` with the input stored -- answering "not
    run" unread could deny a write that was made;
  - the store's error in `review_writes`, reading a task for its
    description: raised before the interrupt, the thread at `review_writes`;
    a continue asks again;
  - a key too long, or no thread: the proposal refused.
- **Interrupts:** `review_writes` only; resumed on the same thread with
  `Command(resume=...)`.
- **Tools:** reads hold a reader; writes hold nothing and are applied by
  the writer the factory is given.
- **Streaming:** the server streams the interrupt as LangGraph does. A
  client reads it from the thread's state, or from the run's stream.
- **Persistence:** the local server's in-memory checkpointer. A pause lasts
  as long as that server's thread (slice 5).
- **Observability:** each decision is a row in `task_writes`. Logs are
  slice 6.
- **Runtime:** `scripts/serve.sh`. The story test drives it through the
  SDK: run, read the interrupt, resume.
- **Test plan:**
  - unit: `route_after_tools`, `route_after_writes`, `request_refusal`;
    `describe_write`, `read_decisions`, `write_key` and `outcome_message`
    are proved through the graph, at integration, since each requirement
    is the graph's behaviour -- the request's shape, the resume's meaning,
    the key in the store (pass 3: the plan said unit);
  - integration: the routes with fakes and an in-memory checkpointer
    (`test_approval.py`), each on `invoke` and on `ainvoke` -- the server
    runs the async path (pass 3); the topology and state; the request
    guard;
  - acceptance (live): the server.
- **Graph id:** `assistant`.

### Routes -- the ladder's checklist

| Route | Requirement, or N-A |
|---|---|
| completion | ASSISTANT-TOOL-LOOP; ASSISTANT-WRITE-DECISIONS (all approved) |
| refusal | ASSISTANT-WRITE-PROPOSAL (a proposal the rules refuse) |
| approval, rejection | ASSISTANT-WRITE-DECISIONS |
| interruption and resume | ASSISTANT-WRITE-APPROVAL; LOCAL-SERVER-APPROVAL; new input instead: ASSISTANT-NO-CALL-LEFT-UNANSWERED |
| retry exhaustion | ASSISTANT-TRANSIENT-RETRY; a write is never retried |
| limit exhaustion | the four budgets, writes counted as tool calls |
| tool denial | ASSISTANT-TOOL-ERROR; TOOLS-MANIFEST |
| malformed model output | ASSISTANT-TOOL-ERROR |
| retrieval failure, timeout | the store's error propagates, at a read or at a write |
| forbidden access | N-A until slice 5; a page's request: LOCAL-SERVER-REQUEST-GUARD |
| a resume with nothing paused | N-A: no write can follow -- on a new thread it runs from `START` on an empty transcript; on a completed one it decides nothing (measured, pass 3) |

## Risks

- **[A v1 checkpoint meets v2]** -> a v1 thread has no `write_decisions`.
  Every run starts at `start_run`, which sets it, and no v1 thread can be
  paused at a node that reads it: v1 had no interrupt.
- **[A continue on a thread paused after a failed write]** -> `apply_writes`
  re-runs under the same keys. A write made before the failure answers what
  it recorded.
- **[A resume the owner got wrong]** -> it rejects. The safe outcome is no
  effect.
- **[A run ends after the store commits, before its answer is stored]** --
  killed, or cancelled after the commit -> the next run's `start_run`
  answers the call with the outcome recorded under its key, never "not
  run"; a continue's `apply_writes` reads the record before the rules.
- **[A run cancelled while its write waits for the list's lock]** -> the
  write's thread is not stopped by the cancel, and may commit after the
  next run's `start_run` answered it "not run" (pass 3, measured). Then the
  transcript denies a write the list holds. It needs a cancel inside the
  store's 5-second wait and new input before the commit; recording "not
  run" under the key would close it, and needs a new outcome in
  `task_writes` -- slice 5, with durable threads.
- **[A fork that edits a reply's arguments under the same ids]** -> the key
  records another write: `apply_writes` refuses it through the writer
  (TASKS-WRITE-ONCE). It reads the key's record directly only when the
  rules now refuse the call -- the answer lost, then the rules changed --
  and new input answers the call with what the key holds; neither matches
  the record to the call. Only a client that can edit state reaches it
  (accepted, finding 21's reach).
- **[Read and decide nodes hold the writer]** -> `start_run` and
  `review_writes` read through `TaskWriter.recorded` and `.task`, both
  read-only connections. A narrower view is slice 5's, with ownership.
- **[`CONFIG_KEY_CHECKPOINTER`]** -> "is there a checkpointer" is read from
  a LangGraph constant kept for backward compatibility; there is no public
  way. `langgraph<1.3` bounds it, and the no-checkpointer test fails if it
  stops being set: re-check it at every LangGraph upgrade.
- **[A client that is not a browser, and reaches the port]** -> it is the
  owner, as far as this server can tell: it can start a run and approve it
  -- over the SDK or the WebSocket -- set `write_decisions`, or swap a
  waiting call. The guard keeps every web page but Agent Chat UI's out; any
  other client that can connect to 127.0.0.1:2024 -- another account on the
  machine, a tool allowed loopback but not the task file -- can still do it.
  The approved identity line holds ("one owner on 127.0.0.1"); slice 5's
  thread ownership is where it ends.
- **[The model proposes the same write twice in two turns]** -> two
  proposals, two decisions. The key holds the reply, so each is its own
  write. That is what the owner approved.

## Migration and rollback

- **The task list:** unchanged (v2, from 4b1).
- **Threads:** the server's in-memory threads from before run on, as
  above.
- **Rollback:** revert the merge. The task list keeps its version and its
  audit rows.

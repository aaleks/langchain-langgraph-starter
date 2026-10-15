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
   - `apply_writes` is a write node. It applies or rejects each waiting
     write through the writer, and answers each call.
   - They are separate nodes, so the write sits after the interrupt in its
     own step. The step is part of the key (decision 4).
2. **`run_tools` splits the reply's calls:**
   - Reads and unknown tools go through `ToolNode`, as before. It is given a
     copy of the reply holding only those calls.
   - Write calls are checked, by the tool's schema (pydantic) and the
     domain's builder (TASKS-WRITE-VALUES). A refused one is answered then
     and there; an accepted one is left unanswered, waiting.
   - Malformed calls are answered as before.
   - The tool-call budget counts every well-formed call, writes included.

   The domain's `route_after_tools`, on the number of writes waiting, goes
   to `review_writes` or `call_model`.
3. **The approval request is LangChain's** `HITLRequest` shape, built as
   plain data. No import from `langchain.agents.middleware` is needed: the
   shape is the interface, and the test pins it.
   - `action_requests`: one per waiting call, in the reply's order -- the
     tool's name, the checked arguments, and a description from the
     domain's `describe_write`.
   - `review_configs`: one per tool named, in first-named order, each
     allowing `approve` and `reject`.

   The resume is read by the domain's `read_decisions(resume, count)`.
   - Each action gets `approve` only for an exact `{"type": "approve"}`;
     any other decision rejects it.
   - A resume that is not `{"decisions": [...]}` of the right length
     rejects every action.
4. **The key is `<thread id>:<step>:<call id>`**, from the domain's
   `write_key`, checked against `WRITE_KEY_MAX`.
   - The thread id is `config["configurable"]["thread_id"]`.
   - The step is `config["metadata"]["langgraph_step"]` in `apply_writes`.
   - A replay from the checkpoint before `apply_writes` runs the same step,
     so the same keys, so the store answers what it recorded (ADR 0008).
   - A continue after `apply_writes` failed part-way re-runs it under the
     same keys, so the writes it already made are not made again.
5. **The outcome as the model reads it is JSON**, from the domain's
   `outcome_message`:
   - `{"outcome": "applied", "task_id": 8}`, status `success`;
   - refused: the same keys plus a `reason`, status `error`;
   - rejected: the fixed sentence `REJECTED_ANSWER` in `application/prompts.py`,
     status `error`.
6. **After the writes**, the domain's `route_after_writes` on the decisions
   goes to `call_model` when all approved, and to the end when any rejected
   -- the owner's rule.
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
   - A write tool given without a writer is refused when the graph is
     composed (TOOLS-MANIFEST), as is a write manifest that is not
     idempotent or names no audit event.
   - The registry passes `store.writer()`.
   - Reads are built over `store.reader(...)`, never the store (4b1's
     finding 4): `read_tools(reader)` and `write_tools()`.
10. **Prompt version 2** names the five tools and says each write waits for
    the owner's approval. Its digest is pinned.

## Orchestration design

| Node (a business outcome) | Kind (read, decide, write) | Reads | Writes or side effect | Routes to | Decided by (domain policy or model) |
|---|---|---|---|---|---|
| `start_run` | read | `messages` | counts 0; `write_decisions` `{}`; calls an earlier run left answered as not run | `call_model` | `unanswered_calls` |
| `call_model` | decide | `messages`, `model_calls` | the reply, within the budgets | `run_tools`, `END` | `route_after_reply` |
| `run_tools` | read | the reply, `tool_calls` | reads and malformed calls answered; write calls checked, refused ones answered | `review_writes`, `call_model` | `route_after_tools` |
| `review_writes` | decide | the waiting write calls | `interrupt()`; on resume, `write_decisions` | `apply_writes` | the owner (`read_decisions`) |
| `apply_writes` | write | the waiting write calls, `write_decisions` | each applied or rejected by the writer, once per key; each answered | `call_model`, `END` | `route_after_writes` |

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
  - the store's error at apply: raised, the thread paused at
    `apply_writes`, and a continue re-runs it under the same keys;
  - a key too long: `ValueError`.
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
  - unit: `describe_write`, `read_decisions`, `write_key`,
    `route_after_tools`, `route_after_writes`, `outcome_message` -- each
    under the requirement it decides;
  - integration: the routes with fakes and an in-memory checkpointer
    (`test_approval.py`), the topology and state;
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
| forbidden access | N-A until slice 5 |

## Risks

- **[A v1 checkpoint meets v2]** -> a v1 thread has no `write_decisions`.
  Every run starts at `start_run`, which sets it, and no v1 thread can be
  paused at a node that reads it: v1 had no interrupt.
- **[A continue on a thread paused after a failed write]** -> `apply_writes`
  re-runs under the same keys. A write made before the failure answers what
  it recorded.
- **[A resume the owner got wrong]** -> it rejects. The safe outcome is no
  effect.
- **[The model proposes the same write twice in two turns]** -> two
  proposals, two decisions. The key holds the step, so each is its own
  write. That is what the owner approved.

## Migration and rollback

- **The task list:** unchanged (v2, from 4b1).
- **Threads:** the server's in-memory threads from before run on, as
  above.
- **Rollback:** revert the merge. The task list keeps its version and its
  audit rows.

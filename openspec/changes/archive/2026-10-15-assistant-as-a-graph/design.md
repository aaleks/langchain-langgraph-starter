# Design

Why: frame.md. What: the delta specs. This is how.

## Context

The assistant is `create_agent` with six middleware (`factory.py`). Each
route the living spec names is held by one of them, and some by their order:
- the malformed call, by `AnswerInvalidCalls`, listed first;
- the cut-off reply, by `OutputBudget`;
- the context budget, by `ContextBudget`;
- both call budgets and the retry, by LangChain's middleware.

4a moves every one of these into three nodes this project writes. The routes
stay the same.

## Decisions

1. **Three nodes, one effect each** -- the table below. The alternatives:
   - a node per check (`check_context`, `answer_invalid_calls`,
     `check_tool_budget`): more supersteps, nodes that change no state, and a
     table that reads like the middleware list;
   - one node for everything: no tool boundary to retry or observe.

   The checks that guard a model call run in `call_model`, before and after
   the call. The checks that guard tools run in `run_tools`, before any tool.
2. **`ToolNode` runs the tools, inside `run_tools`.** It is what
   `create_agent` used: an unknown tool and refused arguments come back as
   error tool messages, and a tool's own exception propagates. `run_tools`
   wraps it for three things it does not do:
   - the tool-call budget, checked before any call runs;
   - the count;
   - an answer to each malformed call, beside well-formed ones too.
     `create_agent` patched those into the next model call's input without
     storing them; here they are stored, so the transcript is what was sent.
3. **The retry is `call_model`'s `RetryPolicy`:**
   - `max_attempts = 1 + MODEL_RETRIES`;
   - `retry_on` = the factory's `transient` predicate;
   - `initial_interval`, `backoff_factor` and `max_interval` from the
     domain;
   - no random part: `RETRY_JITTER = False`. LangGraph's default adds up to
     a second to every wait, and `create_agent`'s added +-25% (verify pass
     1, finding 1). One local client spreads no crowd of retries, so the
     waits are 1 s, then 2 s.

   A retry re-runs the node, and the counts are written only when it
   finishes, so a retry spends no budget. That is the living rule, now held
   by construction. The budget checks run inside the retried node, so only
   the predicate keeps a budget error from being retried: each of the four
   is asserted not transient.
4. **Each node has a sync and an async body** (`RunnableLambda(func,
   afunc=...)`). The local server streams with `astream`, and a tool written
   async runs only on that path. Measured in bound-the-tool-loop: a
   sync-only hook failed there.
5. **Budgets raise domain errors.**
   - `ModelCallBudgetExceededError` and `ToolCallBudgetExceededError` live in
     `domain/agents/budgets.py`, beside the numbers they enforce, and replace
     LangChain's `ModelCallLimitExceededError` and
     `ToolCallLimitExceededError`.
   - The local server reports either as the run's error, as before.
   - A status in the state was considered (frame.md, question 1). It would
     change what a caller sees, and 4a changes no behaviour.
6. **Counts per run, reset by `start_run`.** The counts are state, so a
   checkpointer keeps them across a thread's runs. `start_run`, the first
   node of every run, sets both to zero.
   - `create_agent` kept its run count in an untracked channel instead.
     That resets on any invocation, a resume included, and 4b's resume must
     not reset the budget it pauses inside.
   - The input schema takes only `messages`, so a caller cannot hand a run
     a count.
7. **The step ceiling is 9,999**, set by the factory with
   `with_config(recursion_limit=...)`. The local server, or LangGraph's
   default (10,007, settable by an environment variable), never decides it.
   The budget needs 22 steps (measured).
8. **The routing is a domain policy** (`domain/agents/routing.py`), called
   by `routes.py`'s conditional edge from typed facts: how many well-formed
   and malformed calls the reply proposes. `keep_malformed_calls` decides,
   from their ids, whether a reply keeps its malformed calls.
9. **Layout** (`.claude/rules/langgraph/graphs.md`, "Where things go"):
   - under `infrastructure/agents/graphs/assistant/`: `state.py`,
     `graph.py` (the uncompiled builder), `nodes.py` and `routes.py`;
   - `factory.py` compiles it, the only place one is compiled, as
     `tests/architecture` requires;
   - `nodes.py` holds the three nodes in one module. Three thin nodes in
     three files would be ceremony; the rule's `nodes/<node>.py` waits
     until a node grows;
   - `middleware.py` is deleted: its checks are the nodes' now. `call_chars`
     moves to `nodes.py`, and the measurement script imports it from there.
10. **A run starts with every call answered** (ASSISTANT-NO-CALL-LEFT-
    UNANSWERED, verify pass 1, finding 2). A run that ends between a reply
    and its tools -- a tool's exception, the tool-call budget -- leaves the
    reply's calls unanswered on the thread, and a real endpoint refuses that
    transcript on every later turn. `start_run` answers each such call as not
    run, right after its reply.
    - Each answer must follow its reply, so the transcript is written again
      in order (`RemoveMessage(REMOVE_ALL_MESSAGES)`, then every message, the
      ids kept). This happens only when a call was left.
    - The alternatives: answering the calls before raising cannot be stored,
      since a node that raises writes nothing; stripping the calls from the
      reply hides from the model what it asked for.
    - The bug was in the old loop too. It is fixed here because 4b makes it
      common: new input on a thread paused for approval drops the pending
      tools the same way.
    - A call is answered only by a tool message right after its reply -- the
      endpoint's own check -- so a backend that uses an id again in a later
      turn is answered too (verify pass 2).
    - Scope: a run that starts from input. A continue without input resumes
      the stopped run at `run_tools`, whose tools run again -- safe while
      every tool reads; 4b's write node must not repeat its effect. An
      owner who edits the thread's state and then continues goes past
      `start_run`, as with the counts (Risks).
    - What a client sees: on the rare run that rewrites, `start_run`'s update
      streams the whole transcript after a `remove` marker, and the
      checkpoint holds it once more. No client here reads updates
      incrementally; a UI that does would show the history twice.
11. **A reply whose id the transcript already holds is appended under a new
    one** (verify pass 1, finding 8). `add_messages` would otherwise replace
    the earlier message where it stands, and the route reads the last
    message.
12. **The node names are deliberate.** `start_run`, `call_model` and
    `run_tools` are LangGraph's common vocabulary for a tool loop, and they
    name what each node does for the run. They become an interface with
    slice 5's durable checkpoints, and changing one after that needs a
    migration.

## Orchestration design

| Node (a business outcome) | Kind (read, decide, write) | Reads | Writes or side effect | Routes to | Decided by (domain policy or model) |
|---|---|---|---|---|---|
| `start_run` | read -- it computes, with no effect outside the state | `messages` | `model_calls = 0`, `tool_calls = 0`; each call an earlier run left unanswered, answered as not run | `call_model` | `unanswered_calls` |
| `call_model` | decide | `messages`, `model_calls` | refuses past `MODEL_CALLS_PER_RUN` or `CONTEXT_CHARS_PER_CALL`; sends `ASSISTANT_PROMPT` and the messages; refuses a cut-off reply; appends the reply -- without its malformed calls unless `keep_malformed_calls`; `model_calls + 1` | `run_tools` or `END` | `route_after_reply`, on the model's reply |
| `run_tools` | read | the last reply, `tool_calls` | refuses past `TOOL_CALLS_PER_RUN`; runs the well-formed calls through `ToolNode`; answers each malformed call with the fixed error; `tool_calls + n` | `call_model` | fixed |

- **State:** `AssistantState`, `ASSISTANT_STATE_VERSION = 1`:
  - `messages`: LangChain messages, `add_messages`;
  - `model_calls: int`, `tool_calls: int`.

  It is serialisable by the checkpointer's serializer, and holds no client,
  prompt or callable. The input and output schemas are `messages` only. The
  version is pinned beside the fields in a test, so a field changed without
  a new version fails the suite. The first migration is slice 5's, with the
  first durable checkpoint.
- **Identity:** N-A until 4b and slice 5. The local server's own threads,
  in memory; no owner check exists to change.
- **Budgets:**
  - model turns, 10: `ModelCallBudgetExceededError`;
  - tool calls, 20: `ToolCallBudgetExceededError`;
  - context, 150,000 characters: `ContextBudgetExceededError`;
  - output, 4,096 tokens: `OutputBudgetExceededError`;
  - retries, 2 a turn: the last failure, raised;
  - steps, 9,999: `GraphRecursionError`, never reached first.
- **Errors:**
  - transient: retried by `call_model`'s policy, then raised;
  - model-recoverable (unknown tool, refused or malformed arguments): an
    error tool message, and the loop goes on;
  - policy (each budget): raised;
  - unexpected (a tool's or the model's own exception): raised unchanged.
- **Interrupts:** none in 4a. 4b's approval node goes between `call_model`
  and the write.
- **Tools:** unchanged: read-only, each manifest checked by the factory
  before compiling (TOOLS-MANIFEST).
- **Streaming:** the server streams `call_model`'s model tokens as it did
  `create_agent`'s model node's. Calls carrying tools are not streamed by the
  client (MODEL-OPENWEBUI-CLIENT).
- **Persistence:** none of the project's own. The local server's in-memory
  checkpointer, as today.
- **Observability:** unchanged; slice 6.
- **Runtime:** unchanged -- `scripts/serve.sh`, the registry, `langgraph.json`.
- **Test plan:**
  - unit: `route_after_reply`, `keep_malformed_calls`. The budget checks are
    proved through the graph, where each limit is a scenario of its own (verify
    pass 1, finding 14);
  - integration: the topology and the state contract
    (`test_assistant_graph.py`); every route of the living spec through the
    factory, unchanged in what it asserts but the error classes
    (`test_assistant.py`);
  - acceptance: the registered graph, offline and through the stand-in;
  - live: the local server and the owner's Open WebUI, `check.sh live`.
- **Graph id:** `assistant`, unchanged.

### Routes -- the ladder's checklist

| Route | Requirement, or N-A |
|---|---|
| completion | ASSISTANT-TOOL-LOOP |
| refusal | N-A: no request policy declines a question; the prompt tells the model what it cannot do (ASSISTANT-PROMPT) |
| approval, rejection | N-A until 4b |
| interruption and resume | N-A until 4b; ASSISTANT-NO-CALL-LEFT-UNANSWERED keeps a thread usable after a run stops |
| retry exhaustion | ASSISTANT-TRANSIENT-RETRY |
| limit exhaustion | ASSISTANT-MODEL-CALL-BUDGET, ASSISTANT-TOOL-CALL-BUDGET, ASSISTANT-CONTEXT-BUDGET, ASSISTANT-OUTPUT-BUDGET |
| tool denial | ASSISTANT-TOOL-ERROR (a tool not given, refused arguments), TOOLS-MANIFEST (a manifest refused at compose). Denial by authorisation: N-A, one owner and no write |
| malformed model output | ASSISTANT-TOOL-ERROR |
| retrieval failure, timeout | the model: ASSISTANT-TRANSIENT-RETRY. The task store: ASSISTANT-ERRORS-PROPAGATE -- a tool's exception, the store's `sqlite3.Error` among them (its manifest), ends the run unchanged |
| forbidden access | N-A until slice 5: one owner, one local server |

## Risks

- **[Behaviour drifts in a route no test names]** -> every test of the
  living spec runs unchanged against the new graph but the two error
  classes. They are the evidence that the behaviour held. Mutations of the
  new code prove those tests can fail.
- **[The server's async path differs]** -> each node has an async body, and
  the async tests stay (context budget, malformed call). `check.sh live`
  runs the server.
- **[A thread from the old graph meets the new one]** -> the local server
  saves its threads to `.langgraph_api/`, so an old thread can outlive a
  restart. Its state holds `messages`, which both graphs share. A new run on
  it starts at `start_run`, which sets the counts the old state lacks. No
  thread can be paused mid-run, since neither graph has an interrupt.
  Checked once with a throwaway script, not a test: a thread written by
  `create_agent` (channels `messages`, `thread_model_call_count`) ran on
  under the new graph -- its transcript kept, the new run counted from 0.
  Deleting `.langgraph_api/` drops them all. Nothing else stores a thread.
  A thread the old graph left stopped mid-run (`next` names a node that no
  longer exists) does nothing on a continue (verify pass 1, finding 16).
  **The policy:** delete `.langgraph_api/` when upgrading across this change.
- **[A thread outgrows the context budget]** -> the transcript is never cut.
  Once it passes 150,000 characters, every run on the thread ends with
  `ContextBudgetExceededError`, before calling the model, and each superstep
  checkpoints the whole transcript again. It was so before this change. The
  owner chose, 2026-10-14 ("Defer to slice 5 (Recommended)"), to leave it to
  slice 5's retention and size budget. Until then: a new thread.
- **[A caller sets the counts]** -> the local server's state-update endpoint
  can write `model_calls` and `tool_calls` between runs, past the input
  schema. Accepted: its caller is the owner, on 127.0.0.1, who can start
  any number of runs anyway. Slice 5's thread ownership revisits it.
- **[The state version is not in a checkpoint]** -> `ASSISTANT_STATE_VERSION`
  is pinned in a test with the fields, their being required and the
  compiled channels. Stamping it on each checkpoint, so a migration can
  read it, is slice 5's, with the first durable one.

## Migration and rollback

**No data migrates.** The task list is untouched. A thread the server saved
under the old graph runs on under the new one (Risks). A client that matched `ModelCallLimitExceededError` or
`ToolCallLimitExceededError` by name -- none in this repository but the
tests -- sees the domain's names instead.

**Rollback** is reverting the merge: the factory's body, `middleware.py` and
the tests return together.

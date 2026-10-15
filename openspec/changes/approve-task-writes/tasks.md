# Sequence

- **Order:**
  1. The domain policies.
  2. The write tools and their manifests.
  3. The state and the topology.
  4. The proposal.
  5. The approval.
  6. The decisions.
  7. The key.
  8. The prompt.
  9. Registration.
  10. The server, end to end.
- **Wiring point:** `src/starter/infrastructure/agents/factory.py` and
  `registry.py`.
- **Story test:**
  `tests/acceptance/agents/test_local_server.py::TestApprovalThroughTheServer`
  -- `live`. It stays red until the registry passes the writer and the graph
  pauses.

## 1. The story test

- [x] 1.1 /accept -- `TestApprovalThroughTheServer`, red: the run completed, no
  `add_task` to pause on

## 2. TOOLS-TASK-WRITES, TOOLS-MANIFEST (modified)

- [x] 2.1 /accept -- `TestTaskWriteTools`; the manifest rows
- [x] 2.2 /tdd -- `add_task.py`, `close_task.py`, `reassign_task.py`;
  `check_capability` takes writes; reads built over a reader

## 3. ASSISTANT-STATE-CONTRACT, ASSISTANT-GRAPH-TOPOLOGY, ASSISTANT-ROUTING (modified)

- [x] 3.1 /accept -- the version, the table, the policies' rows
- [x] 3.2 /tdd -- state v2, the two nodes, `route_after_tools`, `route_after_writes`

## 4. ASSISTANT-WRITE-PROPOSAL

- [x] 4.1 /accept -- `TestWriteProposal`
- [x] 4.2 /tdd -- `run_tools` checks write calls

## 5. ASSISTANT-WRITE-APPROVAL

- [x] 5.1 /accept -- `TestWriteApproval`
- [x] 5.2 /tdd -- `review_writes`, `describe_write`

## 6. ASSISTANT-WRITE-DECISIONS

- [x] 6.1 /accept -- `TestWriteDecisions`
- [x] 6.2 /tdd -- `apply_writes`, `read_decisions`, `outcome_message`

## 7. ASSISTANT-WRITE-KEY

- [x] 7.1 /accept -- `TestWriteKey`. Red after the code was written: the
  replay applied the write twice -- the superstep differs on replay (5, then
  6, measured). The key is the reply's id instead; spec, design and ADRs
  amended
- [x] 7.2 /tdd -- `write_key(thread, reply, call)`

## 8. ASSISTANT-PROMPT (modified), ASSISTANT-UNTRUSTED-TASK-TEXT, ASSISTANT-NO-CALL-LEFT-UNANSWERED (rows)

- [x] 8.1 Prompt v2 and its digest; the adversarial row; the new-input row

## 9. ASSISTANT-REGISTERED (modified), the story test green

- [x] 9.1 The registry passes the writer; five tools offered
- [x] 9.2 The story test green through `scripts/serve.sh`. Measured on the
  way: the server ends a run stopped at an interrupt `success`; the pause is
  the thread's status, `interrupted`. The scenario said the run's: amended

## 10. Close

- [x] 10.1 Mutations of the new code, 19, each red once three survivors were
  closed with rows: a reader's wait other than its manifest; one review config
  per tool; writes spending the tool-call budget
- [x] 10.2 Documents: CLAUDE.md, the roadmap, the measurement script

## 11. Verify pass 1 -- the fixes

- [x] 11.1 Each well-formed call of a reply under an id of its own
  (`calls_to_rename`); the owner's `reject, approve` on two writes once under
  one id now rejects the one and applies the other
- [x] 11.2 One write a step, answered and routed from the outcome the store
  recorded; a failure part-way then new input; a replay deciding otherwise;
  rules changed while a write waited
- [x] 11.3 The task's title and status in the description, quoted as JSON;
  strict schema; the key a JSON array, checked with the proposal; no thread,
  no proposal; a write without a builder refused
- [x] 11.4 Browsers: `CORS_ALLOW_ORIGINS=http://localhost:3000`, the owner's
  choice -- `TestBrowserOrigins`, live preflights from three origins
- [x] 11.5 Test gaps closed: NO-CALL row 4, the write tools' defaults and
  every direct call, the registered graph's write reaching `TASKS_DB`, the
  replay re-running, the read beside a write succeeding
- [x] 11.6 Mutations of the fixes, 18, each red -- one, at first an error
  rather than a red, closed with the changed-rules scenario

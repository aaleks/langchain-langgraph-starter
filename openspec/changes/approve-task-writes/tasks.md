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

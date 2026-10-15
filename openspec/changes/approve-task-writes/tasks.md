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

- [ ] 1.1 /accept -- `TestApprovalThroughTheServer`, red

## 2. TOOLS-TASK-WRITES, TOOLS-MANIFEST (modified)

- [ ] 2.1 /accept -- `TestTaskWriteTools`; the manifest rows
- [ ] 2.2 /tdd -- `add_task.py`, `close_task.py`, `reassign_task.py`;
  `check_capability` takes writes; reads built over a reader

## 3. ASSISTANT-STATE-CONTRACT, ASSISTANT-GRAPH-TOPOLOGY, ASSISTANT-ROUTING (modified)

- [ ] 3.1 /accept -- the version, the table, the policies' rows
- [ ] 3.2 /tdd -- state v2, the two nodes, `route_after_tools`, `route_after_writes`

## 4. ASSISTANT-WRITE-PROPOSAL

- [ ] 4.1 /accept -- `TestWriteProposal`
- [ ] 4.2 /tdd -- `run_tools` checks write calls

## 5. ASSISTANT-WRITE-APPROVAL

- [ ] 5.1 /accept -- `TestWriteApproval`
- [ ] 5.2 /tdd -- `review_writes`, `describe_write`

## 6. ASSISTANT-WRITE-DECISIONS

- [ ] 6.1 /accept -- `TestWriteDecisions`
- [ ] 6.2 /tdd -- `apply_writes`, `read_decisions`, `outcome_message`

## 7. ASSISTANT-WRITE-KEY

- [ ] 7.1 /accept -- `TestWriteKey`
- [ ] 7.2 /tdd -- `write_key`

## 8. ASSISTANT-PROMPT (modified), ASSISTANT-UNTRUSTED-TASK-TEXT, ASSISTANT-NO-CALL-LEFT-UNANSWERED (rows)

- [ ] 8.1 Prompt v2 and its digest; the adversarial row; the new-input row

## 9. ASSISTANT-REGISTERED (modified), the story test green

- [ ] 9.1 The registry passes the writer; five tools offered
- [ ] 9.2 `bash scripts/check.sh live` -- the story test green

## 10. Close

- [ ] 10.1 Mutations of the new code, each red
- [ ] 10.2 Documents: CLAUDE.md, the roadmap, the measurement script

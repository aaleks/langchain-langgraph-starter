## ADDED Requirements

### Requirement: LOCAL-SERVER-APPROVAL
Through the local server's API (`bash scripts/serve.sh`), a run whose model proposes a write SHALL pause with the approval request (ASSISTANT-WRITE-APPROVAL) -- the thread's status `interrupted`, its state showing the interrupt, the task list unchanged; the run itself ends `success`, as the server reports a run stopped at an interrupt (measured); a run on the same thread with `command={"resume": {"decisions": [{"type": "approve"}]}}` SHALL apply the write and complete, and with `{"type": "reject"}` SHALL end with nothing written.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestApprovalThroughTheServer`

#### Scenario: Approved through the server
- **GIVEN** the server, Open WebUI configured as a stand-in on 127.0.0.1 that proposes `add_task(title="Call the plumber")`, then answers
- **WHEN** a client runs `assistant` on a new thread with `add the plumber`
- **THEN** the thread's status is `interrupted`, its interrupt carries one action request, `add_task`, and the task list holds no task
- **AND** resumed on that thread with an approval, the thread's status is `idle`, both runs `success`, and the list holds `Call the plumber`

#### Scenario: Counter-example -- rejected through the server
- **WHEN** the same, resumed with a rejection
- **THEN** the thread's status is `idle`, its last message the rejection's tool message, and the list holds no task of that thread's

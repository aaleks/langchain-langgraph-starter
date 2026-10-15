## ADDED Requirements

### Requirement: LOCAL-SERVER-APPROVAL
Through the local server's API (`bash scripts/serve.sh`), a run whose model proposes a write SHALL pause with the approval request (ASSISTANT-WRITE-APPROVAL), the thread's state showing the interrupt and the task list unchanged; a run on the same thread with `command={"resume": {"decisions": [{"type": "approve"}]}}` SHALL apply the write and complete, and with `{"type": "reject"}` SHALL end with nothing written.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestApprovalThroughTheServer`

#### Scenario: Approved through the server
- **GIVEN** the server, Open WebUI configured as a stand-in on 127.0.0.1 that proposes `add_task(title="Call the plumber")`, then answers
- **WHEN** a client runs `assistant` on a new thread with `add the plumber`
- **THEN** the run's status is `interrupted`, the thread's interrupt carries one action request, `add_task`, and the task list holds no task
- **AND** resumed on that thread with an approval, the run's status is `success`, and the list holds `Call the plumber`

#### Scenario: Counter-example -- rejected through the server
- **WHEN** the same, resumed with a rejection
- **THEN** the run's status is `success`, its last message the rejection's tool message, and the list holds no task

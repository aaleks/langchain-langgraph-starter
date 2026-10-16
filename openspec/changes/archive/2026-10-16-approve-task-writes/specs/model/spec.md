## MODIFIED Requirements

### Requirement: MODEL-OPENWEBUI-LIVE
With Open WebUI configured in `.env`, a run of the registered assistant SHALL be answered by that Open WebUI model: a transcript that begins with the human message and ends with a model answer calling no tool, every tool call on the way answered, nothing written to the task list, and an answer that is not empty and is not the offline model's. A real model may read the task list before it answers -- measured 2026-10-15, two runs of three called `list_tasks` on `Reply with one word.` -- so the route between is the model's, never asserted.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_openwebui_live.py::TestAnsweredByOpenWebUI`

#### Scenario: A real answer
- **GIVEN** `.env` configuring an Open WebUI that is running
- **WHEN** the registered assistant runs on the human message `Reply with one word.`
- **THEN** the first message is that human message, the last is a model answer calling no tool, every tool call has its answer, the answer is not empty, and it is not the offline model's fixed answer
- **AND** the task list it ran against holds no task

#### Scenario: Counter-example -- not configured, not run
- **GIVEN** a `.env` that does not configure Open WebUI
- **THEN** the test is skipped, saying so -- never passed

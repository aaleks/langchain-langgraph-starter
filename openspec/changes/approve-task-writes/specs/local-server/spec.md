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

### Requirement: LOCAL-SERVER-REQUEST-GUARD
The local server SHALL refuse with 403, before any route sees it, a request the domain policy `request_refusal` refuses: one whose `Host` is not this machine -- `127.0.0.1`, `localhost` or `[::1]`, any port -- whatever its method; and one other than `GET`, `HEAD` or `OPTIONS` whose `Origin` is present and not `http://localhost:3000`, or whose body, for `POST`, `PUT` or `PATCH`, is not `application/json`. CORS limits what a page may read; this refuses what a page may send.

- **Kind:** deterministic
- **Proved by:** `tests/unit/domain/test_access.py::TestRequestGuard`

#### Scenario: Requests refused
| Method | Host | Origin | Content-Type | Refused |
|---|---|---|---|---|
| `POST` | `127.0.0.1:2024` | `https://evil.example` | `text/plain` | yes: the origin |
| `POST` | `127.0.0.1:2024` | `https://evil.example` | `application/json` | yes: the origin |
| `POST` | `127.0.0.1:2024` | none | `text/plain;charset=UTF-8` | yes: the body |
| `DELETE` | `127.0.0.1:2024` | `null` | none | yes: the origin |
| `GET` | `evil.example:2024` | none | none | yes: the host |
| `POST` | none | none | `application/json` | yes: the host |

#### Scenario: Counter-example -- requests let through
| Method | Host | Origin | Content-Type |
|---|---|---|---|
| `POST` | `127.0.0.1:2024` | none -- the SDK | `application/json` |
| `POST` | `localhost:2024` | `http://localhost:3000` | `application/json; charset=utf-8` |
| `GET` | `[::1]:2024` | `https://evil.example` -- CORS keeps the answer from it | none |
| `OPTIONS` | `127.0.0.1:2024` | `https://evil.example` -- CORS refuses the preflight | none |
| `DELETE` | `localhost` | none | none |

### Requirement: LOCAL-SERVER-BROWSER-ORIGINS
`bash scripts/serve.sh` SHALL let a web page use the server only from `http://localhost:3000`, Agent Chat UI's default origin -- the owner's choice (2026-10-15): a preflight from any other origin SHALL get no CORS permission, and a request that would change anything from any other origin SHALL be refused before it reaches a route (LOCAL-SERVER-REQUEST-GUARD) -- a `text/plain` POST a browser sends without a preflight included -- so no other page in the owner's browser can read a paused run or approve a write. A client that is not a browser -- the SDK -- is unaffected.

- **Kind:** deterministic
- **Proved by:** `tests/acceptance/agents/test_local_server.py::TestBrowserOrigins`

#### Scenario: A browser's preflight
| `Origin` of a preflight to `/threads` | `Access-Control-Allow-Origin` in the answer |
|---|---|
| `http://localhost:3000` | `http://localhost:3000` |
| `https://evil.example` | none |
| `http://localhost:8080` | none |

#### Scenario: A page's blind write
| Sent to `/threads` | Answer | Threads afterwards |
|---|---|---|
| a POST from `https://evil.example`, its body `text/plain` | 403 | none created |
| a POST with the `Host` `evil.example` -- a rebound name | 403 | none created |
| a POST from the SDK, `application/json`, no `Origin` | 200 | one created |

#### Scenario: Counter-example -- set by the script, not by chance
- **THEN** `scripts/serve.sh` starts the server with `CORS_ALLOW_ORIGINS` exactly `http://localhost:3000`, and outside the local-only environment's `export` lines
- **AND** it unsets `CORS_CONFIG`, which would replace it, and refuses a `langgraph.json` holding a `"cors"` key
- **AND** `langgraph.json` names the request guard as its `http.app`


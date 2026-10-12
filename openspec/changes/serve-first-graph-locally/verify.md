# Verify

- **Verdict:** SHIP -- after three passes. Pass 1: DO NOT SHIP (one BLOCKER,
  four MAJOR). Pass 2: no BLOCKER, no MAJOR. Pass 3: the MINOR fixes, nothing new.
- **Reviewed at:** `edba5f3` -- pass 3. Pass 1 reviewed `c8f8401`; pass 2 the
  fix diff `ba5eae8..2dfe19f`.
- **Evidence (pass 3):** `bash scripts/check.sh live` at `edba5f3`: all checks
  passed -- architecture 48, `openspec validate --all --strict` 2 passed,
  `sdd check` OK, method 117 OK, suite 69, live 7. **Evidence (pass 1):** at
  `c8f8401`, all checks passed -- architecture 46, method 117 OK, suite 66,
  live 6; three mutations red (tasks.md). Two fresh-context lenses over
  `main..c8f8401`: proof (`spec-compliance`) and defects (`code-reviewer`); both
  re-ran the live tests (6 passed) and left no server running.

## Findings

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | BLOCKER | proof, defects | The "hostile shell" is the suite's sealed environment plus three overrides: `serve.sh` receives the LangSmith endpoint at `127.0.0.1:9`, analytics and the version check already off. Delete `serve.sh`'s exports and both live tests stay green -- the requirement's premise is never tested | `tests/localserver.py:73-78` | Remove every `LOCAL_ONLY` key from the child's environment; hostile values for the LangSmith switches, keys and endpoint (a `.invalid` name, so a regression is recorded, never delivered); prove red against a `serve.sh` without its LangSmith exports |
| 2 | MAJOR | proof, defects | On Windows `taskkill /T /F` kills the tree outright: no lifespan shutdown, no exit-time flush -- "whatever the server would send at exit is recorded" is untested where the change was measured | `tests/localserver.py:126-131` | Stop gracefully first (`CTRL_BREAK_EVENT`; uvicorn handles `SIGBREAK`), fall back to `taskkill`; the probe records an `exit`, and the test asserts the server wrote one |
| 3 | MAJOR | defects | `shutil.which("bash")` finds WSL's `System32\bash.exe` from a fresh PowerShell PATH on this machine: serve.sh would run in WSL, without the probe's variables, on a CRLF checkout | `tests/localserver.py:64` | On Windows, Git for Windows' bash, found beside `git`; refuse System32 and WindowsApps bash |
| 4 | MAJOR | defects, proof | The test servers use the developer's `.langgraph_api/` (two at once): a developer's own assistant for `assistant` breaks "exactly one", and test threads land in their store. The design's "one server for both" is two | `test_local_server.py:54,71` | One module-scoped server for both classes, in a throwaway working copy |
| 5 | MINOR | proof | The traced-run test does not assert the probe loaded; alone, with a broken probe, it passes | `test_local_server.py:156-160` | Assert it in the fixture |
| 6 | MINOR | proof | The counter-example never exercises the connect branch; `LOCAL_HOSTS` holds `None`, which the spec does not list | `test_local_server.py:19,162-172` | A non-local connect in the counter-example; `None` named in the spec |
| 7 | MINOR | proof, defects | The probe's blind spots are wider than written: native code (grpcio's C core), non-Python processes (`uv`), and the `gethostbyname`/`getnameinfo`/`sendto` events it does not hook | `probe/sitecustomize.py` | Hook the extra events; document the native and non-Python gap |
| 8 | MINOR | defects | A connect to `127.0.0.1:9` -- serve.sh's dead LangSmith endpoint, the sign tracing came back on -- counts as local | `test_local_server.py` | Assert no connect to that endpoint |
| 9 | MINOR | proof | `.env` loading's destination is only in intake.md; the roadmap still lists both deferred items under 1b, and its fifth item and first item are neither kept nor deferred | `docs/roadmap.md` | Update the roadmap in this change |
| 10 | MINOR | defects | A stop that times out kills only the leader (SIGKILL to uv; `taskkill` failures silent) | `tests/localserver.py:127-141` | Kill the group; check `taskkill`'s exit code |
| 11 | MINOR | defects | The `/ok` poll goes through a configured proxy | `tests/localserver.py:113` | An opener with no proxy |
| 12 | MINOR | defects | A hard kill of pytest orphans the server (no job object, no parent-death hook) | `tests/localserver.py:86-90` | Record; a Windows job object is more machinery than a live-tier harness needs |
| 13 | MINOR | defects | The free port is released before the server binds it -- a rare, loud flake, never a false pass | `tests/localserver.py:51-54` | Record |

## Not checked

- Placement, graph-architecture and durability lenses: the change adds tests
  only -- no production code, graph, registration or state.
- The CI Linux `live` job: not run (on demand); POSIX behaviour read from code.

## Pass 2 -- the fix diff `ba5eae8..2dfe19f`

One fresh-context reviewer, proof and defects lenses together; four
throwaway harness runs in the scratchpad, 127.0.0.1 only, no process left.

- **Pass 1 resolved:** the BLOCKER (1) -- a `serve.sh` without its tracing-off
  line now records 5 connects to `127.0.0.1:9`, without its LangSmith exports
  14 lookups of the `.invalid` endpoint; nothing real is reachable. MAJORs 3
  and 4 resolved; 2 partly (below). MINORs 5-11 resolved; 12-13 accepted.
- **No BLOCKER, no MAJOR.** Seven MINOR:

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 14 | MINOR | proof | The analytics and version-check switches are not "spared": unset is their hostile state, so a regression would cost one real request each; and the method tests check the seed, not this project's `scripts/serve.sh` | `tests/localserver.py:9-12,57-59` | Keep both at their local values in the server's environment, and check `scripts/serve.sh`'s exports in the default suite |
| 15 | MINOR | defects | A CTRL_BREAK that cannot be sent (no console) raises before the `taskkill` fallback: six server processes left running, measured | `tests/localserver.py:193-196` | Catch the signal's failure and go to the kill |
| 16 | MINOR | proof | On Windows the "no connect to `127.0.0.1:9`" clause cannot see asyncio clients: a `serve.sh` that kept the credentials started the usage-report loop to `127.0.0.1:9` and the probe recorded nothing | traced-run scenario | The default-suite check of `serve.sh`'s exports catches that regression; the clause's Windows limit written |
| 17 | MINOR | proof | SIGTERM/SIGBREAK is not a person's Ctrl+C: uvicorn re-raises the signal, and only SIGINT then runs Python's normal shutdown (atexit, langsmith's non-daemon flush) | `tests/localserver.py:183-190`; `design.md` | SIGINT on POSIX; on Windows (no group-targeted CTRL_C) the gap written |
| 18 | MINOR | defects | Proxy variables reach the server; a local proxy would turn a regression into a 127.0.0.1 connect | `tests/localserver.py:128-133` | Strip them |
| 19 | MINOR | proof | "Serve on 127.0.0.1" is not proved: a server bound to 0.0.0.0 answers on 127.0.0.1 too | spec; TestServesTheAssistant | Record binds; assert every one is on this machine |
| 20 | MINOR | proof | Overclaiming text: the probe "re-runs at every upgrade" (it runs on demand); `scripts/serve.sh` still cites 0.4.32 / 0.15.1 as measured | `docs/roadmap.md`; `scripts/serve.sh:13-14` | Correct both |

**Pass 2 verdict:** shippable. The MINORs are fixed before landing, in a
separate commit, read in pass 3.

## Pass 3 -- the fix diff `5f0119b..edba5f3`

Read by the agent that wrote the fixes; not fresh-context. Every pass-2
finding, 14 to 20, is fixed: the default suite checks `scripts/serve.sh`'s
exports (a dropped export caught on a fixture); the two third-party switches
spared, the licence key and proxies removed; the stop's fallback taken when the
signal cannot be sent; SIGINT on POSIX; binds recorded and asserted on
loopback, a bind to every interface caught on a pure counter-example; the
Windows limits and the overclaiming text corrected. Nothing new found.

## Not checked -- all passes

- Placement, graph-architecture and durability lenses: the change adds tests
  only -- no production code, graph, registration or state.
- The POSIX stop (SIGINT to the session, the exit phase recorded) and the CI
  `live` job: not run -- this machine is Windows, and the job is on demand.
  Read from code; the first `live` run on Linux is its proof.
- A live mutation binding the server to every interface: not run -- it would
  expose the server and, on Windows, raise a firewall prompt. The pure
  counter-example proves the classification.
- Pass 3 is not fresh-context.

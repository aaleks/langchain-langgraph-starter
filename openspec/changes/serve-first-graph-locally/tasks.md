# Sequence

- **Order:** the harness and the probe first -- neither requirement can be
  tested without a running server. Then LOCAL-SERVER-SERVES-ASSISTANT, whose
  runs LOCAL-SERVER-STAYS-LOCAL then inspects.
- **Wiring point:** `bash scripts/serve.sh` -- the one way the server starts.
- **Story test:** `tests/acceptance/agents/test_local_server.py::TestServesTheAssistant`
  -- driven through the real entry point; it is LOCAL-SERVER-SERVES-ASSISTANT's
  own proof.

## 0. Harness

- [x] 0.1 `tests/localserver.py`: a free port, the server started through
  `serve.sh` from a hostile shell with the probe on `PYTHONPATH`, `/ok`
  awaited, the tree stopped and the port seen free -- no server left listening
  after six passing and seven failing live runs
- [x] 0.2 `tests/acceptance/agents/probe/sitecustomize.py`: the audit-hook probe

## 1. LOCAL-SERVER-SERVES-ASSISTANT

- [x] 1.1 /accept LOCAL-SERVER-SERVES-ASSISTANT -- the test is red, for the right reason:
  the behaviour exists (no production code is written here), so red was shown by
  mutation -- the graph registered as `helper`: all four tests ERROR. The first live run
  also corrected the spec: an unknown graph id is refused, `NotFoundError: Graph
  'agent' not found. Expected one of: ['assistant']`, not answered empty
- [x] 1.2 /tdd -- every scenario, counter-example included, asserted and green (`-m live`):
  `6 passed` for both classes

## 2. LOCAL-SERVER-STAYS-LOCAL

- [x] 2.1 /accept LOCAL-SERVER-STAYS-LOCAL -- the test is red, for the right reason: by
  mutation -- the registry resolving `probe-mutation.invalid` at import fails both
  live tests; the probe kept off `PYTHONPATH` fails the loaded-probe assertion
- [x] 2.2 /tdd -- every scenario, counter-example included, asserted and green (`-m live`);
  the counter-example is pure and runs in the default suite

## 3. Wiring

- [x] 3.1 The story test is green through `scripts/serve.sh` -- TestServesTheAssistant, 4 passed
- [x] 3.2 The full check passes, `bash scripts/check.sh`, and `bash scripts/check.sh live` --
  "all checks passed", exit 0: architecture 46, method 117 OK, suite 66, live 6

## 4. Verify pass 1 -- the fixes (`verify.md`, reviewed at `c8f8401`)

- [x] 4.1 A shell that is actually hostile (finding 1): every `LOCAL_ONLY`
  variable removed, LangSmith switched on with keys and a `.invalid` endpoint.
  Proved against a `serve.sh` without its LangSmith exports: 14 lookups of
  `langsmith-hostile.invalid` recorded, both stays-local tests FAILED
- [x] 4.2 Stopped as a person stops it (finding 2): CTRL_BREAK / SIGTERM to the
  group; `stopped_gracefully` asserted. Measured: the lifespan shutdown runs; the
  re-raised signal skips atexit, for a person's Ctrl+C too -- the probe's
  planned `exit` record was dropped, after it never appeared
- [x] 4.3 Git for Windows' bash, found beside `git` (finding 3); one server in a
  throwaway working copy with `UV_PROJECT` -- the repo's `.langgraph_api/`
  untouched across the runs (finding 4)
- [x] 4.4 The probe loaded asserted in both stays-local tests (5); a non-local
  connect in the counter-example, `None` in the spec (6); lookups by
  `gethostbyname`/`getnameinfo` and datagram sends hooked, native and non-Python
  gaps written (7); no connect to `127.0.0.1:9` (8); the roadmap records 1b's
  five items (9); group kill and `taskkill`'s exit code (10); no proxy on `/ok`
  (11); 12 and 13 accepted, in the design

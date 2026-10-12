# Sequence

- **Order:** the harness and the probe first -- neither requirement can be
  tested without a running server. Then LOCAL-SERVER-SERVES-ASSISTANT, whose
  runs LOCAL-SERVER-STAYS-LOCAL then inspects.
- **Wiring point:** `bash scripts/serve.sh` -- the one way the server starts.
- **Story test:** `tests/acceptance/agents/test_local_server.py::TestServesTheAssistant`
  -- driven through the real entry point; it is LOCAL-SERVER-SERVES-ASSISTANT's
  own proof.

## 0. Harness

- [ ] 0.1 `tests/localserver.py`: a free port, the server started through
  `serve.sh` from a hostile shell with the probe on `PYTHONPATH`, `/ok`
  awaited, the tree stopped and the port seen free
- [ ] 0.2 `tests/acceptance/agents/probe/sitecustomize.py`: the audit-hook probe

## 1. LOCAL-SERVER-SERVES-ASSISTANT

- [ ] 1.1 /accept LOCAL-SERVER-SERVES-ASSISTANT -- the test is red, for the right reason
- [ ] 1.2 /tdd -- every scenario, counter-example included, asserted and green (`-m live`)

## 2. LOCAL-SERVER-STAYS-LOCAL

- [ ] 2.1 /accept LOCAL-SERVER-STAYS-LOCAL -- the test is red, for the right reason
- [ ] 2.2 /tdd -- every scenario, counter-example included, asserted and green (`-m live`)

## 3. Wiring

- [ ] 3.1 The story test is green through `scripts/serve.sh`
- [ ] 3.2 The full check passes, `bash scripts/check.sh`, and `bash scripts/check.sh live`

# Intake

- **Class:** structural
- **Intent:** For a developer starting from this starter: `bash scripts/serve.sh`
  serves the registered `assistant` on 127.0.0.1, a run through the server's API
  completes and streams, a second process reads the run's thread, and the whole
  of it -- start, run, read -- makes no connection beyond this machine, even from
  a shell that exports LangSmith keys. Proved by `live` tests anyone can re-run
  at every upgrade, in place of a one-off probe.
- **Because:** it adds a flow the repository does not have -- serving a graph
  and driving it through the server's API -- and the first `live` tier. No
  existing flow is changed, so it is not bounded.
- **Approved:** under the owner's standing delegation of 2026-10-12 ("continue
  automatically with the next cycles ... only stop when you genuinely need me
  for a significant decision"). The class and the scope below were decided by
  the agent and are reported to the owner with the change.

## Scope, against the roadmap's 1b

The roadmap lists five items for 1b. Two are deferred, each to the change whose
requirement needs it -- CLAUDE.md rule 2 and ADR 0003's ladder:

- **An interrupt resumed on the same thread** -- deferred to the durability
  slice. The registered graph has no interrupt; adding one only so a smoke test
  can resume it is a rung no requirement needs. Interrupts are designed there,
  with the checkpointer and thread ownership they depend on.
- **`config/` loading `.env` without overriding** -- deferred to the first
  change that reads a setting (the first provider). Nothing reads one yet; a
  loader with nothing to load is an abstraction without a requirement.
  `scripts/serve.sh` already refuses a `.env` that would switch LangSmith on.

Kept: the graph id served; a run that streams; a second process reading the
run's state; the connection probe re-run against the pinned versions
(`langgraph-api` 0.16.0) -- as a `live` test rather than a one-off `strace`,
which this Windows machine does not have. "Every entry point starts from the
local-only environment": the method's tests already hold `scripts/serve.sh`'s
environment to the settings, and register-first-graph sealed the suite; this
change proves it end to end, on the running server.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

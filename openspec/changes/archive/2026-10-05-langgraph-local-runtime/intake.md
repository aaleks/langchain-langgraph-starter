# Intake

- **Class:** structural
- **Intent:** For anyone starting a LangGraph project from this starter or from
  `install --packs langgraph`: LangGraph runs on the developer's machine only,
  never through LangSmith. The pack also states the production-grade rules a
  graph is built and reviewed against -- folder structure, the design record,
  test tiers, error classes and persistence security -- and checks mechanically
  every rule that can be checked.
- **Because:** it changes the method's shipped interface. A pack can now seed
  files and add to the seeded settings, `scripts/serve.sh` becomes the one way
  a development server starts, and new architecture checks fail the build. It
  also records a decision that is expensive to reverse -- no hosted Studio, no
  LangSmith, no `langgraph up` -- so it gets an ADR.
- **Approved:** the user, 2026-10-05, approved closing the gaps in the gap
  analysis with one method PR ("Method PR now"). They then added the
  constraint "i want only langgraph locally never through smith.langchain.com".
  The class is the agent's, per "when in doubt, take the heavier class"; it was
  not presented for approval on its own.

## Where the requirements live

This change adds and amends the **method's own** requirements. These live in
`.claude/sdd/specs/` and are checked through `.claude/sdd/self.toml`, because
they ship with the method and are proved in every installed project by
`sdd.sh selftest`. OpenSpec's delta-and-archive flow only reaches
`openspec/specs/`, so this change sets `skip_specs: true` in `.openspec.yaml`.
The requirement diff is reviewed in the PR, beside the tests that prove it.
The project's own living spec (`openspec/specs/`) is untouched.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

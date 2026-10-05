# Intake

- **Class:** bounded
- **Intent:** For anyone building a LangGraph application from this starter:
  the langgraph pack says everything the source plan
  (`langchain-playground/langgraph-adaptation.md`, read-only) requires of a
  graph, and checks mechanically what can be checked cheaply. Routes are named
  where requirements are written; the edit guard refuses server
  configuration that would undo the local-only environment, and runtime data
  nobody should hand-edit.
- **Because:** it amends flows that already exist -- the pack's rules,
  references and auditors, two stage templates, `/discover` and `/verify` --
  and adds two edit-guard rules beside the existing ones. No new interface,
  store or graph id; nothing expensive to reverse.
- **Approved:** the user, 2026-10-05: "Only the starter ... Playground is
  source and be sure that we construct a good target starter".
  - **The approval covers** the three follow-ups proposed on 2026-10-05:
    route criteria required; the edit guard on `langgraph.json` `env`; the
    tool-manifest check required in roadmap slice 4.
  - **What re-reading the source added**, on the user's instruction to be sure
    of the target: the gaps listed in `frame.md`, each traced to a line of the
    source plan.
  - **Constraint:** the playground is never modified.

## Where the requirements live

As in `langgraph-local-runtime`, the requirements this change adds are the
method's own. They live in `.claude/sdd/specs/` and are proved by
`sdd.sh selftest`. `.openspec.yaml` declares `skip_specs`, and the requirement
diff is reviewed in the PR.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

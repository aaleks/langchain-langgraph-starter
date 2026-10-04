---
name: intake
description: "Use when someone asks for any change to this project -- a feature, a fix, a refactor, a new dependency, or a question to investigate -- before any discovery, debugging or code. Also when work under way turns out bigger than its class."
argument-hint: "<the request, in quotes>"
model: inherit
disallowed-tools: Edit, NotebookEdit
---

# /intake -- classify the work before doing it

Request: $ARGUMENTS

Every change here is an OpenSpec change. What differs between changes is which
stages they run, and that is decided now, out loud, and recorded. A stage
skipped on the record is a method; a stage skipped silently is a habit.

## 1. Classify, before the first question

| Class | Observable predicate | Stages |
|---|---|---|
| **spike** | the output is an answer, not code you keep: "can we", "is it possible", "which is faster" | intake only, ending in a verdict |
| **defect** | something behaves differently from a requirement, or from what a requirement should have forbidden | intake, /debug, frame (root cause), specs (one requirement), tasks, apply, verify, land |
| **bounded** | changes a flow that already exists in this repository: a flag, a message, one requirement amended, a refactor | intake, frame (brief), specs, tasks, apply, verify, land |
| **structural** | a new capability, subsystem or interface; or a decision expensive to reverse: data model, store, provider, embedding, public contract, graph id, state schema | the full DAG, with design.md and an ADR |

- **When two classes fit, take the heavier one.** Reaching for the lighter class to skip a stage is the doubt itself.
- **Bounded measures the repository, not your familiarity.** If no existing flow is being changed, it is not bounded.
- **Not a change at all** when no requirement, test, interface or user-visible output changes: a typo in a comment, formatting. Say so in the commit message and skip intake. A reworded user-facing message *is* a change -- messages are an interface.
- A refactor or tooling change with no behaviour change is **bounded with `skip_specs: true`**: no requirement moves, and the suite proves it.

## 2. Say it, then stop

Present the class in a few lines and wait for an explicit yes:

```
Class: bounded -- it amends PROVIDER-PRECEDENCE in openspec/specs/providers.
Intent: an unknown provider name is refused with the valid names listed.
Stages: brief frame, one MODIFIED requirement, tasks, apply, verify, land. No design.
Change id: refuse-unknown-provider
```

**A reply approves the stage actually presented** -- the class and the intent.
It does not approve requirements, a design or code that do not exist yet. Resume
at the earliest incomplete stage, never past it.

## 3. Record it

On approval:

1. `bash .claude/sdd/sdd.sh openspec new change <id>` -- kebab-case, naming the outcome.
2. Spike, or a change with no behaviour change: append `skip_specs: true` to
   `openspec/changes/<id>/.openspec.yaml`.
3. Write `openspec/changes/<id>/intake.md` from
   `openspec/schemas/sdd-proof/templates/intake.md`: Class, Intent, Because,
   Approved (who, when).

## 4. Hand off

| Class | Next |
|---|---|
| spike | Investigate as cheaply as correctness allows. Label anything built as throwaway. Record the **Verdict** -- `go`, `clarify` or `kill`, with the fact that decided it -- in intake.md, then `/land` archives the spike. A kill is a successful spike. |
| defect | `/debug` -- the root cause comes before any fix. |
| bounded, structural | `/discover`. |

## The ratchet -- it holds for the rest of the change

Hidden complexity found at any later stage upgrades the class. Stop, say "this
is now structural because ...", add a row to intake.md's Ratchet table, and
resume at the first stage the new class requires that has not run. Nothing ever
downgrades mid-change.

## Red flags

| Thought | Reality |
|---|---|
| "Too small to classify" | Classifying a small change takes one line. Skipping it is how the method's real coverage becomes unknown. |
| "Call it bounded and skip the frame" | The lighter label to avoid work is the doubt. Take the heavier class. |
| "It's obvious -- start while they read" | The gate is the approval, not the length of the message. Present, then stop. |
| "The spike works, so keep the code" | A spike's output is an answer. Keeping code is a new request: classify it. |
| "They approved the idea, so the follow-up is approved" | Each change gets its own class and its own approval. |

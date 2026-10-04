# The SDD method -- always on

This project is developed spec-first, with proof. The method is versioned in
`.claude/sdd/` -- `METHOD.md` is the reference; this file is what every session
carries. It is owned by the method; your project's own rules live in
`CLAUDE.md` and `.claude/rules/project/`.

## Four laws, at every stage

1. **Evidence before claims.** Before saying anything passes, works, is fixed or
   is done: identify the command that proves it, run it now, read the output,
   then state the result with the evidence. This covers summaries, hand-offs,
   PR text and paraphrases. A subagent's "done" is a claim -- check the diff.
2. **Approval covers the stage actually presented.** Approving an idea does not
   approve requirements, a design or code that do not exist yet. Resume at the
   earliest incomplete stage, never past it.
3. **Report findings, fix nothing,** in any stage whose job is to look:
   `/verify`, `/quality`, every auditor agent.
4. **One place holds the specification:** `openspec/specs/` is the current
   truth, `openspec/changes/` what is in flight. No spec, plan or design
   document lives anywhere else.

## Seven non-negotiables -- a violation is a BLOCKER by construction

1. Traceability holds in both directions and fails the build: every requirement
   names its proof, every test file is claimed (`bash .claude/sdd/sdd.sh check`).
2. Every requirement is `deterministic` (asserted with `==`) or `evaluated`
   (scored against an agreed threshold). No test asserts generated prose; no
   default test calls a real model.
3. Secrets and evaluation ground truth are written by a human, never by an agent.
4. Measure before asserting a threshold. Report N beside every score. Never
   invent a number.
5. Challenge the build before drafting a requirement: name the maintained
   options, state the delta, and let the user choose.
6. Report findings and fix nothing in the same pass.
7. Prove each requirement at the lowest tier that can prove it.

## The loop -- which skill, when

| When | Skill |
|---|---|
| any change is asked for | `/intake` -- spike, defect, bounded or structural, said out loud; the class only ratchets up |
| an approved intake needs its requirements | `/discover` |
| something behaves wrongly | `/debug` -- root cause before any fix |
| a deterministic requirement has no failing test | `/accept` |
| a failing test needs its code | `/tdd` -- one cycle, then stop |
| a requirement is evaluated | `/eval` |
| a change's tasks are all checked | `/verify` |
| a change is verified | `/land` -- the user invokes it |
| a failure a check could have caught | `/learn` |
| a repository-wide audit | `/quality` |

`bash .claude/sdd/sdd.sh status` shows where each in-flight change stands. Run
OpenSpec only through `bash .claude/sdd/sdd.sh openspec <args>` -- the pinned
version, telemetry off. The project's commands are in `sdd.toml` `[commands]`.

## What enforces this -- and what does not

- **Fails the build:** `sdd check`, `openspec validate --strict` and the
  project's architecture tests, all inside `[commands].check`.
- **Edit hooks** refuse writes to secrets, ground truth, lockfiles and CI
  workflows, and ask before living specs or enforcement files change. They
  guard the Edit and Write tools only; a shell goes around them. The real
  boundary is branch protection, required review, and CI no agent can edit.
- **No machine can check** that a test actually proves its requirement. That is
  `/verify`'s proof lens, and it needs a reader.

---
name: land
description: "Land a verified change: fresh evidence, archive the change into the living spec, then a PR or a merge."
argument-hint: "<change-id>"
model: inherit
disable-model-invocation: true
---

# /land -- evidence, archive, integrate

Change: $ARGUMENTS

```
NO CLAIM OF A STATE WITHOUT A FRESH OBSERVATION OF IT
```

Identify the command that proves the claim, run it now, read its output -- exit
code, counts, failures -- and only then state the result, with the evidence.
"Should pass", "passed earlier" and a subagent's "done" are not evidence; the
law covers paraphrases and expressions of satisfaction too. (Superpowers'
verification gate; see .claude/sdd/CREDITS.md.)

## 1. The change is verified, at this commit

`openspec/changes/<id>/verify.md` says **SHIP**, and its reviewed sha is HEAD --
or everything after it is the archive itself. Code changed since the review:
run `/verify` again. A spike lands with its verdict recorded in intake.md and no
verify.md.

## 2. Fresh evidence

Run `[commands].check` from `sdd.toml`. It must pass, now.

## 3. Archive inside the branch -- the change's last commit

```bash
bash .claude/sdd/sdd.sh openspec archive <id> --yes
bash .claude/sdd/sdd.sh check
```

Archive merges the deltas into `openspec/specs/` and moves the change to
`openspec/changes/archive/`. Then the living spec claims the tests directly,
so `sdd check` must still be green. Commit: `Archive <id>: <the outcome>`.

**Why inside the branch:** the code and the living spec then land atomically.
Archived on the default branch ahead of the merge, the living spec would claim
behaviour the default branch does not have. Archived never, the change stays
"in flight" forever.

## 4. Integrate -- the user chooses

Present exactly these options and wait:

```
<id> is verified, archived and green. How should it land?
1. Push and open a pull request against <base>   (protected default branch: the only option)
2. Merge into <base> locally
3. Keep the branch as it is
```

- **Pull request:** title is the outcome. Body: the intent from intake.md; the
  requirements added, modified and removed; the evidence -- each command and
  what it printed; the verify verdict; and Not checked.
- **Merge:** run `[commands].check` again on the merged result before anything
  is deleted. Red there: stop, leave everything in place, investigate.
- **Discard** happens only when the user asks for it explicitly, after you list
  what will be deleted and they confirm.

## 5. Then

Ask once: *did anything go wrong in this change that a requirement, guard,
check or fixture could have caught?* If so, `/learn`.

## Red flags

| Thought | Reality |
|---|---|
| "CI will run the checks anyway" | CI is a second witness, not the first. Run them now. |
| "Archive after merge, on main" | Then the living spec and the code are briefly two different truths, on the branch everyone pulls. Archive in the branch. |
| "verify.md is a bit old, but nothing important changed" | Then re-verifying is quick. A review of different code is not a review. |
| "It's done!" (before the commands ran) | Satisfaction before evidence is the exact failure this law exists for. |

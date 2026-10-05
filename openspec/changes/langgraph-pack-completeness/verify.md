# Verify

- **Verdict:** SHIP
- **Reviewed at:** `0835885`, after a first pass at `2f57610` (two MINOR
  findings, no blocker) and a separate fix pass.
- **Evidence:** run fresh at `0835885`.
  - `bash scripts/check.sh`: all checks passed.
    - The method's 117 tests: OK.
    - `sdd check --config .claude/sdd/self.toml`: OK on 7 capabilities, 35
      requirements and 5 test files, all claimed.
    - The manifest matches: 107 files at 0.4.0.
    - `openspec validate --all --strict`: 1 passed.
    - The suite: 30 passed, 3 skipped, each with its reason.
  - `shellcheck -x` clean on every hook and wrapper.
  - The two new requirements' tests were watched red first: six refusals
    came back allowed (`AssertionError: 2 != 0`).
  - `openspec instructions specs` on a probe change prints the new route
    rule.
  - The ladder's middleware facts were read from the installed classes
    (langchain 1.4.3): defaults from their signatures, behaviour from their
    docstrings and, for `ToolRetryMiddleware`'s `'continue'`, its source
    ("Return a `ToolMessage` with error details").

## Findings

The three lenses over `72bfd21..2f57610`.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MINOR | placement | The guard's comment marks rule 4 "(langgraph pack)", but its data-store half refuses `*.db`, `*.sqlite` and `*.sqlite3` in every project with the core guard. `GUARD-RUNTIME-DATA` states it generally, as it should; the comment misleads | `guard-edits.sh` rule 4 | fixed in `0835885`: the comment says which half is the pack's and which is every project's |
| 2 | MINOR | defects | `GUARD-SERVER-CONFIG` matches text, so a graph id named `env` is refused too -- the same trade-off as `serve.sh`'s check, but not said where the rule is | `guard-edits.sh` rule 7 | fixed in `0835885`: the comment says so |

Second pass, at `0835885`: the fix diff `2f57610..0835885` -- two comments in
`guard-edits.sh` and the manifest -- read on its own. Nothing new to report.
`bash scripts/check.sh` is green again: 117 method tests, 35 requirements
traced.

## Not checked

- **Fresh-context lenses.** Read by the agent that wrote the change, as in the
  last change; the PR review is the independent read.
- **The route rule on a real change.** No graph change has gone through the
  loop yet. The rule reaches the specs stage (seen in OpenSpec's
  instructions); whether it produces the right requirements will show on the
  foundation slice.
- **Whether the middleware facts stay true.** They are pinned to langchain
  1.4.3; the ladder says to re-check them when `langchain` moves.

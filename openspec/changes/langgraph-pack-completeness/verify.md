# Verify

- **Verdict:** SHIP -- pending a second read of the fix pass below
- **Reviewed at:** `2f57610`
- **Evidence:** run fresh at that commit.
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
| 1 | MINOR | placement | The guard's comment marks rule 4 "(langgraph pack)", but its data-store half refuses `*.db`, `*.sqlite` and `*.sqlite3` in every project with the core guard. `GUARD-RUNTIME-DATA` states it generally, as it should; the comment misleads | `guard-edits.sh` rule 4 | say which half is the pack's and which is everyone's |
| 2 | MINOR | defects | `GUARD-SERVER-CONFIG` matches text, so a graph id named `env` is refused too -- the same trade-off as `serve.sh`'s check, but not said where the rule is | `guard-edits.sh` rule 7 | say so in the comment |

## Not checked

- **Fresh-context lenses.** Read by the agent that wrote the change, as in the
  last change; the PR review is the independent read.
- **The route rule on a real change.** No graph change has gone through the
  loop yet. The rule reaches the specs stage (seen in OpenSpec's
  instructions); whether it produces the right requirements will show on the
  foundation slice.
- **Whether the middleware facts stay true.** They are pinned to langchain
  1.4.3; the ladder says to re-check them when `langchain` moves.

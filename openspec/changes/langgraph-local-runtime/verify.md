# Verify

- **Verdict:** DO NOT SHIP -- finding 1 leaves the guarantee this change adds
  editable without a prompt. Fix, then verify again.
- **Reviewed at:** `0f3aa67`
- **Evidence:** run fresh at that commit.
  - `bash scripts/check.sh`: all checks passed -- format and lint clean;
    architecture 30 passed and 3 skipped, each skip with its reason;
    `openspec validate --all --strict` 1 passed; `sdd check` OK; the method's
    109 tests OK; `sdd check --config .claude/sdd/self.toml` OK on 7
    capabilities, 33 requirements and 5 test files, all claimed; the manifest
    matches; the suite 30 passed and 3 skipped.
  - Every test written in this change was watched red first. The red is
    recorded per group in `tasks.md`.
  - Hand mutations were all caught:
    - 13 of the wrapper and the settings;
    - each of the nine deny rules deleted in turn;
    - 7 of the distribution code;
    - 7 of the architecture helpers;
    - a planted violation in the real package.
  - The real server was run through the seeded wrapper under strace, with
    LangSmith keys and tracing exported by the calling shell: 0 `connect()`
    calls (`tasks.md` 9.4).

## Findings

The three lenses, read in this order against the diff `8b7c8be..0f3aa67`.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | placement | `scripts/serve.sh`, `seeds/serve.sh` and `seeds/settings.langgraph.json` now carry the local-only guarantee. Yet the edit guard asks before a change to `scripts/check.sh` and the checker, not before a change to these: an agent could pass `--tunnel` through the wrapper, or drop a deny rule, without a prompt | `.claude/hooks/guard-edits.sh` rule 7; `GUARD-ASK` | add both scripts and the seeds directory to rule 7 and to `GUARD-ASK`, test first |
| 2 | MINOR | defects | The deny rules match text, so a command that merely mentions a denied phrase is refused. This includes a commit message or PR body passed on the command line, such as `git commit -m "... langgraph dev ..."` | settings deny; CLAUDE.md | keep the contains-rules, since a false refusal costs a retry and a missed spelling leaks. Document the way round: write the message to a file and commit with `-F` |
| 3 | MINOR | defects | The wrapper's tracing check matches `true`, `True`, `TRUE` and `1`. The server lower-cases the value, so `tRuE` is true to it and passes the check | `seeds/serve.sh` | match the value case-insensitively, with bracket classes for a portable sed |
| 4 | MINOR | defects | `_unmerged` assumes a project's settings `env` and `permissions` are objects. A malformed file (`"env": []`) raises AttributeError, after install has already copied the method | `sddlib/distribute.py` | treat a non-object as empty, so the merge is reported |
| 5 | MINOR | defects | The wrapper's `"env"` check is textual, so a graph id named `env` would be refused too | `seeds/serve.sh` | accept it, and say so in the comment -- a JSON parser in bash would cost more than that edge |
| 6 | MINOR | placement | design.md does not say why the pack's seed files ship in core: the selftest's `test_serve.py` reads them in every installed copy | `design.md`, decision 3 | one sentence |
| 7 | MINOR | defects | `ServeCase.config` repeats `DEFAULT_CONFIG` from the support module | `test_serve.py` | use the constant |

## Not checked

- **Fresh-context lenses.** The three lenses were read by the agent that wrote
  the change, in its own context, not by fresh-context subagents. This
  session's tool policy rules out spawning agents unless asked. The PR review
  is the independent read.
- **Claude Code's own matching of the deny rules.** `LOCAL-AGENT-SETTINGS` is
  proved against a model of the matcher taken from its documentation (`*`
  stands for any text; contains-rules only, which a test enforces), not
  against Claude Code. Checking it needs a live session in this repository.
- **bash 3.2.** The wrapper avoids bash-4 features (no `${x,,}`, no `mapfile`,
  arrays expanded with the `${a[@]+...}` idiom), but was run only on this
  machine's bash 5.
- **macOS and Windows.** The strace probe is Linux only. The wrapper's
  `printenv` and `sed -E` are POSIX, but untested elsewhere.
- **The graph auditors.** Nothing to audit: no graph exists.

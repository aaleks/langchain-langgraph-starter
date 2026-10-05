# Verify

- **Verdict:** SHIP
- **Reviewed at:** `18ebc84`, after a first pass at `0f3aa67` returned DO NOT
  SHIP (finding 1) and a separate fix pass.
- **Evidence:** run fresh at `18ebc84`.
  - `bash scripts/check.sh`: all checks passed.
    - Format and lint clean.
    - Architecture: 30 passed, 3 skipped, each skip with its reason.
    - `openspec validate --all --strict`: 1 passed.
    - `sdd check`: OK.
    - The method's 111 tests: OK.
    - `sdd check --config .claude/sdd/self.toml`: OK on 7 capabilities, 33
      requirements and 5 test files, all claimed.
    - The manifest matches: 107 files, version 0.3.0.
    - The suite: 30 passed, 3 skipped.
  - `shellcheck -x` clean on both wrappers, every hook, `sdd.sh` and
    `check.sh`.
  - **The real server, started by the final wrapper under strace**, with
    `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, `LANGGRAPH_CLOUD_LICENSE_KEY`,
    `LANGSMITH_TRACING=true`, `LANGCHAIN_TRACING_V2=true` and
    `LANGSMITH_ENDPOINT=https://api.smith.langchain.com` exported by the
    calling shell:
    - it served on `http://127.0.0.1:8123` and skipped its metadata loop;
    - a run returned `{"text":"LOCAL ONLY"}`;
    - `strace -f -e trace=connect` recorded **0 `connect()` calls**.
  - Every test written in this change was watched red first; `tasks.md`
    records each red.
  - Hand mutations were all caught:
    - 13 of the wrapper and the settings;
    - each of the nine deny rules deleted in turn;
    - 7 of the distribution code;
    - 7 of the architecture helpers;
    - a violation planted in the real package for each of the three graph
      checks.

## Findings

First pass, at `0f3aa67`: the three lenses over `8b7c8be..0f3aa67`.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | placement | `scripts/serve.sh`, `seeds/serve.sh` and `seeds/settings.langgraph.json` carry the local-only guarantee. Yet the edit guard asked before a change to `scripts/check.sh` and the checker, not before a change to these: an agent could pass `--tunnel` through the wrapper, or drop a deny rule, without a prompt | `guard-edits.sh` rule 7; `GUARD-ASK` | both scripts and `.claude/sdd/seeds/*` added to rule 7 and to `GUARD-ASK`, test first |
| 2 | MINOR | defects | The deny rules match text, so a command that merely mentions a denied phrase is refused. This includes a commit message or PR body passed on the command line | settings deny; CLAUDE.md | the contains-rules kept: a false refusal costs a retry, a missed spelling leaks. The way round is documented in CLAUDE.md and `runtime.md` |
| 3 | MINOR | defects | The wrapper's tracing check matched only `true`, `True`, `TRUE` and `1`. The server lower-cases the value, so `tRuE` was true to it and passed the check | `seeds/serve.sh` | the value is now matched case-insensitively; a `tRuE` row added to `LOCAL-SERVE-REFUSALS`, red then green |
| 4 | MINOR | defects | `_unmerged` assumed a project's settings `env` and `permissions` were objects; a malformed file crashed install after it had copied the method | `sddlib/distribute.py` | malformed shapes are read as empty and the merge reported; a row added to `DIST-PACK-SEEDS`, red (`AttributeError`) then green. Hardened again in the fix pass for a non-list rule set, which would have read as a substring |
| 5 | MINOR | defects | The wrapper's `"env"` check is textual, so a graph id named `env` is refused too | `seeds/serve.sh` | accepted, and said so in the comment |
| 6 | MINOR | placement | design.md did not say why the pack's seed files ship in core | `design.md`, decision 3 | one paragraph: the selftest reads them in every installed copy |
| 7 | MINOR | defects | `ServeCase.config` repeated `DEFAULT_CONFIG` | `test_serve.py` | the constant used |

Second pass, at `18ebc84`: the fix diff `0f3aa67..18ebc84`, read on its own.
Nothing new to report.

## Not checked

- **Fresh-context lenses.** The lenses were read by the agent that wrote the
  change, in its own context, not by fresh-context subagents. This session's
  tool policy rules out spawning agents unless asked. The PR review is the
  independent read.
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

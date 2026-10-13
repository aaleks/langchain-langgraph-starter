# langchain-langgraph-starter

A starting point for LangChain and LangGraph applications, developed
**spec-first, with proof**: every requirement names the test that proves it,
every test is claimed by a requirement, and the build fails the moment either
side drifts.

What you get on day one:

- **The SDD method**, in `.claude/` -- OpenSpec runs the lifecycle of
  specifications; a proof layer holds each requirement to its test; ten skills
  carry a change from intake to landing. Start at
  [`.claude/sdd/README.md`](.claude/sdd/README.md).
- **A walking skeleton** -- five layers with their contracts already enforced,
  each check proved able to fail. Product code arrives through the loop like
  everything else: so far the `assistant` graph, its Open WebUI model, and a
  task list it reads.
- **A LangGraph plan** -- the adoption ladder, where graphs live, and the slices
  to build them in: [`docs/roadmap.md`](docs/roadmap.md).
- **LangGraph on your machine only** -- never through LangSmith: no hosted
  Studio, no tracing, no `langgraph up`. `bash scripts/serve.sh` is the one way
  to start the development server, from an environment measured to make no
  outbound connection. Why, and what replaces Studio:
  [`docs/decisions/0004-langgraph-runs-locally.md`](docs/decisions/0004-langgraph-runs-locally.md).

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 0.8+ | Python 3.13, the environment, the lockfile |
| Node.js | 20.19+ | OpenSpec, pinned and run through `npx` |
| bash | any | the hooks and `sdd.sh` -- Git Bash on Windows |
| [Claude Code](https://code.claude.com) | current | the skills, agents and hooks |

## Start

```bash
uv sync                      # Python 3.13, the dev tools, the package (editable)
bash scripts/check.sh        # every check -- green on a fresh clone
```

Then, in Claude Code, describe the first change:

```
/intake "Add the LangGraph foundation slice from docs/roadmap.md"
```

`/intake` classifies it and waits for your approval; `/discover` turns it into
requirements you approve; `/accept` and `/tdd` prove them one at a time;
`/verify` reviews; `/land` archives and integrates. The walkthrough is
[`.claude/sdd/GUIDE.md`](.claude/sdd/GUIDE.md).

## The loop

```
/intake -> /discover -> /accept -> /tdd -> /verify -> /land       (+ /learn after anything goes wrong)
   |           |                     ^
   |           +-- evaluated? -------+-- /eval: a scored check, never ==
   +-- defect? -> /debug: root cause first, then a requirement that stays
```

What enforces it: `bash .claude/sdd/sdd.sh check` (traceability, in both
directions), `openspec validate --strict`, the architecture tests, and edit
hooks that refuse writes to secrets, ground truth, lockfiles and CI. What does
not, and cannot: whether a test actually proves its requirement -- that is
`/verify`'s job, and it needs a reader. The honest list is in
[`.claude/sdd/README.md`](.claude/sdd/README.md#what-this-guarantees----and-what-it-does-not).

## Make it yours

1. **Turn on CI and protect `main`** -- one command and two settings, in
   [`docs/ci/README.md`](docs/ci/README.md). Until then, the edit hooks are the
   only line, and they are a habit guard, not a boundary.
2. **Rename the package** `starter` -> yours: the `src/starter/` directory; in
   `pyproject.toml`, `[tool.uv.build-backend] module-name`, `[tool.importlinter]`
   (the root and every layer) and `[tool.ruff.lint.isort] known-first-party`;
   `module-path` in `mutation.toml`; and the package named in
   `openspec/config.yaml`'s context. Then `uv sync` and `bash scripts/check.sh` --
   the architecture tests read the name from `[tool.importlinter]`, so they follow.
3. **Describe the project** in `openspec/config.yaml` (`context`) and
   `CLAUDE.md`: what an agent cannot infer by reading the code.

## Reuse the method in another starter

The method is versioned and distributed from this repository:

```bash
bash .claude/sdd/sdd.sh install ../another-starter --packs python,langgraph
bash .claude/sdd/sdd.sh update  ../another-starter       # later, from a newer checkout
```

Install never overwrites a file; update replaces only what the other project
never modified, and reports the rest. Packs: `core` always, `python` for the
layer rules, `langgraph` for graph rules, auditors and the local-only runtime --
it seeds `scripts/serve.sh` and adds the local-only environment and deny rules
to the settings it seeds.

## Layout

```
src/starter/          domain, config, application, infrastructure, cli -- empty, contracted
tests/                unit, integration, acceptance; architecture checks the checkers
openspec/             specs (living), changes (in flight), the sdd-proof schema
.claude/              skills, agents, rules, hooks, and sdd/ -- the method itself
sdd.toml              where this project keeps its specs and tests, and its commands
docs/                 decisions (ADRs), architecture, roadmap, ci, learnings
scripts/check.sh      every check, one list
scripts/serve.sh      the local LangGraph server -- 127.0.0.1, nothing to LangSmith
```

## Licence

Apache 2.0 -- see [LICENSE](LICENSE). The method's credits and the licences of
the work it builds on are in [`.claude/sdd/CREDITS.md`](.claude/sdd/CREDITS.md).

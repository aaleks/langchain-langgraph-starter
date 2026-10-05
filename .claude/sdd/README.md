# SDD -- spec-driven development, with proof

A method for building software with an AI agent where every requirement names
the test that proves it, every test is claimed by a requirement, and neither
direction is allowed to drift -- because the build fails when it does.

Three parts, each owned by whoever does it best:

| Part | Owner | What it does |
|---|---|---|
| The lifecycle | [OpenSpec](https://github.com/Fission-AI/OpenSpec), pinned | changes as deltas, archived into living specs; a schema that makes the stages executable |
| The proof | this layer | the requirement format, the checker, the guards, the auditors |
| The behaviour | these skills | intake, evidence before claims, root cause before fixes, review, landing, learning |

Built for projects that use language models, where the hardest rule is the
**determinism boundary**: a requirement is either asserted exactly or scored
against a threshold somebody agreed, and generated prose is never asserted.

Read [`METHOD.md`](METHOD.md) for the method, [`GUIDE.md`](GUIDE.md) to walk one
change through it, and [`CHANGELOG.md`](CHANGELOG.md) for what changed.

## Needs

| Tool | For | Why this one |
|---|---|---|
| bash | the hooks and `sdd.sh` | Claude Code runs hooks through it; on Windows that is Git Bash |
| Python 3.11+ | the checker, status, stats, install | standard library only -- nothing to install, any project language |
| Node 20.19+ and npx | OpenSpec | fetched and pinned by `sdd.sh openspec`; the checker never needs it |
| git | the Stop hook, `/land` | |

`sdd.sh` finds a working Python itself -- `python3`, then `python` (on Windows
`python3` may be the Store stub), then `uv` -- or set `SDD_PYTHON`.

## What lives where

```
.claude/
  sdd/               the method: this README, METHOD, GUIDE, CHANGELOG, the checker
                     (sdd.sh, sdd.py, sddlib/), its own specs and tests, fixtures,
                     seeds, packs/, manifest.json
  skills/            intake discover accept tdd eval debug verify quality land learn
  agents/            spec-compliance code-reviewer architecture-guardian
                     determinism-auditor mutation-analyst observability-auditor
                     (+ the langgraph pack's four)
  rules/sdd/         laws.md (always loaded), specs.md, tests.md (path-scoped)
  rules/<pack>/      python/, langgraph/ -- path-scoped, inert where paths do not match
  rules/project/     the project's own lessons -- never touched by the method
  hooks/             guard-edits.sh, check-alignment.sh, session-context.sh
  settings.json      wiring for the hooks and permissions -- project-owned
openspec/
  schemas/sdd-proof/ the stage contract: schema.yaml and its templates
  config.yaml        the project's context -- project-owned
  specs/             the living truth, written by archive
  changes/           in flight; changes/archive/ is history
sdd.toml             the adapter: the one file that says where this project keeps things
scripts/check.sh     every check, one list -- project-owned
```

## The adapter -- `sdd.toml`

The only project-specific file the tooling reads. Unknown keys are refused, not
ignored: a setting that silently does nothing is worse than one rejected.

| Key | Means |
|---|---|
| `[specs] living` | the living specs (`openspec/specs`) |
| `[specs] changes` | in-flight changes (`openspec/changes`); `archive/` inside is never checked |
| `[tests] roots`, `patterns` | where test files live and what their names look like |
| `[tests] exempt` | globs claimed by no requirement -- checks of the checkers. Keep it short |
| `[tests] symbols` | how `file::Name` resolves: `python`, `none`, or `regex:<pattern with one group>` |
| `[commands] *` | `check`, `suite`, `test` (with `{target}`), `architecture`, `lint`, `format`, `live`, `strength` -- read by skills and agents so none hard-codes a runner |
| `[guards] ground_truth` | globs the edit guard refuses; one line per array, because the guard is bash |

A configured directory that does not exist is an error, never an empty project.

## Packs

The core is stack-neutral. A pack adds what is true of every project on one stack:

| Pack | Adds |
|---|---|
| `core` | everything above, always |
| `python` | layer rules for `src/*/domain`, `application`, `infrastructure` -- see `packs/python.md` |
| `langgraph` | the orchestration ladder, graph and runtime rules, four auditors, and LangGraph on the developer's machine only: a seeded `scripts/serve.sh` and settings that keep the agent away from LangSmith -- see `packs/langgraph.md` |

## Install, update, release

```bash
# from a checkout of this repository, into another project
bash .claude/sdd/sdd.sh install ../other-project --packs python,langgraph
bash .claude/sdd/sdd.sh install ../other-project --dry-run       # see first

# later, from a newer checkout
bash .claude/sdd/sdd.sh update ../other-project [--dry-run]

# releasing a change to the method, in this repository
#   bump VERSION in sddlib/__init__.py, add a CHANGELOG entry, then:
bash .claude/sdd/sdd.sh manifest
```

- **install** copies what is absent and seeds the project-owned files once
  (`sdd.toml`, settings, `openspec/config.yaml`, `scripts/check.sh`, the lessons
  and learnings files). A pack seeds its own files too (`langgraph`:
  `scripts/serve.sh`), and adds its rules to the settings being seeded. It
  never writes `CLAUDE.md`, `.env`, `pyproject.toml`, a lockfile, `src/` or
  `tests/`. An existing file is left alone and reported.
- **update** replaces a shipped file only if it is still exactly what was
  installed. A file the project modified is reported and left alone -- never
  merged -- and a file it deleted is not restored. Seeds are never updated; a
  pack seed new in this version is reported, and running `install` again with
  the same packs writes it.
- **manifest --check** fails when a shipped file changed without the manifest
  moving with it; `scripts/check.sh` runs it here, so the method cannot drift
  from its own record. Install and update refuse a source whose manifest is stale.

An existing `.claude/settings.json` is left alone: merge the `hooks` block from
`seeds/settings.json` by hand, once -- and, with the langgraph pack, the `env`
and `deny` entries of `seeds/settings.langgraph.json`, which install reports.

## What this guarantees -- and what it does not

**Fails the build, mechanically:**

- every requirement declares its kind, names a proof that resolves to a real
  test (and test name), and carries a counter-example;
- every test file is claimed by a requirement;
- every evaluated requirement states its threshold, its N and who agreed them --
  or says OPEN, with an owner and a review date;
- every change is structurally valid OpenSpec, and modifies only what exists;
- the method's own checker is proved against 17 fixtures that must fail and 4
  counter-examples that must pass.

**Guarded at write time, not guaranteed:** the edit hooks refuse writes to
secrets, ground truth, lockfiles and CI workflows, and ask before the living
spec or the enforcement changes. They watch the Edit and Write tools only -- a
shell command goes around them, as it goes around any hook. With the langgraph
pack, settings deny the agent the commands that would reach LangSmith; they
match command text, so a launcher spelled another way goes around them too.
All of these are a guard against habit, not a security boundary. **The boundary is outside the agent**:
a protected default branch, required review, and CI that runs from the
committed revision and that no agent can edit. Turn those on.

**Needs a reader:** whether a named test actually *proves* its requirement --
four scenarios, two asserted, passes every check above. That is `/verify`'s
proof lens, done by a fresh-context agent and read by a person.

**Cheap and complete checks are different, on purpose.** The Stop hook runs only
`sdd check` -- under a second -- at the end of a turn that changed files.
`scripts/check.sh` runs the complete list: format, lint, architecture,
`openspec validate --strict`, `sdd check`, the method's own tests, the suite.
A terminal, CI and `/land` run that script, so the list cannot drift between them.

## Known limits

- **This method makes a claim checkable; it does not make it true.** A green
  build says requirements and tests are linked and the tests pass, not that the
  requirements are the right ones.
- **The skills' wording is not yet pressure-tested** against an agent under
  deadline pressure the way Superpowers' is. `pressure-tests.md` holds the
  protocol and the log -- empty, honestly, at 0.3.0.
- **Portability is partly proved**: the checker reads its layout from the
  adapter, its own specs pass through a second adapter, and it has resolved and
  refused references in a TypeScript layout with only `sdd.toml` changed. No
  project in another language has yet landed a change end to end.
- **OpenSpec's schema commands are marked experimental** upstream. The checker
  reads plain Markdown, so if OpenSpec changed or disappeared the specs and their
  proof would survive; the lifecycle commands would not.
- **Out of scope**: security review, penetration testing, compliance, release
  engineering and operations -- each waits in `deferred-register.md` with the
  condition that would bring it in.

## Where this came from

Built in a LangChain playground (`langchain-playground`), where every rule
exists because something broke: a check that passed while checking nothing,
a spec confidently wrong about a library, a threshold set from two examples, a
hand-written crawler nobody decided to build, an installed copy of this very
toolkit weaker than the one it was copied from. Three reviews then compared it
with OpenSpec, Superpowers and Spec Kit and merged the four; this is that merge.
What was taken from each is in [`CREDITS.md`](CREDITS.md).

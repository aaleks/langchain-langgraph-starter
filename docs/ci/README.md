# CI

**Proposed, not yet enabled.** The workflow is `docs/ci/ci.yml`. To turn it on:

```bash
mkdir -p .github/workflows && git mv docs/ci/ci.yml .github/workflows/ci.yml
```

Then, in the repository settings, **protect `main`**: require a pull request,
require the `checks` job to pass, and do not allow bypassing. Those two settings
are the real boundary of this method -- the edit hooks guard an agent's Edit and
Write tools, and a shell command goes around them.

## Why an agent did not put it there

`.claude/settings.json` denies an agent `Edit` and `Write` on
`.github/workflows/**`, and the edit guard refuses them too. CI is where *what
gets enforced* is decided; an agent that can rewrite its own enforcement can
quietly stop enforcing anything. An agent may propose a change here; a person
moves it. Every later change to the workflow takes the same route.

## What it runs

| Job | When | Needs |
|---|---|---|
| `checks` | every push to `main`, every PR | nothing: no Docker, no keys, no quota |
| `live` | on demand (`workflow_dispatch`) | whatever the live tests declare -- none exist yet |

Both run `bash scripts/check.sh` -- the same list `/land` and a terminal run.

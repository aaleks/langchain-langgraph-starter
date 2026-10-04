# The python pack

Layer rules for a Python project laid out as `src/<package>/{domain, config,
application, infrastructure, cli}` -- installed with `--packs python`.

| File | Loads when Claude touches | Says |
|---|---|---|
| `rules/python/domain.md` | `src/*/domain/**` | standard library only; the environment is an argument; deterministic; raise, never exit |
| `rules/python/application.md` | `src/*/application/**` | `langchain_core` and `pydantic` at most; the model is an argument; a prompt is a named constant and is behaviour |
| `rules/python/infrastructure.md` | `src/*/infrastructure/**` | wiring, not judgement; one builder per client; lazy SDK imports; retry only the transient |

The edit guard's two Python rules -- refuse an SDK import into `src/*/domain/`,
note a prompt constant in `src/*/application/` -- are keyed to those paths, so
they are inert in a project without them.

What the pack does **not** ship: the architecture tests themselves. They depend
on the project's package and its contracts in `pyproject.toml`, so they are
project-owned. This repository's `tests/architecture/` is the reference to copy:
an import-linter layer contract driven through its API with a vacuity guard,
allowlists by layer (grimp, package granularity), the environment read only in
`config/`, the process exited only in `cli/` -- each proved to fail on a fixture
package.

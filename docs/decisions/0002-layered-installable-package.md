# 2. A layered package, installable from the first commit, with contracts that are proved to fail

Date: 2026-10-04
Status: Accepted

## Context

The decisions that matter in an LLM application -- which model, which route,
whether a budget is exhausted, whether an action is permitted -- are ordinary
logic. Buried beside a model call they cannot be tested without one; pulled into
a layer that imports nothing they are tested in milliseconds. In the project
this method came from, that separation was what made most requirements
deterministic, and it eroded wherever nothing enforced it.

Two of its enforcement mechanisms had also passed while checking nothing: an
import-linter run that exited 0 because it could not find the package, and an
allowlist evaluated over an empty set of imports.

## Decision

Five layers under `src/starter/`, dependencies pointing inward:
`cli -> infrastructure -> (application | config) -> domain`. Application and
config are independent siblings: a use case takes its settings as arguments.

- **Allowlists, not denylists**: domain imports the standard library only;
  application adds `langchain_core` and `pydantic`. A denylist names the packages
  that existed when it was written; the next dependency walks past it.
- **Conventions that imports cannot express are checked over the syntax tree**:
  `os.environ` only in config, `sys.exit` only in the CLI.
- **Every rule is proved twice**: it holds for `starter`, and it fails for a
  fixture package built to break it. The layer contract itself is re-run against
  fixtures, so weakening it in `pyproject.toml` fails the suite.
- **The package is installable from the first commit** (`uv_build`, editable via
  `uv sync`). The roadmap's LangGraph plan called packaging a later, deliberate
  slice; it is taken now instead because the import graph needs the package
  importable, and an Agent Server will import it the same way. No `pythonpath`
  hack in pytest.

## Consequences

**Good.** The boundaries are enforced before there is code to violate them, and
none of the checks can pass vacuously. A LangGraph graph has an obvious home,
and `langgraph` imported anywhere else fails the build.

**Costly.** Five directories and a contract to learn before the first feature.
Justified by the test surface it buys, and by nothing else -- if the decision
layer stays empty while adapters grow, that is the finding.

# Frame

## Outcome

Whoever runs the checks on a machine that refuses `.venv\Scripts\pytest.exe`
-- the owner's, since 2026-10-16 -- gets `bash scripts/check.sh` green again,
and every skill that reads `sdd.toml`'s commands runs the same tests. The
signal: `bash scripts/check.sh` ends `all checks passed` on this machine, and
on CI's Linux runner as before.

Non-goals: the method's seeds stay as they are; no test, requirement or
dependency changes; the machine's policy is the owner's to change, not this
project's.

## Existing options considered

None -- a change to this project's own configuration: `python -m pytest` is
pytest's own documented way to run it, the same code without the console-script
launcher.

**Decision:** run pytest as a module. Chosen by the agent under the owner's
standing delegation.

## Orchestration rung

N-A -- no LLM work.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | `check.sh` green here and on CI |
| Behaviour -- every rule falsifiable, each with a counter-example | N-A | no requirement moves (`skip_specs`) |
| Determinism -- honestly tagged; every evaluated rule split once more | N-A | no requirement |
| Data -- provenance, freshness, what happens when a source is withdrawn | N-A | no data |
| Untrusted input -- anything ingested that this project did not write | N-A | none |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | `sdd.toml`'s commands are the method's interface to the suite; their meaning is unchanged |
| Failure -- what the user sees when a dependency is down | Clear | a missing pytest fails `python -m pytest` as loudly as the launcher |
| Cost -- tokens, time, money and storage per run | N-A | the same tests |
| Ownership -- who decides when a requirement turns out to be wrong | N-A | no requirement |

`python -m pytest` puts the working directory on `sys.path`, which the launcher
does not. The suite already imports `tests.*` as packages from the repository
root, so nothing new becomes importable -- the full suite run is the proof.

## Defect

N-A

## Open questions

None.

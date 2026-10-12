# Learnings

What went wrong, and what it left behind. Written by `/learn`: exactly one
output per failure -- a requirement, a check, a guard, a fixture, a
rationalisation row, or an explicit "judgement, not automatable".

Mark an entry **upstream** when it would help every project using the method;
it belongs in the canonical method and arrives elsewhere through `sdd.sh update`.

| Date | What went wrong | Output | Link | Upstream |
|---|---|---|---|---|
| 2026-10-12 | Once LangChain was installed, the default suite ran graphs in whatever environment the shell exported: a shell with `LANGSMITH_TRACING=true` would upload every run, from a background thread no network guard saw. Every run in an agent session was green because `.claude/settings.json`'s `env` sealed it -- and so was the first in-process check of the seal. Should have been caught when the dependency arrived: the langgraph pack seals the server (`serve.sh`) and the agent (settings), not the test process. Caught by `/verify` pass 1 | **a check**: `tests/conftest.py` applies `LOCAL_ONLY` before langchain_core is imported; `tests/architecture/test_local_only.py` holds it equal to the settings and proves it in a subprocess from a hostile environment -- red with the seal removed, inside an agent session too | register-first-graph (`openspec/changes/archive/2026-10-12-register-first-graph/verify.md`, findings 1 and 25); PR #4 | **upstream**: the langgraph pack should seed the seal and its check into every project, beside `serve.sh` |

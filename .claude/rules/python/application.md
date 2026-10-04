---
paths:
  - "src/*/application/**"
---

# The application layer -- use cases, prompts, output contracts

- **May import** the standard library, `langchain_core`, `pydantic` and the
  domain -- the abstractions every use case builds on. **Never a runtime**
  (`langchain`, `langgraph`, `deepagents`) and never a vendor SDK; the
  architecture test enforces it at package granularity, which is the only
  granularity the import graph records.
- **The model is an argument.** A use case that constructs its own model cannot
  be tested against a fake.
- **A prompt is a named module constant**, never text assembled inline in a
  function body.
- **A prompt is behaviour that no deterministic test asserts.** Changing its
  text changes the product: the evaluated requirements that depend on it need
  `/eval` before the change lands, and the prompt's version moves with its text.
- Output contracts (pydantic models) and the errors a caller can act on live
  here; the agent loop that produces them lives in `infrastructure/agents/`.

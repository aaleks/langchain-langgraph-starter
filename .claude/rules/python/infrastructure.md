---
paths:
  - "src/*/infrastructure/**"
---

# The infrastructure layer -- thin adapters

- **Wiring, not judgement.** An `if` on a threshold, a precedence choice, a
  retry count or a routing rule here is a domain decision in the wrong place --
  the most common decay in an LLM codebase, and no linter finds it. Call a
  domain function and act on its answer.
- **One place builds each kind of client.** A chat model constructed anywhere
  but its builder is a second configuration path, and the two will disagree.
- **Import SDKs inside the function that needs them**, not at module scope, so
  an unrelated run does not pay for them.
- **Raise `ValueError` for what a caller can fix; never exit.** Only the entry
  point layer turns an error into an exit code.
- **Retry only the transient.** A missing key retried three times is one clear
  error made three times slower.

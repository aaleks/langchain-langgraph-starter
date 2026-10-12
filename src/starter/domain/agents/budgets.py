"""How much a run may spend before it is stopped -- each budget a terminal outcome."""

from __future__ import annotations

# A starting policy, chosen with no real model to measure against; revisited
# by the first change that installs a provider (docs/decisions/0005).
MODEL_CALLS_PER_RUN = 10

# How long one model call may take before it is abandoned -- and, if transient,
# retried (retries.py). A local model on a CPU can be slow; a starting policy,
# measured against real runs (connect-openwebui-model, frame.md).
MODEL_CALL_DEADLINE_SECONDS = 120

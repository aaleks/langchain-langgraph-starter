"""How much a run may spend before it is stopped -- each budget a terminal outcome."""

from __future__ import annotations

# A starting policy, chosen with no real model to measure against; revisited
# by the first change that installs a provider (docs/decisions/0005).
MODEL_CALLS_PER_RUN = 10

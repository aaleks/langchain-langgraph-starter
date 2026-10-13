"""How much a run may spend before it is stopped -- each budget a terminal outcome."""

from __future__ import annotations

# A starting policy, chosen with no real model to measure against; revisited
# by the first change that installs a provider (docs/decisions/0005).
MODEL_CALLS_PER_RUN = 10

# How long the assistant waits on the model at any one point -- to connect, for
# the next part of an answer, for the next streamed chunk -- before abandoning
# the call as timed out, and so transient (retries.py). Not a cap on a whole
# call: a model that keeps answering is not cut off. A local model on a CPU can
# be slow; a starting policy, to be measured against real runs
# (connect-openwebui-model, frame.md).
MODEL_CALL_TIMEOUT_SECONDS = 120

"""How much a run may spend before it is stopped -- each budget a terminal outcome."""

from __future__ import annotations

# Model turns a run may make. Measured (bound-the-tool-loop, frame.md): N = 20
# runs on gpt-5.4-mini took at most 2. Five times that stops a loop that runs
# away, never one that answers.
MODEL_CALLS_PER_RUN = 10

# Tool calls a run may execute, every tool together: a turn that would pass it
# ends the run with an error, none of its calls run. A starting policy, twice
# the model turns. Measured with the model-call budget: at most 2 a run.
TOOL_CALLS_PER_RUN = 20

# What one model call may send, in characters: the prompt, the messages, the
# tool calls' arguments. One read at its measured bound is 132,713 (TASKS-LIST);
# the prompt and a question fit beside it. Measured runs peaked at 16,148
# (N = 20). Characters, not tokens: no tokenizer for a model `.env` can change.
CONTEXT_CHARS_PER_CALL = 150_000


class ContextBudgetExceededError(RuntimeError):
    """A model call would have sent more than its budget: the run ends, the model
    not called."""

    def __init__(self, count: int, budget: int) -> None:
        super().__init__(f"a model call would send {count} characters; the budget is {budget}")
        self.count = count
        self.budget = budget


# How long the assistant waits on the model at any one point -- to connect, for
# the next part of an answer, for the next streamed chunk -- before abandoning
# the call as timed out, and so transient (retries.py). Not a cap on a whole
# call: a model that keeps answering is not cut off. A local model on a CPU can
# be slow; a starting policy, to be measured against real runs
# (connect-openwebui-model, frame.md).
MODEL_CALL_TIMEOUT_SECONDS = 120

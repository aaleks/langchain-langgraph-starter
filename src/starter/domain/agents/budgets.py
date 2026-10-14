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
# Per call: each turn re-sends the conversation, and each retry re-sends the
# turn, so a run's worst case is MODEL_CALLS_PER_RUN x (1 + MODEL_RETRIES) x
# this -- 4.5M characters: about 1.1M tokens of English, and up to 4.5M of text
# chosen to tokenize badly. What the model writes is MODEL_CALLS_PER_RUN x (1 +
# MODEL_RETRIES) x MODEL_OUTPUT_TOKENS at most: 122,880 tokens. A per-run total
# waits for a run that needs one (bound-the-tool-loop, verify.md 10 and 23).

# What one reply may hold, in tokens: the owner chose a cap, and a reply cut off
# at it ends the run (bound-the-tool-loop). Measured: at most 344 output tokens a
# reply, reasoning included (N = 20 on gpt-5.4-mini) -- twelve times that.
MODEL_OUTPUT_TOKENS = 4096


class ContextBudgetExceededError(RuntimeError):
    """A model call would have sent more than its budget: the run ends, the model
    not called."""

    def __init__(self, count: int, budget: int) -> None:
        super().__init__(f"a model call would send {count} characters; the budget is {budget}")
        self.count = count
        self.budget = budget


def check_context_chars(count: int) -> None:
    """Refuse a model call that would send more than CONTEXT_CHARS_PER_CALL."""
    if count > CONTEXT_CHARS_PER_CALL:
        raise ContextBudgetExceededError(count, CONTEXT_CHARS_PER_CALL)


class OutputBudgetExceededError(RuntimeError):
    """A reply was cut off at MODEL_OUTPUT_TOKENS: the run ends, its text never
    taken for an answer, its calls never run."""

    def __init__(self, cap: int) -> None:
        super().__init__(f"a reply was cut off at its cap of {cap} tokens")
        self.cap = cap


# How long the assistant waits on the model at any one point before abandoning
# the call as timed out, and so transient (retries.py): to connect, and -- since
# a call carrying tools is not streamed (MODEL-OPENWEBUI-CLIENT) -- for the
# whole reply. Measured (bound-the-tool-loop, verify.md pass 3): a reply at
# MODEL_OUTPUT_TOKENS takes about 259 s from the owner's local qwen3:1.7b (15.8
# tokens/s) and 16 s from gpt-5.4-mini. A run waits at most MODEL_CALLS_PER_RUN x
# (1 + MODEL_RETRIES) x this: 2.5 hours, every call slow to its limit.
MODEL_CALL_TIMEOUT_SECONDS = 300

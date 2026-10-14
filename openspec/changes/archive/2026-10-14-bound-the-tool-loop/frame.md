# Frame

## Outcome

**For the owner**, running the assistant on a real model over their real
task list. Every route of the tool loop ends in a stated outcome, and every
budget rests on runs that were measured. The signals:

- A model reply whose tool call cannot be parsed reaches the model again as an
  error it can correct. It never ends the run as an empty answer, which is
  what happens today: measured, a reply carrying only `invalid_tool_calls`
  ends the run as `human, ai`, the answer empty.
- A run whose conversation would send the model more than its budget ends with
  a named error before the call.
- Every model call is sent the assistant's prompt first.
- A task whose text gives the model orders changes nothing: the task list is
  unchanged and the budgets hold, whatever the model then proposes.
- The call budgets cite their measurement, with its N.

**Non-goals:**
- Search by assignee. The measurement showed "Which tasks are assigned to
  sam?" finds nothing, since TASKS-SEARCH matches title and notes. That is a
  separate change if the owner wants it.
- Writes: slice 4.
- An evaluated score for resisting prompt injection. With read-only tools,
  the adversarial case asserts no effect, deterministically.

## Measurement -- the budgets' evidence

`scripts/measure_tool_loop.py`, run on 2026-10-14 against the owner's Open
WebUI: model `gpt-5.4-mini`, N = 20 runs (5 questions x 4), a seeded list of
30 tasks, before this change's prompt. Every run completed. The results:

| Per run | Max | Mean |
|---|---|---|
| model calls | 2 | 2.0 |
| tool calls | 2 | 1.2 |
| largest input to one call (characters) | 16,148 | 7,569.6 |

- `MODEL_CALLS_PER_RUN = 10` and `TOOL_CALLS_PER_RUN = 20` stay. Five and ten
  times the measured maxima, they stop a loop that runs away, never one that
  answers. Lowering them buys nothing the measurement shows a need for.
- `CONTEXT_CHARS_PER_CALL = 150,000` is new. One read at its measured bound
  is 132,713 characters (TASKS-LIST); the prompt and a question fit beside
  it. The measured runs peaked at 16,148. A run that would send the model
  more than one full read's worth ends rather than growing.

## Existing options considered

| Option | Maintained? (what was checked) | Covers | Delta |
|---|---|---|---|
| `ContextEditingMiddleware(ClearToolUsesEdit)`, in `langchain` 1.4 | Ships with the pinned `langchain` (checked in the installed package) | Trims old tool results past a token trigger, and the run goes on | Rejected by the owner: "End the run with an error" -- trimming hides what the model read |
| `ToolErrorMiddleware`, in `langchain` 1.4 | Same | Turns a tool's *execution* error into an error tool message | Does not see `invalid_tool_calls`: no call is executed (its docstring) |
| A middleware of our own, per route | -- | `after_model`, to answer malformed calls (measured: it works alone and beside well-formed calls); `wrap_model_call`, to count what a call would send | Two small middlewares, each with its test |

**Decision:** two small middlewares. Nothing maintained ends a run on its
context. The project's rule says a malformed call goes back to the model, and
nothing maintained does that. Chosen by the owner for the context budget; the
rule (`graphs.md`, "Errors") decides the malformed call.

## Orchestration rung

The tool loop, unchanged: two more middlewares and a system prompt. No route
here needs a hand-written graph.

## Coverage screen

| Dimension | Mark | Note |
|---|---|---|
| Outcome -- who it is for; what observable thing says it worked | Clear | Above |
| Behaviour -- every rule falsifiable, each with a counter-example | Clear | A malformed call alone and beside a good one; exactly at the context budget; a task whose text gives orders |
| Determinism -- honestly tagged; every evaluated rule split once more | Clear | All deterministic, with fakes. The measurement informs values and asserts nothing |
| Data -- provenance, freshness, what happens when a source is withdrawn | N-A | No new data |
| Untrusted input -- anything ingested that this project did not write | Clear | Task text, through the tools: data in a tool message; the prompt says so; the adversarial case proves no effect |
| Interfaces -- a flag, env var, output schema, embedding, default or graph id | Clear | The prompt, an interface the model reads; `CONTEXT_CHARS_PER_CALL`; `ContextBudgetExceededError` |
| Failure -- what the user sees when a dependency is down | Clear | Over the context budget: a named error. A malformed call: the model corrects it within its budget, or the budget's error |
| Cost -- tokens, time, money and storage per run | Clear | The context budget bounds every call; the measurement cost 20 runs of a mini model |
| Ownership -- who decides when a requirement turns out to be wrong | Clear | The owner |

## Defect

N-A

## Open questions

| # | Question | Ask now / OPEN | Resolution |
|---|---|---|---|
| 1 | Context budget: end or trim? | Asked | End the run with an error (the owner, 2026-10-14) |
| 2 | A system prompt? | Asked | Yes, short and factual (the owner, 2026-10-14) |
| 3 | How to measure? | Asked | A small, fixed batch: N = 20 (the owner, 2026-10-14) |
| 4 | `task-store-read-only` question 6: a run's budget on what reaches the model | Resolved here | `CONTEXT_CHARS_PER_CALL`, per call: the conversation re-sent each turn is what grows |

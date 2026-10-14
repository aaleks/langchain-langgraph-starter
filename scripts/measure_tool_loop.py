"""Measure the assistant's tool loop on the owner's real model.

    uv run python scripts/measure_tool_loop.py [--repeat N]

It runs the assistant -- the owner's Open WebUI model, from the process's
settings, composed as the registry composes it -- over a seeded task list in a
temporary directory, never the owner's own list. For each of a fixed set of
questions, repeated N times, it records what each budget counts:
- model turns (MODEL_CALLS_PER_RUN), from the transcript;
- tool calls proposed (TOOL_CALLS_PER_RUN), refused ones included;
- the largest input sent to one model call, in characters
  (CONTEXT_CHARS_PER_CALL), counted with the assistant's own `call_chars`;
- the most output tokens one reply took, reasoning included
  (MODEL_OUTPUT_TOKENS);
- how the run ended.

It prints each run and the maxima, with N. Real model calls cost what the
model costs. Re-run it when the model or LangChain changes
(`docs/roadmap.md`); the budgets in `domain/agents/budgets.py` cite its
results.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage

from starter.config.settings import settings_from_process
from starter.domain.models import choose_model
from starter.domain.tasks import new_task
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.middleware import call_chars
from starter.infrastructure.agents.tools import task_tools
from starter.infrastructure.models import build_model, is_transient_failure
from starter.infrastructure.stores.tasks import TaskStore

QUESTIONS = [
    "What is open on my list?",
    "Is there anything about the passport?",
    "Which tasks are assigned to sam?",
    "Summarise everything that mentions the plumber or the car.",
    "How many open tasks do I have, and which is the oldest?",
]

SEED = [
    ("Renew passport", "sam", "Photos are in the drawer; the form needs a witness signature."),
    ("Call the plumber", "", "Kitchen tap drips. Ask for a Saturday slot, after 10am."),
    ("Book the car service", "ana", "Due at 60,000 km. Mention the rattle near the back seat."),
    ("Pay the electricity bill", "sam", ""),
    ("Buy a birthday present for Ivana", "ana", "She mentioned a book on Byzantine history."),
    ("Renew car insurance", "", "Compare at least three quotes before the 30th."),
    ("Fix the bike's rear brake", "sam", ""),
    ("Plan the weekend trip", "ana", "Check the weather and the train times on Friday."),
    ("Return library books", "", "Three books; one is overdue already."),
    ("Ask the plumber about the boiler", "sam", "It makes a knocking noise at night. " * 20),
] + [(f"Archive old document batch {n}", "", "Scan, name and file. " * 30) for n in range(1, 21)]


class Recorder(BaseCallbackHandler):
    """The largest input to one model call, attempts included: a retry re-sends
    the same input, so the maximum is the same."""

    def __init__(self) -> None:
        self.largest_input = 0

    def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
        self.largest_input = max(self.largest_input, max(call_chars(b) for b in messages))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=4)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    settings = settings_from_process()
    choice = choose_model(
        settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model
    )
    if choice != "openwebui":
        print("Open WebUI is not configured: nothing to measure (.env.example)", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="measure-") as directory:
        store = TaskStore(Path(directory) / "tasks.sqlite3")
        store.open()
        for title, assignee, notes in SEED:
            store.add(new_task(title, assignee, notes[:1000]))
        # Composed as the registry composes it -- the same tools, the same
        # factory -- not imported from it: importing the registry builds its
        # export, which opens the owner's own list.
        graph = build_assistant(
            build_model(settings), task_tools(store), transient=is_transient_failure
        )

        runs = []
        for round_ in range(args.repeat):
            for question in QUESTIONS:
                recorder = Recorder()
                turns = proposed = output = None
                try:
                    out = graph.invoke(
                        {"messages": [HumanMessage(question)]}, config={"callbacks": [recorder]}
                    )
                    replies = [m for m in out["messages"] if isinstance(m, AIMessage)]
                    turns = len(replies)
                    proposed = sum(len(m.tool_calls) + len(m.invalid_tool_calls) for m in replies)
                    output = max((m.usage_metadata or {}).get("output_tokens", 0) for m in replies)
                    outcome = "completed"
                except Exception as failure:  # recorded, never re-raised: a measurement
                    outcome = type(failure).__name__
                runs.append((turns, proposed, recorder.largest_input, output, outcome))
                print(
                    f"{round_} | {question[:40]:40} | turns {turns} | calls proposed {proposed} | "
                    f"largest input {recorder.largest_input:6} | output tokens {output} | {outcome}"
                )

    print(f"\nN = {len(runs)} runs, model {settings.openwebui_model!r}")
    # Each statistic with its own N: a run ended by a budget has no transcript,
    # so it reports its outcome and its largest input only.
    for label, column in [
        ("model turns", 0),
        ("tool calls proposed", 1),
        ("largest input", 2),
        ("output tokens, one reply", 3),
    ]:
        values = [r[column] for r in runs if r[column] is not None]
        if values:
            mean = sum(values) / len(values)
            print(f"{label}: max {max(values)}, mean {mean:.1f} (N = {len(values)})")
    print("outcomes:", {o: sum(1 for r in runs if r[4] == o) for o in {r[4] for r in runs}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

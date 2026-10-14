"""Measure the assistant's tool loop on the owner's real model.

    uv run python scripts/measure_tool_loop.py [--repeat N]

It runs the registered assistant -- the owner's Open WebUI model, from the
process's settings -- over a seeded task list in a temporary directory, never
the owner's own list. For each of a fixed set of questions, repeated N times,
it records:
- the model calls;
- the tool calls;
- the largest input sent to the model, in characters;
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
from langchain_core.messages import HumanMessage

from starter.config.settings import settings_from_process
from starter.domain.models import choose_model
from starter.domain.tasks import new_task
from starter.infrastructure.agents.factory import build_assistant
from starter.infrastructure.agents.middleware import call_chars
from starter.infrastructure.agents.tools import list_tasks, search_tasks
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
    def __init__(self) -> None:
        self.model_calls = 0
        self.tool_calls = 0
        self.largest_input = 0

    def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
        self.model_calls += 1
        self.largest_input = max(self.largest_input, max(call_chars(b) for b in messages))

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        self.tool_calls += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=4)
    args = parser.parse_args()

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
        # Composed as the registry composes it, not imported from it: importing
        # the registry builds its export, which opens the owner's own list.
        graph = build_assistant(
            build_model(settings),
            [list_tasks.build(store), search_tasks.build(store)],
            transient=is_transient_failure,
        )

        runs = []
        for round_ in range(args.repeat):
            for question in QUESTIONS:
                recorder = Recorder()
                try:
                    graph.invoke(
                        {"messages": [HumanMessage(question)]}, config={"callbacks": [recorder]}
                    )
                    outcome = "completed"
                except Exception as failure:  # recorded, never re-raised: a measurement
                    outcome = type(failure).__name__
                runs.append((round_, question, recorder, outcome))
                print(
                    f"{round_} | {question[:40]:40} | model {recorder.model_calls:2} | "
                    f"tools {recorder.tool_calls:2} | largest input {recorder.largest_input:6} | "
                    f"{outcome}"
                )

    print(f"\nN = {len(runs)} runs, model {settings.openwebui_model!r}")
    for label, value in [
        ("model calls", lambda r: r[2].model_calls),
        ("tool calls", lambda r: r[2].tool_calls),
        ("largest input (characters)", lambda r: r[2].largest_input),
    ]:
        values = [value(r) for r in runs]
        print(f"{label}: max {max(values)}, mean {sum(values) / len(values):.1f}")
    print("outcomes:", {o: sum(1 for r in runs if r[3] == o) for o in {r[3] for r in runs}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

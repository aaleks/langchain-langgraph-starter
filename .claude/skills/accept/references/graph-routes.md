# Accepting a requirement about a graph's route

Read by `/accept` when the requirement is a route through a LangGraph graph.
Part of the langgraph pack. Which routes a change must name is the route
checklist in `discover/references/orchestration-ladder.md`; this file is how
each one's test asserts it.

The text is non-deterministic; the route is not. Prove the decision behind a
route at unit level first. When the requirement is the route itself, the test
drives the compiled graph -- built the way the registry builds it, with every
model and tool replaced -- in `tests/integration/agents/`, and asserts what a
route is made of:

- **the nodes visited, in order**, from `stream_mode="updates"` or the
  checkpoints in `get_state_history()`;
- **the terminal outcome**, a status in the final state -- never the text;
- **an interrupt**: its payload, then `Command(resume=...)` on the same
  `thread_id`, and the route after it;
- **an exhausted budget**: the fake scripted to keep failing, and the terminal
  outcome the design names for it.

Script the fake model one response per call (`GenericFakeChatModel` over an
iterator of messages), so the route is the only thing left to vary.

If the graph cannot be built with a fake injected -- a model built inline, a
client constructed in a node -- that is the seam problem `/accept` names: stop
and say so. The project's architecture tests refuse the commonest forms.

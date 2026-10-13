# Intake

- **Class:** structural
- **Intent:** For the owner running the task assistant: when `.env` names an
  Open WebUI -- its URL, an API key and a model -- the registered `assistant`
  answers through that model, over Open WebUI's OpenAI-compatible API, with
  transient failures retried, each call bounded by a deadline, and the default
  suite still never calling a model. With nothing configured it keeps the
  offline model.
- **Because:** it adds the project's first model provider (`langchain-openai`)
  and its first settings -- an interface the owner writes into `.env` -- and
  the first reader of `.env` in `config/`. A provider and a settings interface
  are expensive to reverse.
- **Approved:** the owner chose the product and the provider on 2026-10-12
  ("Approval-gated tasks"; "I have openwebui installed locally, I will put in
  .env openwebui url and token and model to use"). Class and scope decided by
  the agent under the owner's standing delegation of the same day.

## Scope, against the roadmap's slice 2

Kept: `.env` read by `config/` with the environment winning; the model built
only in `infrastructure/models.py`, its provider imported inside the builder,
chosen by a factory function the registry calls; transient failures retried by
`ModelRetryMiddleware(..., on_failure="error")` on a domain predicate; a
deadline per call; a `live` run through Open WebUI; the "only `models.py`
builds a model" check extended to every module.

Moved to slice 3, the first tools, because no tool is registered before it and
each only means something with one:

- the decision on `invalid_tool_calls` -- a real model emits them only when
  tools are bound;
- `MODEL_CALLS_PER_RUN` re-measured -- with no tool, every real run is one call.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A

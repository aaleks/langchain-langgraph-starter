# Verify

- **Verdict:** DO NOT SHIP -- pass 1. Seal the default suite from LangSmith
  first (finding 1).
- **Reviewed at:** `a9b2a8f` -- the staged tree the lenses read, committed
  unchanged after they reported.
- **Evidence:** run fresh in this session, on the reviewed tree.
  - `bash scripts/check.sh`: `all checks passed`, exit 0. Architecture: 38
    passed, none skipped. `openspec validate --all --strict`: 1 passed.
    `sdd check`: OK, 3 requirements, 2 test files, both claimed. The method's
    tests: 117 OK; the manifest matches. The suite: 46 passed.
  - Mutations watched during apply: `tools=[]` in the factory fails two
    tool-loop tests; `MODEL_CALLS_PER_RUN = 9` fails both budget scenarios;
    `exit_behavior="end"` fails the first.
  - Five fresh-context lenses over `git diff --cached main` (base `70e7fa2`):
    proof (`spec-compliance`), defects (`code-reviewer`), placement
    (`architecture-guardian`), `graph-architecture-guardian` and
    `graph-eval-auditor`. Their probes ran in the scratchpad, with the
    network refused and any tracing pointed at `127.0.0.1:9`.

## Findings

Six MAJOR and fourteen MINOR findings. No BLOCKER: no non-negotiable is
violated. Duplicates across lenses are merged, and the lenses that found each
one are listed.

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 1 | MAJOR | defects, graph-arch, proof | **The default suite is not sealed from LangSmith.** This change is the first to run LangChain code in it. With `LANGSMITH_TRACING=true` in the shell, a probe recorded `GET /info` and `POST /runs/multipart` (about 14 KB, the run's inputs and outputs) for each run. The upload runs on a background thread, so the offline test's guard misses it, and the test passed. `clean_env` clears nothing, because `.env.example` lists no variables. Every green run in this session ran under `.claude/settings.json`'s local-only `env`; a person's shell or CI has nothing equivalent. | `tests/conftest.py`; `scripts/check.sh:43` | Apply the local-only environment before langchain_core is imported, and disable the `langsmith` pytest plugin. Add a check that fails when the suite does not run in that environment |
| 2 | MAJOR | graph-eval | **ASSISTANT-TOOL-LOOP overclaims.** It says "execute every tool call the model proposes". A call to an unknown tool (`multiply`), or with arguments the schema refuses (`add(a="x")`), is not executed: the model gets back a tool message with `status="error"`. That route, the model-recoverable class, is unnamed and untested. The design's N-A reason for it ("needs a real model") is wrong: a scripted fake reaches it | spec `ASSISTANT-TOOL-LOOP`; `design.md` Errors | Scope the requirement to valid calls to offered tools. Add a requirement for the error route and its scenarios. Correct the design |
| 3 | MAJOR | proof, graph-eval, placement | **Nothing proves the registered graph comes from the factory.** If the registry called `create_agent(build_offline_model(), tools=[])` directly, the served graph would have no budget, and every test would stay green. `uncompiled_registrations` checks the type, not the origin. No check confines compiling to `factory.py`, or `create_agent` to `infrastructure/agents/`, now that `langchain` is installed | `registry.py:14`; `test_registered_assistant.py`; `contract.py` | A scenario: the registered graph's nodes equal the factory's. An architecture check, fixture-proved: graphs are compiled only in `factory.py`, and `langchain.agents` is imported only under `infrastructure/agents/` |
| 4 | MAJOR | proof | **"Hand each result back to the model" is never asserted.** A probe middleware stripped every tool message from the model's input, and scenario 1 still passed. `ScriptedChatModel` records nothing of what it is given | `tests/conftest.py`; `test_assistant.py` | The fake records each call's input, and the tools it was bound to. Assert that the second call's input ends in the tool message `5` answering the call's id |
| 5 | MAJOR | proof | **The offline test builds the registered graph before the network is refused,** because the `registry` fixture sets up before `no_network`. It also runs the package-imported graph, not the one `langgraph.json` resolves to. A model that connects when it is constructed would pass | `test_registered_assistant.py:34-40, 80-88` | Refuse the network first. Then load the graph through `langgraph.json`, so that construction and the run both happen under the guard |
| 6 | MAJOR | graph-eval | **The "unexpected" class has no proof.** The design says a tool's exception is raised. That holds only because of `langgraph-prebuilt`'s default (`_default_handle_tool_errors` re-raises), and the inherited lessons say defaults are the trap. A model's exception propagating is untested too | `design.md` Errors | A requirement: an exception from a tool or the model propagates to the caller. Scenarios with a raising fake tool and a raising fake model |
| 7 | MINOR | graph-eval | The route checklist is not recorded route by route: refusal and tool denial appear nowhere, and the rest are N-A only by implication | `design.md` | A route table, one row per route |
| 8 | MINOR | graph-eval | `invalid_tool_calls` -- arguments the model emitted unparseably -- end the run like an answer (`human, ai`, empty content). That is a malformed output that reads like an answer | factory | A decision: terminal error, or handed back. OPEN until a real model can produce one -- recorded with an owner and a trigger |
| 9 | MINOR | proof, graph-eval | The two-calls scenario does not count the tool messages (a dict keyed by id would collapse a duplicate). It does not assert the transcript shape or the model call count | `test_assistant.py:44-58` | Assert the list of message types and `model.calls` |
| 10 | MINOR | proof | `MODEL_CALLS_PER_RUN` is never asserted. The tests use the literal 10, so a factory hard-coding `run_limit=10` while the constant drifted would pass | `test_assistant.py` | Assert `MODEL_CALLS_PER_RUN == 10` and `model.calls == MODEL_CALLS_PER_RUN` |
| 11 | MINOR | proof, defects, graph-arch | The design's numbers are wrong. The budget takes 40 supersteps, not about 30: a `recursion_limit` of 41 or more lets the budget fire first. The 9,999 ceiling is set by langchain's `create_agent`, not by langgraph. A caller's `recursion_limit` below 41, or `LANGGRAPH_DEFAULT_RECURSION_LIMIT`, makes "never at the step ceiling first" false | `design.md`; spec | Scope the statement to the ceiling `create_agent` sets, and state the floor. Correct the design |
| 12 | MINOR | proof, defects, graph-arch, placement | The offline model's fresh message ids are guarded only by a comment, and `design.md` still prescribes the broken `itertools.cycle([AIMessage])`. A probe showed it gives `human, ai, human`: the second answer replaces the first | `models.py:28`; `design.md:33` | A scenario: two turns of the registered graph give `human, ai, human, ai` with distinct ids. Correct the design |
| 13 | MINOR | proof | The registered graph has no tools, and no requirement claims it. REGISTERED's counter-example is decoration: `built is not registry.assistant` holds for any implementation, and its export scan filters on `CompiledStateGraph` rather than `Pregel` | `test_registered_assistant.py:90-99` | Counter-example: a factory graph built with a tool has a `tools` node, and the registered graph has none. Filter on `Pregel` |
| 14 | MINOR | defects | Nothing guards `LANGGRAPH_CLI_NO_ANALYTICS == "1"` in `langgraph_validate`. Change it to `"true"` and both validate tests stay green, while every run from a person's shell POSTs analytics | `contract.py` | A test that captures the `env` handed to `subprocess.run` |
| 15 | MINOR | graph-arch | "Tool calls are bounded by model calls" is false: one model message can propose any number of calls. There is no tool-call limit | `design.md` | Correct the design. A tool-call budget arrives with the first real tool |
| 16 | MINOR | graph-eval | The fake is trustworthy on `invoke` only. Its inherited `_stream` drops `tool_calls`, so 1b's "a fake-model run streams" would crash, or turn a proposal into an answer. Its `bind_tools` discards the tools | `tests/conftest.py` | Record the bound tools now. Name the streaming limit in the fixture, and hand it to 1b |
| 17 | MINOR | graph-eval | The trigger for adversarial cases -- "the first real model or tool" -- is tied to nothing that would fail or remind anyone | `frame.md`; `docs/roadmap.md` | Make it a precondition of the first change that installs a provider, in the roadmap |
| 18 | MINOR | placement | The root `conftest.py` imports langchain_core for every test, about 0.6 s, so even a pure domain unit run pays it | `tests/conftest.py:21-23` | Move the fakes into a helper module that only the agent tests import |
| 19 | MINOR | placement | The registry composes the model and tools; `graphs.md` gives that to the factory ("settings in"). Once `config/` arrives, choosing a model from settings in an import-time registry is the `.env` trap | `registry.py`; `graphs.md:36` | Nothing here. 1b points settings-driven composition at a factory function |
| 20 | MINOR | placement | "`models.py` is the only place a model is built" is only partly enforced, and `models.py` imports langchain_core at module scope | `contract.py`; `models.py` | With the first provider: extend the check, and import the provider inside its builder |

Also reported, not counted: scenarios without a WHEN clause (cosmetic); the
roadmap calls 1a "landed" while it is in flight -- true on merge.

## Not checked

- `agent-capability-auditor`: the change registers no tool, grants no
  permission and adds no network access; the only tool is a test fake.
- `durability-auditor`: no checkpointer, no state contract, no interrupt, no
  thread handling. The registry compiles without a checkpointer.
- The local server: not started. That is 1b.
- Async runs (`ainvoke`, streaming): not exercised. The server runs graphs
  async -- 1b's smoke run.

## Pass 2 -- the fix diff `a9b2a8f..cf4a2e1`

Three fresh-context lenses: proof (`spec-compliance`), defects
(`code-reviewer`), and `graph-eval-auditor`. The first launch of all three
stopped on a session limit before reporting; they were re-run in full.

- **Pass 1 resolved:** every MAJOR (1-6) and every MINOR the lenses rechecked
  (7-13, 16, 17). The seal was probed from a hostile shell (tracing on, a key
  exported): `uv run pytest` gave 64 passed and 0 connect attempts, while the
  same graph run outside pytest made 16.
- **No BLOCKER, no MAJOR.** Fifteen MINOR findings, merged here:

| # | Severity | Lens | Finding | Where | Fix |
|---|---|---|---|---|---|
| 21 | MINOR | graph-eval, proof | TOOL-ERROR's refused-arguments route (a different library path from an unknown tool) is not asserted to hand the error to the model's next call, or to carry on: a middleware ending the run there kept all four tests green | `test_assistant.py:105-113` | Assert the transcript shape and `model.seen[1][-1]` |
| 22 | MINOR | proof | With two results, nothing checks that both reach the model: a middleware keeping only the last one kept the suite green | `test_assistant.py:56-72` | Assert the model's last two inputs |
| 23 | MINOR | proof | The registered export could lower its own step ceiling (`.with_config(recursion_limit=5)`) and stay green, and nothing pins the 9,999 the budget statement cites | `registry.py:14`; acceptance | Compare the step ceilings; pin 9,999 |
| 24 | MINOR | proof | The offline test's guard misses network access at import of modules already cached by earlier tests: a `models.py` connecting at import was caught only when the test ran alone | `test_registered_assistant.py:100-109` | Drop the cached `starter.infrastructure` modules before loading |
| 25 | MINOR | defects | The seal check cannot fail in an agent session, whose settings already set every variable: removing the seal keeps it green there | `test_local_only.py:25-30` | Prove the seal in a subprocess with tracing switched on |
| 26 | MINOR | defects | `graphs_compiled_outside_factory` misses `create_agent as make` | `contract.py` | Track the local names factories are imported under |
| 27 | MINOR | defects | It misses `builder.compile()` in a module that imports the builder rather than a runtime -- the usual shape of a hand-written graph | `contract.py` | Flag `.compile()` anywhere under `infrastructure/agents/`, with an exempt-receiver list |
| 28 | MINOR | defects | It flags `re.compile` in a module that also imports a graph runtime -- the first tool module with a regex would fail the build | `contract.py` | The same exempt-receiver list |
| 29 | MINOR | defects | `agent_runtime_imports_outside_agents` misses `from langchain import agents` | `contract.py` | Yield `module.name` for each `ImportFrom` alias |
| 30 | MINOR | graph-eval, proof | TOOL-LOOP's wording settles the OPEN `invalid_tool_calls` question by default ("answers without proposing a tool call"); the OPEN items carry no Review by date | spec; `frame.md` | Scope the clause; owners and dates |
| 31 | MINOR | graph-eval | The timeout row says N-A though a model's `TimeoutError` is proved to propagate, and no deadline exists; the first-provider list has retry but no timeout; refusal names no owning slice | `design.md`; `docs/roadmap.md` | Correct the rows; add the timeout |
| 32 | MINOR | graph-eval | The fake's streaming limit is mis-stated: for a proposal with no text, a stream raises (`No generation chunks were returned`) rather than turning it into an answer | `tests/fakes.py`; roadmap | State the measured behaviour |

Also noted, not counted: `-p no:langsmith_plugin` is extra protection, not the
seal -- with the plugin forced on, langsmith 0.14.7 still read no switch at
load (pyproject's comment overstates it); TOOL-ERROR's counter-example keys
tool messages by id, which its scenario does not ask to count.

**Pass 2 verdict:** shippable -- no BLOCKER, no MAJOR. The MINORs are fixed
before landing, in a separate commit, and that diff is read in pass 3.

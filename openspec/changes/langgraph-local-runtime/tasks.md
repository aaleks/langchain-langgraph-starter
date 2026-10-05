# Sequence

- **Order:** the status defect first, because this change is the first to
  declare `skip_specs` and would otherwise misreport itself. Then the server
  wrapper, whose environment the agent's settings must equal. Then pack
  seeding, which ships both. The project's checks, rules and wiring come after
  the method requirements they describe.
- **Wiring point:** `sdd.sh install --packs langgraph` -- the entry point
  through which a new project receives the wrapper and the settings.
- **Story test:**
  `.claude/sdd/tests/test_distribution.py::TestALangGraphInstallIsLocalOnly`.
  It stays red until a fresh install seeds a wrapper that starts the server
  local-only, and settings that deny the hosted commands.

## 1. HOOKS-NEXT-STAGE (modified -- the defect in frame.md)

- [x] 1.1 /accept HOOKS-NEXT-STAGE -- the skip_specs scenario is red for the right reason
  (`AssertionError: 'design' != 'specs'` -- the defect itself; the counter-example already green)
- [x] 1.2 /tdd -- every scenario, counter-example included, asserted and green
  (`test_status.py`: 7 tests OK; this change now reads `specs~ ... -> next: apply`)

## 2. LOCAL-SERVE-LOOPBACK

- [x] 2.1 /accept LOCAL-SERVE-LOOPBACK -- red: the wrapper does not exist
  (`FileNotFoundError: ... .claude/sdd/seeds/serve.sh` in each of the five tests)
- [x] 2.2 /tdd -- every scenario, counter-example included, asserted and green
  (`test_serve.py`: 5 tests OK. Hand mutations caught: bind 0.0.0.0, browser opens, --tunnel passed on, missing config tolerated)

## 3. LOCAL-SERVE-ENVIRONMENT

- [x] 3.1 /accept LOCAL-SERVE-ENVIRONMENT -- red for the right reason
  (`FileNotFoundError: ... seeds/serve.sh` -- nothing yet sets the environment)
- [x] 3.2 /tdd -- every scenario, counter-example included, asserted and green
  (2 tests OK. Caught: a key left as exported, the endpoint not pointed at the closed port)

## 4. LOCAL-SERVE-REFUSALS

- [x] 4.1 /accept LOCAL-SERVE-REFUSALS -- red for the right reason
  (`FileNotFoundError: ... seeds/serve.sh` -- nothing yet refuses)
- [x] 4.2 /tdd -- every scenario, counter-example included, asserted and green
  (4 tests OK. Caught: env key allowed, credential check off, tracing check off, values printed)

## 5. LOCAL-AGENT-SETTINGS

- [x] 5.1 /accept LOCAL-AGENT-SETTINGS -- red: the settings additions do not exist
  (`FileNotFoundError` on `seeds/settings.langgraph.json`, then on the wrapper)
- [x] 5.2 /tdd -- every scenario, counter-example included, asserted and green
  (4 tests OK. Deleting any one of the nine deny rules fails a test; an env drift between settings and wrapper fails one)

## 6. DIST-PACK-SEEDS

- [x] 6.1 /accept DIST-PACK-SEEDS -- red, and the story test written and red
  (`AttributeError: 'Report' object has no attribute 'merge_by_hand'`; serve.sh not seeded: `False is not true`; story test: `0 != 127`, bash finds no seeded wrapper. `test_without_the_pack_neither_is_seeded` green already -- today's behaviour, kept)
- [x] 6.2 /tdd -- every scenario, counter-example included, asserted and green
  (`test_distribution.py`: 6 + story OK, 108 method tests OK. Caught: every pack's seeds always, env conflict tolerated, unknown key dropped, merge not reported, unseeded not reported, always asks to merge, pack rules replace core)

## 7. The project's architecture checks (exempt: checks of the checkers)

- [x] 7.1 Registration: `langgraph.json` resolves to registry exports, stable ids, no `env` -- red on fixtures, skipped here until a graph exists
  (mutants caught: env allowed, any id, any path is the registry, unbound name accepted; a planted bad `langgraph.json` failed the real check, then was removed)
- [x] 7.2 The agents adapter imports only its allowlist -- red on a fixture
  (fixture finds exactly `{langchain_openai, httpx}`; mutant `httpx allowed` caught; a planted `import httpx` failed the real check)
- [x] 7.3 No model built inline in the agents adapter -- red on a fixture
  (fixture finds a.py, b.py, c.py and not models.py; mutants `model= ignored` and `scans beyond agents` caught; a planted `init_chat_model` failed the real check. `uv run pytest tests/architecture`: 30 passed, 3 skipped with reasons)

## 8. The pack's rules and the stage templates (prose: no test can prove it)

- [x] 8.1 `rules/langgraph/graphs.md` -- structure, node kinds, error classes, subgraphs, persistence security, test tiers
  (API names checked against langgraph 1.2.13 / langgraph-checkpoint 4.2.0 / langchain-core 1.6.6: `RetryPolicy`, `timeout=` async only, `EncryptedSerializer`, `LANGGRAPH_STRICT_MSGPACK`, `GenericFakeChatModel`)
- [x] 8.2 `rules/langgraph/runtime.md` -- the local runtime, what replaces Studio, the connection probe
  (`langgraph_sdk` 0.4.5 calls checked: `threads.create`, `runs.wait(command=)`, `runs.stream`, `assistants.get_graph(xray=)`, `threads.get_history`)
- [x] 8.3 `packs/langgraph.md`, the orchestration ladder, the four auditors
- [x] 8.4 `design.md` template and the schema's design instruction; `/accept` route criteria
  (the route criteria live in `accept/references/graph-routes.md`, a langgraph-pack file -- a core skill only points at it, as `/discover` does for the ladder; `openspec schema validate sdd-proof`: valid)

## 9. Wiring

- [x] 9.1 The project takes its own pack: `.claude/settings.json`, `scripts/serve.sh`, `.gitignore`
  (settings written by `seeded_settings(., [python, langgraph])` -- what a fresh install seeds; `scripts/serve.sh` a copy of the seed; no tracked file matches the new ignores)
- [x] 9.2 CLAUDE.md, README, roadmap slices 1 and 3, the architecture overview
  (also slice 5: tracing local, never LangSmith; `.env.example` says no LangSmith variable belongs there)
- [x] 9.3 The story test is green through `install`
  (`TestALangGraphInstallIsLocalOnly` OK within 109 method tests; and through the CLI: `sdd.sh install <scratch> --packs python,langgraph` seeded `scripts/serve.sh` and settings with 16 deny rules and 13 env variables; the installed copy's selftest OK; into a project with its own settings, the file was untouched and `seeds/settings.langgraph.json` reported for a merge by hand)
- [x] 9.4 The real server, started by the seeded wrapper under strace with LangSmith keys exported: zero outbound connections
  (langgraph-cli 0.4.32 / langgraph-api 0.15.1; shell exported `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`,
  `LANGGRAPH_CLOUD_LICENSE_KEY`, `LANGSMITH_TRACING=true`, `LANGCHAIN_TRACING_V2=true`,
  `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`. Server on `http://127.0.0.1:8123`, "skipping metadata loop",
  a run returned `{"text":"LOCAL ONLY"}`; `strace -f -e trace=connect`: 0 connect() calls in all.
  The banner still prints a Studio link to smith.langchain.com -- printed, never opened)
- [x] 9.5 Release: VERSION 0.3.0, CHANGELOG, deferred register, manifest; the full check passes (`[commands].check` in sdd.toml)
  (manifest: 107 files, version 0.3.0; `bash scripts/check.sh`: all checks passed -- 109 method tests, 33 method requirements traced, 30 passed and 3 skipped in the suite; shellcheck clean on every script)

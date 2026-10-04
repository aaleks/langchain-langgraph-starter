# Deferred -- real, not now, and what brings each back

Every idea here is sound for some system. None is in the method yet, because
nothing in a typical project using it has the property that makes it matter.
Each row names that property. Review this register at every method release: a
trigger that has quietly fired is a finding.

| Deferred | Brought back when |
|---|---|
| A security-verification lane and an adversarial corpus beyond one case | a capability gains write-capable tools, real credentials, or a second tenant |
| A production logging and audit contract; detection and response | the first deployed service with users who are not its developers |
| Guardrail and policy frameworks (NeMo Guardrails, Presidio, OpenTelemetry, OPA) | a named problem in hand that build-or-adopt cannot answer locally -- OpenTelemetry first |
| Rollout, rollback, on-call, recovery objectives | anything deployed on a schedule |
| SBOM, signing, dependency scanning, hardened CI | a released artifact someone else installs |
| Data governance and a corpus quality lifecycle | a corpus not reproducible from public sources, or holding anyone else's data |
| Agent and MCP capability manifests as a standalone artifact | the first tool with a side effect outside the repository (the langgraph pack's capability auditor covers the in-repo case) |
| SLOs, capacity, back-pressure | a latency or availability promise made to anyone |
| Runbooks, dashboards, escalation | someone other than the author has to diagnose a failure |
| OpenAPI and breaking-change diffs | an interface another system consumes |
| A layered documentation product | the method gains users who are not its author |
| Assurance profiles and a production-readiness block | **refused**, not deferred: the intake classes and the coverage screen replaced them |

The one supply-chain control that is not deferred: a **protected default
branch**, with required review and CI an agent cannot edit. Without it the edit
guards are the only line, and they are a habit guard, not a boundary.

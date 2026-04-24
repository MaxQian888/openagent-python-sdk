## Why

The SDK ships a minimal `examples/multi_agent/` that shows `agent_router.delegate` / `transfer` at the API level (4 toy agents, mock + real demo), but there is no "production-density" reference comparable to `examples/production_coding_agent/` for multi-agent use cases. The archived spec `agent-router` promises three `session_isolation` modes (`shared` / `isolated` / `forked`), depth limiting, `AgentNotFoundError`, and `default_child_budget` fallback — the current minimal example exercises only `isolated`. Users who want to build real multi-agent apps (support, triage, operations) get no worked example showing how to wire `deps`, nested delegation, failure paths, and session topology into an app-defined protocol layer.

This change adds a customer-support triage example — `examples/multi_agent_support/` — that mirrors `production_coding_agent`'s layering (app-defined protocol on top of SDK seams) and deliberately exercises every contract in the `agent-router` spec plus the session-reentry / fork behavior. The existing `examples/multi_agent/` stays as a short feature reference; the new one becomes the flagship multi-agent demo referenced from docs.

## What Changes

- **NEW** `examples/multi_agent_support/` — a customer-support triage app with four agents wired through the `agent_router` seam:
  - `concierge` (entry / orchestrator) — greets user, classifies intent, delegates data lookups to `account_lookup`, transfers to `refund_specialist` for refund requests, transfers to `tech_support` for technical issues.
  - `refund_specialist` — handles refund requests; delegates to `account_lookup` with `session_isolation="shared"` so the refund reasoning shares the ongoing customer conversation.
  - `tech_support` — handles technical issues; uses `session_isolation="forked"` when delegating exploratory diagnostic branches to `account_lookup`, so dead-end hypotheses never pollute the main session.
  - `account_lookup` — leaf specialist with app-defined tools that read from an in-memory `CustomerStore` dep; demonstrates how data-fetch specialists compose via `delegate`.
- **NEW** `examples/multi_agent_support/app/` — app-defined protocol layer: `deps.py` (`SupportDeps` with `CustomerStore` + `TicketStore`), `plugins.py` (tools: `lookup_customer`, `find_orders`, `issue_refund`, `open_ticket`, plus router-bound tools `route_to_refund`, `route_to_tech`, `consult_account_lookup`), `protocol.py` (pydantic envelopes rode on `RunContext.state` / `context_hints` — intent, ticket draft, delegation trace).
- **NEW** `examples/multi_agent_support/agent_mock.json` / `agent_real.json` — mock config wires `provider: mock` with scripted responses to drive each flow deterministically; real config uses the MiniMax Anthropic-compatible endpoint same as other examples. Both set `multi_agent.enabled: true`, `max_delegation_depth: 3`, `default_child_budget`.
- **NEW** `examples/multi_agent_support/run_demo_mock.py` — offline end-to-end scenario runner that drives 4 scripted conversations covering: (a) refund flow (transfer + nested shared delegate), (b) tech issue with forked diagnostic branches, (c) depth limit enforcement (`DelegationDepthExceededError`), (d) unknown agent error path (`AgentNotFoundError`). All scenarios run in CI via pytest.
- **NEW** `examples/multi_agent_support/run_demo_real.py` — LLM-driven entry point for interactive exploration; requires `MINIMAX_API_KEY`. Prints events via the `rich_console` event bus.
- **NEW** `tests/integration/test_multi_agent_support_example.py` — exercises every scenario in `run_demo_mock.py` against real builtins (no mocks except the LLM provider), asserts: child run ids, `metadata["handoff_from"]`, session-mode snapshot correctness (`forked` sees parent history but parent post-fork writes don't leak), depth metadata propagation, error types.
- **UPDATE** `examples/multi_agent/README.md` — add a one-paragraph pointer to the new production-style example and label itself as the short feature-reference demo.
- **UPDATE** `docs/examples.md` + `docs/examples.en.md` — add a new section for `multi_agent_support` modeled on the `production_coding_agent` section; update the "只保留两组" language to acknowledge the multi-agent flagship.
- **NEW** `docs/multi-agent-support-example.md` + `.en.md` — standalone guide walking through the four flows, the app-defined protocol, and which part of the `agent-router` spec each flow exercises.

No changes to `openagents/` source code. No new seam. No spec-level behavior change in existing capabilities.

## Capabilities

### New Capabilities

- `multi-agent-support-example`: the structural contract of the new example — which agents exist, what each `session_isolation` mode is demonstrated by, which error paths must be covered, which deps layer is expected, and what the mock-driven integration test must verify. Registering this as a capability makes "completeness" machine-checkable on future maintenance.

### Modified Capabilities

None. The `agent-router` spec is unchanged; the example only consumes it.

## Impact

- **Code**
  - NEW `examples/multi_agent_support/` — new package with `__init__.py`, `app/`, mock + real configs, two run_demo scripts, a small `README.md`.
  - `examples/multi_agent/README.md` — one-paragraph edit to point at the new flagship.
  - Zero changes to `openagents/` kernel / seams / builtin plugins.
- **Tests**
  - NEW `tests/integration/test_multi_agent_support_example.py` — one integration test file covering the four mock scenarios end-to-end.
  - `tests/conftest.py` already puts repo root on `sys.path`, so the new example's plugins resolve via `examples.multi_agent_support.app.plugins.<Class>` — no conftest change needed.
- **Dependencies** — none added. Uses existing `pydantic`, `rich`, `anthropic` via existing providers.
- **Docs**
  - NEW `docs/multi-agent-support-example.md` + `.en.md`.
  - `docs/examples.md` + `.en.md` — add a section, adjust the "只保留两组" claim.
  - `docs/seams-and-extension-points.md` — unchanged (no new seam).
- **Runtime / kernel** — zero.
- **Coverage floor** — the new example code is exercised by the integration test; projected line coverage for `examples/multi_agent_support/app/plugins.py` stays above the 90 % floor. `coverage omit` entries are not needed.
- **Config** — no changes to `pyproject.toml` except possibly adding `tests/integration/test_multi_agent_support_example.py` under `tool.pytest.ini_options` only if marker conventions require it (current convention does not).

## Context

`examples/multi_agent/` is a 4-file feature reference (≈200 lines) that demonstrates the `agent_router` seam at the API level: two orchestrator/child pairs, a mock demo, a real demo, scripted scenarios. It is deliberately minimal — it does not model any domain, does not use `deps`, does not exercise `session_isolation="shared"` or `"forked"`, does not demonstrate nested delegation, does not cover `DelegationDepthExceededError` or `AgentNotFoundError` paths, and is not referenced from `docs/examples.md` (which currently claims only `quickstart` and `production_coding_agent` are maintained).

`examples/production_coding_agent/` is the SDK's flagship "production-density" single-agent example: it layers an app-defined protocol (task packets, memory, delivery artifacts) on top of SDK seams, uses typed `deps`, ships a benchmark harness, and is the canonical reference for "what a real app looks like on this kernel." There is no multi-agent equivalent.

Stakeholders: users building support / operations / research apps on the SDK. Constraint: zero changes to `openagents/` — the `agent-router` spec was finalized in the `fix-multi-agent-p0-gaps` archive (2026-04-17) and does not need revision; this change lives entirely under `examples/` + `docs/` + `tests/`.

## Goals / Non-Goals

**Goals:**

1. Ship a customer-support multi-agent example that mirrors `production_coding_agent`'s layering: app-defined protocol (`deps`, context envelopes, app-level tools) on top of SDK seams.
2. Cover every contract currently registered in the `agent-router` spec end-to-end: `delegate`, `transfer`, all three `session_isolation` modes, `max_delegation_depth` enforcement, `AgentNotFoundError`, `default_child_budget` fallback, `HandoffSignal` metadata propagation.
3. The mock-driven end-to-end scenarios run offline in CI with deterministic assertions — not smoke tests, but proper integration tests that fail if the example regresses.
4. Keep the existing minimal `examples/multi_agent/` as a short feature-reference sibling; update its README to point at the new production example.
5. Docs: a standalone guide (`docs/multi-agent-support-example.md` + `.en.md`) and a section in `docs/examples.md`.

**Non-Goals:**

1. No changes to `openagents/` kernel / interfaces / builtin plugins. No new seam.
2. Not a framework-wide "multi-agent team" abstraction — the kernel remains a single-agent runtime, and product orchestration lives in app code (CLAUDE.md rule). The example demonstrates how to build that layer, not ship it as framework code.
3. No real-world customer-data integration. `CustomerStore` / `TicketStore` are in-memory fakes seeded from the config; real apps would swap these for actual services.
4. No CLI wizard UI (this is not a `pptx_generator`-style Rich TUI). The `run_demo_real.py` prints event-bus output via `rich_console` and feeds prompts stdin-style; the focus is the multi-agent orchestration, not terminal UX.
5. No benchmark harness. Integration tests provide the regression floor; a benchmark similar to `production_coding_agent/run_benchmark.py` is out of scope for this change (can be added later).

## Decisions

### Decision 1: Domain — customer-support triage

**Rationale:** This domain naturally exercises all three `session_isolation` modes:

- `shared` fits a sub-specialist that must see the ongoing customer conversation (refund eligibility depends on recent messages).
- `isolated` fits a leaf lookup that only needs a query (account lookup).
- `forked` fits exploratory diagnostic branches (tech support testing hypothesis A while keeping the main session clean for hypothesis B).

It also naturally separates `delegate` (concierge consults account_lookup) from `transfer` (concierge hands the whole conversation to refund_specialist because the problem is now squarely billing).

**Alternative considered:** research-team fan-out (one lead, N parallel analysts). Rejected because the framework currently exposes sequential `delegate` only — parallel delegation is an app-level concurrency layer and would make the example about `asyncio.gather`, not about the seam contract. Can be a future sibling example.

### Decision 2: Directory layout mirrors `production_coding_agent/`

```
examples/multi_agent_support/
├── __init__.py
├── README.md
├── agent_mock.json
├── agent_real.json
├── run_demo_mock.py
├── run_demo_real.py
└── app/
    ├── __init__.py
    ├── deps.py        # SupportDeps (CustomerStore, TicketStore)
    ├── plugins.py     # ToolPlugin subclasses (lookup_*, route_*, consult_*)
    └── protocol.py    # pydantic envelopes (CustomerIntent, TicketDraft, DelegationTrace)
```

**Rationale:** Users who already read `production_coding_agent` see an isomorphic tree and can reason about the new example by analogy. Keeping the app layer under `app/` (not flat) signals "this is an app-defined middle protocol, not SDK code."

**Alternative considered:** Flat layout like the current minimal `multi_agent/`. Rejected — the whole point of this example is to show the layering.

### Decision 3: Four agents, not three or five

The four agents (`concierge`, `refund_specialist`, `tech_support`, `account_lookup`) give:

- Two agents that `transfer` targets (`refund_specialist`, `tech_support`).
- One shared leaf specialist (`account_lookup`) that demonstrates how the same agent is called with different `session_isolation` modes by different callers (concierge: `isolated`, refund_specialist: `shared`, tech_support: `forked`).
- A nested-delegation path: `concierge → account_lookup → (no further)` OR `concierge → transfer to refund_specialist → delegate to account_lookup (shared)`. Depth never exceeds 2 in happy-path; the depth-limit scenario forces a synthetic loop `account_lookup → delegate to account_lookup → ...` under `max_delegation_depth=3` using a "verify another account" tool added specifically for the error scenario.

**Rationale:** Fewer than four cannot both demonstrate all three isolation modes and the depth error. More than four adds agents that duplicate existing roles and bloats the config without adding seam coverage.

### Decision 4: Keep the existing `examples/multi_agent/` alongside the new one

**Rationale:** It serves a legitimate purpose as a "here is the seam in 100 lines" quick reference. Deleting it would remove a useful learning on-ramp. The README update marks it as "minimal feature reference — for the production-style example see `multi_agent_support/`."

**Alternative considered:** Rename to `examples/multi_agent_basics/` to make the distinction immediate. Rejected — breaks the archived change reference in git history and requires updating the `fix-multi-agent-p0-gaps` archive. One-line README pointer is sufficient.

### Decision 5: Scripted mock LLM responses via a custom `LLMProvider`

The builtin `mock` provider echoes input or returns a canned response — it cannot drive a ReAct loop that must produce deterministic `tool_use` blocks for each scenario. We need per-scenario scripted responses.

**Approach:** a thin `ScriptedMockProvider` in `examples/multi_agent_support/app/plugins.py` that subclasses `LLMProvider` (or wraps the existing `mock` provider via config) and returns a configured sequence of messages keyed by `(agent_id, step_index)`. The mock config points each agent at a different script.

**Alternative considered:** Use the existing `mock` provider's `canned_responses` list. Rejected — the canned-response list is per-provider-instance; each agent gets its own provider instance in current wiring, so we would need 4 distinct provider configs with carefully ordered scripts that break if any internal ReAct retry re-uses the same response slot. A scripted provider keyed on `(agent_id, step)` is robust and self-documenting.

**Subdecision:** If inspection shows the existing `mock` provider supports per-agent scripted responses via a `script` or `by_agent` field, reuse it (the builtin may have grown such a field since the last audit). The implementation plan calls this out explicitly so the TDD step verifies current provider capabilities before building a new one.

### Decision 6: App-defined protocol rides on `RunContext.state` and `context_hints`

Per `CLAUDE.md`, product semantics (envelopes, planner state) live in app code via `RunContext.state` / `.scratch` and `RunRequest.context_hints`, never in the kernel.

- `SupportDeps` (attached via `RunRequest.deps`) carries the shared `CustomerStore` + `TicketStore`.
- `CustomerIntent` (pydantic model, in `protocol.py`) is computed by the concierge pattern and stashed on `ctx.state["intent"]`; downstream tools read it.
- `DelegationTrace` (pydantic model) records every delegate/transfer for observability; written by the router-bound tools via `ctx.state.setdefault("trace", []).append(...)`.

**Rationale:** Same mental model as `production_coding_agent`. No new seam, no new metadata key on `RunContext` — only `state` keys, which are app-owned.

### Decision 7: Integration test is the regression floor, not run_demo_mock.py

`run_demo_mock.py` prints human-readable output and exits 0 on happy path. It's not a test — it's a scenario driver. `tests/integration/test_multi_agent_support_example.py` imports the same scenario functions from `run_demo_mock.py` (or a shared `scenarios.py`) and asserts:

- Scenario 1 (refund flow): parent run ends with `stop_reason=COMPLETED`, `metadata["handoff_from"]` equals the refund_specialist's child `run_id`, ticket store has one `refund` ticket.
- Scenario 2 (tech flow, forked diagnostic): two forked child sessions exist in session_manager.list_sessions(); each has a distinct `session_id` matching `{parent}:fork:*`; parent session's post-fork writes absent from child snapshots.
- Scenario 3 (depth limit): calling the synthetic loop tool with `max_delegation_depth=3` raises `DelegationDepthExceededError(depth=3, limit=3)`; parent run's `stop_reason=ERROR` with error metadata naming the exception.
- Scenario 4 (unknown agent): a tool that passes an invalid `agent_id` to `router.delegate` causes `AgentNotFoundError("missing_agent")` to surface in the parent `RunResult.error`.

**Rationale:** Examples that are only smoke-tested drift — this is how the archived pptx example accumulated gaps. A proper integration test locks behavior.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Scripted mock LLM becomes brittle — a ReAct retry reorders steps and the script breaks | Keyed by `(agent_id, step_index)` with a fallback "unexpected step" message that makes the failure mode visible, and an integration-test assertion on step count per agent so any drift fails CI |
| The new example drifts from the `agent-router` spec on future kernel refactors | The new capability spec (`multi-agent-support-example`) encodes "MUST demonstrate each isolation mode / error path" so `openspec validate` plus the integration test catches regressions |
| "Production-density" expands scope into wizard UX territory | Non-Goal 4 explicit; `run_demo_real.py` keeps an event-bus-driven print loop and does not build a TUI |
| Two multi-agent examples confuse users about which to read | `examples/multi_agent/README.md` gets a one-paragraph "for the production-style version see ..." banner; `docs/examples.md` lists the new one as the recommended starting point for multi-agent work |
| Integration test runtime grows CI | All four scenarios run with the scripted provider, no network calls; budget: ≤3 s total, comparable to `test_pptx_generator_example.py` |
| `fork_session` snapshot assertion depends on internal session-manager state | Use the public `SessionManagerPlugin.load_messages` / `get_artifacts` APIs per the spec; do not introspect private fields |

## Migration Plan

None. This change only adds files; the existing `examples/multi_agent/` is preserved (with a one-line README update). No database migrations, no API changes, no deprecations.

If users were pinning imports like `from examples.multi_agent import ...` they continue to work. The new example is reachable at `examples.multi_agent_support`.

## Open Questions

1. **Does the existing builtin `mock` provider support per-agent scripted responses?** Implementation task 1 must audit `openagents/llm/providers/mock.py` before building the scripted provider. If it already supports this pattern, reuse it; otherwise ship a thin subclass in `examples/multi_agent_support/app/plugins.py`.

2. **Should `run_demo_real.py` default to MiniMax (matching other examples) or prompt for provider?** Decision: default to MiniMax-Anthropic endpoint for consistency with `production_coding_agent/run_demo.py`; document `LLM_API_BASE` override in `.env.example`. A multi-provider demo is out of scope per user direction.

3. **Coverage floor for the new example.** The integration test exercises `app/plugins.py`, `app/deps.py`, `app/protocol.py`. If any branch (e.g., an error handler in a tool) is not hit by the four scenarios, we either add a targeted scenario or add a `coverage.omit` entry — the choice is deferred to the task where coverage is measured, but the working assumption is "no omit entries needed."

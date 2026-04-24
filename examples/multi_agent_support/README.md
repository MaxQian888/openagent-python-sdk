# multi_agent_support

A customer-support triage multi-agent application built on the `agent_router` seam. This is the SDK's flagship multi-agent example — it exercises every contract in the `agent-router` spec (all three `session_isolation` modes, depth protection, unknown-agent error path, handoff metadata, child-budget fallback) through a single coherent business scenario.

For a shorter seam-only reference see [`examples/multi_agent/`](../multi_agent/).

## Directory

```
examples/multi_agent_support/
├── agent_mock.json           # offline mock config (four agents, no API key)
├── agent_real.json           # real-LLM config (Anthropic-compatible endpoint)
├── agent_mock_scenario3.json # depth-limit scenario variant
├── agent_mock_scenario4.json # unknown-agent scenario variant
├── .env.example              # credentials template for the real demo
├── scenarios.py              # 4 scenario functions shared by the demo and the test
├── run_demo_mock.py          # offline end-to-end demo (CI-safe)
├── run_demo_real.py          # LLM-driven demo
└── app/
    ├── deps.py               # SupportDeps: CustomerStore + TicketStore + trace
    ├── plugins.py            # ToolPlugin subclasses (lookup, router-bound, action)
    └── protocol.py           # pydantic envelopes + state keys
```

## Agent topology

```
concierge ─┬─ delegate(isolated) ───▶ account_lookup
           │
           ├─ transfer ─▶ refund_specialist ─ delegate(shared) ▶ account_lookup
           │                                       │
           │                                       └─ issue_refund ticket
           │
           └─ transfer ─▶ tech_support ─ delegate(forked)   ▶ account_lookup
                                        └ delegate(isolated) ▶ account_lookup
                                        └─ open_ticket
```

## Run (offline mock)

```bash
uv run python examples/multi_agent_support/run_demo_mock.py
```

All four scenarios run in < 1 s with no API key and no network access. Scenarios:

1. **Refund flow** — concierge transfers to refund_specialist, which delegates to account_lookup with `session_isolation="shared"`, then persists a refund ticket.
2. **Tech flow** — concierge transfers to tech_support, which does one `session_isolation="forked"` diagnostic delegate (main hypothesis) and one `session_isolation="isolated"` fallback lookup before opening a tech ticket.
3. **Depth limit** — `SelfDelegateLookupTool` invoked with a context already at `DELEGATION_DEPTH_KEY == max_delegation_depth` raises `DelegationDepthExceededError(depth=3, limit=3)` before any child is constructed.
4. **Unknown agent** — `DelegateToMissingTool` calls `router.delegate("does_not_exist", ...)` → `AgentNotFoundError("does_not_exist")`.

## Run (real LLM)

```bash
cp examples/multi_agent_support/.env.example examples/multi_agent_support/.env
# edit .env with LLM_API_KEY / LLM_API_BASE / LLM_MODEL
uv run python examples/multi_agent_support/run_demo_real.py
```

Runs scenarios 1 and 2 only (the depth and unknown-agent scenarios rely on direct tool invocation that a real LLM may not emit verbatim). The demo uses the `rich_console` event bus so tool / LLM / session events stream to stderr in real time.

## Integration tests

```bash
uv run pytest -q tests/integration/test_multi_agent_support_example.py
```

Runs all four scenarios plus a static-analysis check on `app/plugins.py` that every `session_isolation` mode appears and that router calls span ≥ 2 classes. Expected runtime: ≤ 1 s.

## Multi-agent config block

```jsonc
"multi_agent": {
  "enabled": true,                        // wires DefaultAgentRouter onto ctx.agent_router
  "default_session_isolation": "isolated",
  "max_delegation_depth": 3,              // depth protection for nested delegation
  "default_child_budget": {               // budget fallback for child runs
    "max_steps": 4,
    "max_cost_usd": 0.05
  }
}
```

## Router API used

```python
# From any tool or pattern:
router = ctx.agent_router  # DefaultAgentRouter, injected when multi_agent.enabled=true

# Orchestrator — await a specialist and keep going
result = await router.delegate(
    "account_lookup",
    "cust-001",
    ctx,
    session_isolation="shared",   # or "isolated" / "forked"
)

# Handoff — hand over, parent run ends with child output
await router.transfer(
    "refund_specialist",
    "/tool process_refund cust-001",
    ctx,
    session_isolation="isolated",
)
# transfer() raises HandoffSignal; DefaultRuntime catches it and sets
# parent.metadata["handoff_from"] = child.run_id.
```

## Further reading

- [docs/multi-agent-support-example.md](../../docs/multi-agent-support-example.md) — a complete walkthrough naming the `agent-router` spec requirement each scenario exercises.
- [openspec/specs/agent-router/spec.md](../../openspec/specs/agent-router/spec.md) — the formal contract this example demonstrates.

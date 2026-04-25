# multi_agent

> **Looking for a full, production-style multi-agent app?** See [`examples/multi_agent_support/`](../multi_agent_support/) — the SDK's flagship multi-agent example, covering the full `agent_router` spec contract (all three session-isolation modes, depth protection, `AgentNotFoundError`, handoff metadata, `default_child_budget` fallback) with complete integration tests and docs.
>
> This directory is a **~200-line seam-level minimal reference** demonstrating only the basic shape of the `delegate` / `transfer` APIs. It does not cover business layering, deps passing, or error paths. Read this first to get a feel for the API, then look at `multi_agent_support` for a real app.

[中文文档](README.zh.md)

Demonstrates the `agent_router` seam: two multi-agent collaboration modes based on `delegate` (orchestration) and `transfer` (handoff).

## Directory

```
examples/multi_agent/
├── plugins.py           # Two custom tools: DelegateToSpecialistTool + TransferToBillingTool
├── agent_mock.json      # 4-agent config using mock provider (no API key required)
├── agent_real.json      # 4-agent config using a real LLM (API key required)
├── run_demo_mock.py     # Offline demo
├── run_demo_real.py     # LLM-driven demo
└── .env.example         # Credentials template for the real demo
```

Four agents:
- `orchestrator` — mounts the `delegate_to_specialist` tool
- `specialist` — child agent, receives sub-tasks from the orchestrator
- `triage` — mounts the `transfer_to_billing` tool
- `billing_agent` — child agent, receives billing requests transferred from triage

## Quick start (dev environment)

### Offline mock demo (no API key)

```bash
uv sync
uv run python examples/multi_agent/run_demo_mock.py
```

Three scenarios are demonstrated:
1. **Delegate** — calls `router.delegate("specialist", ...)` directly, showing `RunResult` return and `_run_depths` tracking.
2. **Transfer** — calls `router.transfer("billing_agent", ...)` directly and catches `HandoffSignal`.
3. **Tool-driven** — `runtime.run()` with `/tool delegate_to_specialist ...`, exercising the full ReAct → tool → router path.

### Real LLM demo

```bash
cp examples/multi_agent/.env.example examples/multi_agent/.env
# Edit .env — fill in LLM_API_KEY, LLM_API_BASE, LLM_MODEL
uv run python examples/multi_agent/run_demo_real.py
```

Two scenarios:
- `orchestrator` receives a factual query; the LLM calls `delegate_to_specialist` and synthesises the final answer.
- `triage` receives a refund request; the LLM calls `transfer_to_billing`, permanently handing control to `billing_agent`.

## Testing

```bash
uv run pytest -q tests/integration/test_multi_agent.py
```

Uses the mock provider — no API key required.

## Key API

```python
# Inside a custom tool or pattern:
router = ctx.agent_router  # injected by DefaultRuntime when multi_agent.enabled=true

# Orchestrator (await child result, then continue)
result = await router.delegate(
    "specialist", task, ctx,
    session_isolation="isolated",  # "shared" | "isolated" | "forked"
)

# Handoff (permanent hand-over)
await router.transfer("billing_agent", task, ctx)  # raises HandoffSignal
```

## Config block

```json
{
  "multi_agent": {
    "enabled": true,
    "default_session_isolation": "isolated",
    "max_delegation_depth": 3
  }
}
```

- `max_delegation_depth` — caps nested delegation; exceeding it raises `DelegationDepthExceededError`. Depth is tracked via `RunRequest.metadata["__openagents_delegation_depth__"]`, not process-level state.
- `default_child_budget` — applied automatically when `delegate(budget=None)` is called.
- `session_isolation` modes:
  - `shared` — child run reuses the parent `session_id` (asyncio-task reentrant lock prevents deadlocks).
  - `isolated` — fresh session (default).
  - `forked` — `SessionManagerPlugin.fork_session()` copies the parent's messages/artifacts snapshot to a new `{parent}:fork:{run_id}`; parent and child then write independently.

## Environment variables (real demo only)

| Name | Required | Notes |
|------|----------|-------|
| `LLM_API_KEY` | yes | OpenAI-compatible key. |
| `LLM_API_BASE` | yes | Base URL of the provider. |
| `LLM_MODEL` | yes | Model name. |

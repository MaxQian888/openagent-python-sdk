# multi_agent_support — Walkthrough

`examples/multi_agent_support/` is the SDK's flagship multi-agent example — it exercises **every** contract in the `agent_router` spec through a single customer-support triage application. After reading this you will know:

- How four agents coordinate via `delegate` and `transfer`
- When each `session_isolation` mode (`shared` / `isolated` / `forked`) is the right call
- How `max_delegation_depth` and `AgentNotFoundError` protect the top-level run
- How `deps` carry shared cross-agent state (`CustomerStore` / `TicketStore` / `trace`) without leaking into the kernel
- Why this example bundles "consult + commit" into a single tool (ReAct pattern dispatches at most one tool call per run)

## Topology

```
        user message
             │
             ▼
     ┌──────────────┐
     │  concierge   │
     └────┬───┬─────┘
          │   └─── delegate(isolated) ─────┐
          │                                 ▼
          │                       ┌─────────────────┐
          │                       │  account_lookup │
          │                       └─────────────────┘
          ▼
   ┌─ transfer ─────────────────────────────┐
   │                                        │
   ▼                                        ▼
┌──────────────────┐                ┌─────────────────┐
│ refund_specialist│                │   tech_support  │
└────────┬─────────┘                └────────┬────────┘
         │                                   │
         │ delegate(shared)                  │ delegate(forked) + delegate(isolated)
         ▼                                   ▼
┌─────────────────┐                ┌─────────────────┐
│ account_lookup  │                │ account_lookup  │
└─────────────────┘                └─────────────────┘
```

All four agents run under `multi_agent.enabled: true`, `max_delegation_depth: 3`, and `default_child_budget: {max_steps: 4, max_cost_usd: 0.05}`.

## Layering

The example strictly follows the layering that CLAUDE.md mandates — all product semantics live under `app/`, never in the kernel:

| Layer | File | Responsibility |
|---|---|---|
| SDK seam (unchanged) | `openagents/plugins/builtin/agent_router/default.py` | Provides `delegate` / `transfer` / three isolation modes / depth checks |
| App-defined protocol | `app/protocol.py` | Three pydantic envelopes: `CustomerIntent`, `TicketDraft`, `DelegationTraceEntry` |
| App-defined deps | `app/deps.py` | `SupportDeps` wraps `CustomerStore` + `TicketStore` + `trace` |
| App-defined tools | `app/plugins.py` | All `ToolPlugin` subclasses (lookup, action, router-bound consult / route) |
| Scenario orchestration | `scenarios.py` | Four scenario functions shared by the demo and the test |

`SupportDeps` is attached to the top-level `RunRequest.deps`. When the router constructs a child run with `deps=None`, it falls back to `ctx.deps`, so the entire call tree shares the same `customer_store` / `ticket_store` / `trace` instances.

## Four scenarios

### Scenario 1 — Refund flow (transfer + shared delegate)

The user sends `/tool route_to_refund cust-001` to the concierge.

```
concierge                          refund_specialist                 account_lookup
   │                                      │                               │
   │ RouteToRefundTool.invoke()           │                               │
   │   │                                  │                               │
   │   └─ router.transfer("refund_       │                               │
   │        specialist", "/tool           │                               │
   │        process_refund cust-001")     │                               │
   │                                      │                               │
   │   raises HandoffSignal ←─────────────┤ ProcessRefundTool.invoke()    │
   │                                      │   ├─ router.delegate(          │
   │                                      │   │    "account_lookup",      │
   │                                      │   │    "cust-001",            │
   │                                      │   │    session_isolation=     │
   │                                      │   │      "shared")  ──────────▶
   │                                      │   │                           │ (echo)
   │                                      │   │ ◀──────────────────────── │
   │                                      │   └─ ticket_store.create(     │
   │                                      │        TicketDraft(refund))   │
   │                                      │                               │
   │ RunResult.metadata["handoff_from"]   │                               │
   │   = refund_specialist.run_id         │                               │
```

`agent-router` contracts exercised:

- **Transfer ends the parent run with child output** — the concierge's `RunResult.metadata["handoff_from"]` equals the refund_specialist's `run_id`, and `final_output` is the specialist's output.
- **`shared` session mode — reentrant lock** — the refund_specialist's `shared` delegate reuses the parent session id; the asyncio-task-reentrant session lock prevents deadlock.
- **Child run budget fallback** — neither the refund_specialist nor account_lookup child runs pass `budget=`, so they inherit `default_child_budget`.

Assertions (`assert_refund_outcome` / integration test):

- `parent.stop_reason == StopReason.COMPLETED`
- `parent.metadata["handoff_from"]` non-empty
- `SupportDeps.trace` contains one `(delegate, refund_specialist → account_lookup, shared)` entry
- `SupportDeps.ticket_store` holds exactly one `kind="refund"` ticket with `customer_id="cust-001"`

### Scenario 2 — Tech flow (transfer + forked diagnostic + isolated fallback)

The user sends `/tool route_to_tech cust-002` to the concierge.

`TroubleshootTechTool` first dispatches a `session_isolation="forked"` "network" diagnostic — the spawned child session is `{tech_support.session_id}:fork:{tech_support.run_id}` and starts with a full snapshot of the parent session's messages and artifacts. Then it runs a `session_isolation="isolated"` "billing cache" fallback check, and finally writes a tech ticket.

`agent-router` contracts exercised:

- **`forked` session mode — real snapshot copy** — the forked child sees the parent's snapshot at fork time; writes on either side after fork do not leak across.
- **`isolated` session mode** — the second branch uses a fresh session, showing how one tool can mix isolation modes.
- **Router injection when enabled** — `multi_agent.enabled: true` guarantees `ctx.agent_router` is the `DefaultAgentRouter`.

*Why only one fork*: `DefaultAgentRouter._resolve_session` hard-codes the forked child sid as `{parent_sid}:fork:{parent_run_id}`, so multiple forks from the same parent run collide on the target sid. A single fork fully exercises the snapshot + isolation contract.

Assertions:

- `parent.stop_reason == StopReason.COMPLETED`
- `SupportDeps.trace` contains at least one `isolation="forked"` entry with `child_session_id` matching the `<parent_sid>:fork:<run_id>` format
- `session_manager.load_messages(forked_child_sid)` succeeds (the child session is registered)
- `SupportDeps.ticket_store` holds exactly one `kind="tech"` ticket with `customer_id="cust-002"`

### Scenario 3 — Depth protection (DelegationDepthExceededError)

`SelfDelegateLookupTool` recursively calls `router.delegate("account_lookup", "/tool self_delegate_lookup ...", isolated)`. Under `max_delegation_depth=3`, the fourth call (parent depth=3) raises `DelegationDepthExceededError(depth=3, limit=3)` inside the router, before any child request is constructed.

The scenario function `run_depth_scenario` builds a `RunContext.run_request.metadata={DELEGATION_DEPTH_KEY: 3}` directly and invokes the tool — this way the caller catches the raw exception instead of having `DefaultRuntime.run()`'s `except Exception` wrap it into a `PatternError`.

`agent-router` contracts exercised:

- **Delegation depth is tracked via request metadata** — depth lives on `RunRequest.metadata["__openagents_delegation_depth__"]`, no process-level state.
- **Depth limit enforced** — when `depth >= limit`, the router raises before `_run_fn` is called.

### Scenario 4 — Unknown target agent (AgentNotFoundError)

`DelegateToMissingTool.invoke` calls `router.delegate("does_not_exist", ...)`. The router's `_agent_exists` callback (injected by `Runtime.__init__`) returns False, and the router raises `AgentNotFoundError("does_not_exist")` — not `ConfigError`, not a generic `Exception` — with `.agent_id` equal to the rejected id.

`agent-router` contracts exercised:

- **Unknown agent_id raises AgentNotFoundError** — the exception type is exact, and the `.agent_id` attribute is preserved.

## FAQ

**Q: Why bundle consult + commit inside one tool?**

`ReActPattern` short-circuits the next step to `final` after any tool dispatch (via `_PENDING_TOOL_KEY` in scratch) — every agent run dispatches **at most one** tool call. So two-step business logic like "look the customer up, then issue a refund" must live inside a single tool (`ProcessRefundTool`). This is not an example quirk; it is the shape of the builtin ReAct pattern.

**Q: How does the mock provider decide which tool to dispatch?**

`MockLLMClient` parses the prompt's `INPUT:` line; if it starts with `/tool <id> <query>` the provider emits a tool_call for `<id>`. So the scenarios feed `/tool ...` into the concierge's `input_text`, and `RouteToRefundTool` passes `/tool process_refund ...` as the child's `input_text` to prime the downstream agent. Layer by layer, the `/tool` prefix drives the flow.

**Q: Why does `deps.trace` live on `deps` rather than `ctx.state`?**

`ctx.state` is per-run — a parent run cannot see its child's state. We want the top-level test to inspect "how many delegates / transfers happened across the whole call tree," so `trace` rides on `deps`, which the router inherits across children by default.

**Q: The real-LLM demo can't guarantee which tool the LLM picks. What then?**

`run_demo_real.py` runs only scenarios 1 and 2 and does not assert specific `final_output` strings — it only prints stop_reason / handoff_from / tickets. The regression lock lives on the mock path.

## See also

- [agent-router spec](../openspec/specs/agent-router/spec.md) — the formal WHEN/THEN for every contract
- [seams-and-extension-points](seams-and-extension-points.en.md) — the "where should this go" decision tree
- [production_coding_agent](examples.en.md#examplesproduction_coding_agent) — the single-agent counterpart, same app-layering style

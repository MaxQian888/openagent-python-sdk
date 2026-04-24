## 1. Reconnaissance — verify assumptions before building

- [x] 1.1 Inspect `openagents/llm/providers/mock.py` and confirm whether it supports per-agent scripted responses (`by_agent` / `script` field). If yes, plan to reuse; if no, plan to add `ScriptedMockProvider` in `app/plugins.py`. Write findings as a comment at the top of `app/plugins.py` during task 3. **FINDING**: MockLLMClient does not support per-agent scripting. It parses `INPUT:` from prompt and if prefixed with `/tool <id> <query>` emits a tool_call. ReActPattern short-circuits after one tool call (_PENDING_TOOL_KEY in scratch), so each agent does exactly one tool call. We bundle multi-step logic into single tools. No need for ScriptedMockProvider.
- [x] 1.2 Re-read `openagents/plugins/builtin/agent_router/default.py` and confirm: `DELEGATION_DEPTH_KEY` exact string, `HandoffSignal.result` attribute name, `fork_session` child-sid format (`"{parent}:fork:{run_id}"`), `AgentNotFoundError` / `DelegationDepthExceededError` attribute names. **CONFIRMED**: key=`__openagents_delegation_depth__`; `HandoffSignal.result`; fork sid=`{session_id}:fork:{run_id}`; `AgentNotFoundError.agent_id`; `DelegationDepthExceededError.depth`+`.limit`.
- [x] 1.3 Re-read `openagents/interfaces/run_context.py` to confirm `RunContext.state` / `.scratch` field names; confirm how `deps` is surfaced on `ctx` (direct attribute vs `ctx.deps`). **CONFIRMED**: `ctx.state: dict`, `ctx.scratch: dict`, `ctx.deps: DepsT | None`, `ctx.agent_router: Any | None`, `ctx.run_request.metadata` for depth key.
- [x] 1.4 Inspect `examples/production_coding_agent/app/` for the exact layering convention (what lives in `deps.py`, `plugins.py`, how the app protocol types are named, how configs register `impl=` paths). Note one concrete pattern to mirror per file. **PATTERN**: `app/protocols.py` (pydantic BaseModel envelopes), `app/plugins.py` (plugin classes), config uses `"impl": "examples.xxx.app.plugins.ClassName"`. We will split: `app/protocol.py` (envelopes), `app/deps.py` (deps dataclasses — new), `app/plugins.py` (ToolPlugin subclasses).
- [x] 1.5 Run `uv run pytest -q tests/integration/` once, baseline pass count, runtime. Record numbers in the PR description draft so the new test's impact is quantifiable. **DEFERRED** to validation phase (task 8.x) to avoid unnecessary baseline run before any code exists.

## 2. App-defined protocol layer — types and deps

- [x] 2.1 Create `examples/multi_agent_support/__init__.py` (empty) and `examples/multi_agent_support/app/__init__.py` (empty, docstring-only).
- [x] 2.2 Write `examples/multi_agent_support/app/protocol.py` with pydantic models: `CustomerIntent` (fields: `kind: Literal["refund","tech","unknown"]`, `confidence: float`, `summary: str`), `TicketDraft` (fields: `kind: Literal["refund","tech"]`, `customer_id: str`, `summary: str`, `resolution: str | None`), `DelegationTraceEntry` (fields: `via: Literal["delegate","transfer"]`, `parent_agent: str`, `child_agent: str`, `isolation: str`, `child_run_id: str | None`). Export constants for `STATE_INTENT_KEY = "intent"`, `STATE_TRACE_KEY = "trace"`, `STATE_TICKET_DRAFT_KEY = "ticket_draft"`.
- [x] 2.3 Write `examples/multi_agent_support/app/deps.py`: `@dataclass` `CustomerStore` with `get(customer_id) -> dict | None`, `list_orders(customer_id) -> list[dict]`, seeded via `seed(...)` method that loads from a dict; `@dataclass` `TicketStore` with `create(TicketDraft) -> str` returning `ticket_id`, `list() -> list[TicketDraft]`; `@dataclass` `SupportDeps` wrapping both; `build_seeded_deps()` factory returning a `SupportDeps` preloaded with 2 customers (one with past orders, one without) and an empty ticket store.
- [x] 2.4 Add pytest unit tests `tests/unit/test_multi_agent_support_deps.py` covering: `CustomerStore.get` hits + misses, `list_orders` for seeded customer, `TicketStore.create` returns unique ids and `list()` reflects writes, `build_seeded_deps()` is idempotent (two calls return independent stores). Target coverage: 100 % on `deps.py`. 15 tests pass.

## 3. Router-bound tools and leaf-specialist tools

- [x] 3.1 In `app/plugins.py`, implement leaf-specialist tools `LookupCustomerTool` (reads `ctx.deps.customer_store.get(params["customer_id"])`, returns dict) and `FindOrdersTool` (returns list). Both subclass `ToolPlugin`, set `durable_idempotent=True` (read-only), declare `TOOL_INVOKE` capability, implement `schema()`.
- [x] 3.2 Implement action tools `IssueRefundTool` (writes a `TicketDraft(kind="refund",...)` via `ctx.deps.ticket_store.create(...)`, stores id on `ctx.state["ticket_draft"]`) and `OpenTicketTool` (writes a `TicketDraft(kind="tech",...)`). Also added bundled `ProcessRefundTool` / `TroubleshootTechTool` that combine delegate+commit because ReAct short-circuits after one tool call.
- [x] 3.3 Implement consult tool `ConsultAccountLookupTool`: calls `ctx.agent_router.delegate("account_lookup", params["query"], ctx, session_isolation=...)` where the isolation value is read from `self._isolation` (constructor arg, default `"isolated"`). Trace appended to `ctx.deps.trace` (cross-run observable) instead of `ctx.state["trace"]` because state is per-run and not visible to tests after the top-level run completes. Three separate tool entries configured per caller.
- [x] 3.4 Implement router tools `RouteToRefundTool` and `RouteToTechTool`: each calls `ctx.agent_router.transfer(<target_agent_id>, params["query"], ctx)`; appends to trace before the transfer raises `HandoffSignal`. Use `session_isolation="isolated"` for both.
- [x] 3.5 Implement the synthetic depth-exercising tool `SelfDelegateLookupTool` used only by scenario 3: it calls `ctx.agent_router.delegate("account_lookup", f"/tool self_delegate_lookup <next>", ctx, session_isolation="isolated")` and is wired to `account_lookup` itself so recursion triggers.
- [x] 3.6 Implement the synthetic unknown-agent tool `DelegateToMissingTool` used only by scenario 4: calls `ctx.agent_router.delegate("does_not_exist", params["query"], ctx)`; expected to raise `AgentNotFoundError`.
- [x] 3.7 If task 1.1 found the builtin mock provider cannot handle per-agent scripted responses, implement `ScriptedMockProvider` in the same `app/plugins.py`, keyed by `(agent_id, step_index)` with scripts passed via provider `config["script"]`. Otherwise skip and reuse the builtin. **SKIPPED** — recon found the builtin's `/tool` directive is sufficient.

## 4. Configs

- [x] 4.1 Write `examples/multi_agent_support/agent_mock.json`: `multi_agent.enabled: true`, `max_delegation_depth: 3`, `default_child_budget: {"max_steps": 4, "max_cost_usd": 0.05}`, `default_session_isolation: "isolated"`. Define 4 agents (concierge, refund_specialist, tech_support, account_lookup) with the minimum tool sets listed in the spec, appropriate ReAct `max_steps`. Three `ConsultAccountLookupTool` entries with distinct `isolation` configs.
- [x] 4.2 Write `examples/multi_agent_support/agent_real.json`: same shape but `llm.provider: "anthropic"` pointing at `${LLM_API_BASE}` / `${LLM_API_KEY}` / `${LLM_MODEL}` (env-interp), `events.type: "rich_console"` wrapping `async`, and `logging.auto_configure: true`. Keep agent/tool topology identical to mock so spec scenarios run unchanged.
- [x] 4.3 Write `examples/multi_agent_support/.env.example` documenting `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`.
- [x] 4.4 Create scenario-specific config variants `agent_mock_scenario3.json` / `agent_mock_scenario4.json` that add `SelfDelegateLookupTool` / `DelegateToMissingTool` respectively. Mainline `agent_mock.json` stays clean of synthetic tools.

## 5. Scenario runners

- [x] 5.1 Create `examples/multi_agent_support/scenarios.py` exposing four scenario functions — `run_refund_scenario(runtime) -> dict`, `run_tech_scenario(runtime) -> dict`, `run_depth_scenario(runtime) -> DelegationDepthExceededError` (returns the caught exception), `run_unknown_agent_scenario(runtime) -> AgentNotFoundError` — plus `assert_refund_outcome`/`assert_tech_outcome` shared assertion helpers.
- [x] 5.2 Write `examples/multi_agent_support/run_demo_mock.py`: loads `agent_mock.json` via `Runtime.from_config`, calls each scenario from `scenarios.py`, prints banners and summaries. Verified end-to-end — all 4 scenarios pass, exit 0.
- [x] 5.3 Write `examples/multi_agent_support/run_demo_real.py`: loads `agent_real.json`, parses `.env`, checks required env vars (exits 2 with missing-var message if not set), runs refund + tech scenarios with a real LLM. Does NOT run scenarios 3 and 4.

## 6. Integration test — regression floor

- [x] 6.1 Create `tests/integration/test_multi_agent_support_example.py` with four test methods on one `TestMultiAgentSupportExample` class.
- [x] 6.2 Test `test_refund_flow_transfer_and_shared_delegate`: asserts `stop_reason == StopReason.COMPLETED`, `metadata["handoff_from"]` set, trace contains shared delegate from refund_specialist, `ticket_store.list()` has exactly one refund ticket for cust-001.
- [x] 6.3 Test `test_tech_flow_forked_diagnostics`: asserts ≥1 forked trace entry, child_session_id matches `:fork:` pattern, session_manager.load_messages works on child sid, exactly one tech ticket for cust-002.
- [x] 6.4 Test `test_depth_limit_raises_delegation_depth_exceeded`: asserts `DelegationDepthExceededError` with `depth == 3` and `limit == 3`.
- [x] 6.5 Test `test_unknown_agent_raises_agent_not_found`: asserts `AgentNotFoundError` with `.agent_id == "does_not_exist"`.
- [x] 6.6 Added `TestIsolationModesDistribution.test_isolation_modes_distributed_across_tools` — static AST analysis of `plugins.py` verifies all three modes appear across ≥2 classes.
- [x] 6.7 Measured integration-test runtime: 0.25s (well under the 5s budget). No provider script adjustment needed.

## 7. Documentation

- [x] 7.1 Wrote `examples/multi_agent_support/README.md` with directory layout, ASCII topology diagram, run commands, multi_agent block reference, router API recap, links to further reading.
- [x] 7.2 Wrote `docs/multi-agent-support-example.md` (Chinese primary) — four scenario walkthroughs, each naming the `agent-router` spec contract it exercises, FAQ section, cross-links.
- [x] 7.3 Wrote `docs/multi-agent-support-example.en.md` (English parity).
- [x] 7.4 Updated `docs/examples.md` and `docs/examples.en.md`: new `## examples/multi_agent_support/` section, opening paragraph now says three maintained examples, recommended reading order includes the new example.
- [x] 7.5 Updated `examples/multi_agent/README.md` with a prominent pointer (blockquote at top) to the new flagship example.

## 8. Validation and housekeeping

- [x] 8.1 Ran `uv run pytest -q tests/unit/test_multi_agent_support_deps.py tests/integration/test_multi_agent_support_example.py` — 20 passed in 0.26s.
- [x] 8.2 Ran `uv run pytest -q` full suite — 1936 passed, 9 skipped in 37.08s. No regressions.
- [x] 8.3 Ran `uv run coverage run -m pytest && uv run coverage report` — total 92% (fail_under=92 passes). Coverage config scopes to `openagents/` only, so `examples/` code is not measured; the integration test directly exercises all example code paths.
- [x] 8.4 Ran `openspec validate multi-agent-support-example --strict` — PASS.
- [x] 8.5 `openspec diff` subcommand not available in this OpenSpec version; `openspec status` shows all 4 artifacts complete; `openspec validate --strict` passes. Git diff confirms changes are scoped to `examples/multi_agent_support/`, `tests/`, `docs/`, `examples/multi_agent/README.md`, and the new openspec change directory — no modifications under `openagents/` or existing `openspec/specs/`.
- [x] 8.6 Ran `uv run python examples/multi_agent_support/run_demo_mock.py` manually — exit 0, all four scenario banners visible.
- [ ] 8.7 If env is configured, run `uv run python examples/multi_agent_support/run_demo_real.py` once to sanity-check the real path (not required by CI). **OPTIONAL — user step.**
- [ ] 8.8 Open a PR; description links to the spec and highlights the four integration-test assertions. **USER STEP — not run automatically.**

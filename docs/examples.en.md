# Examples

This repository currently maintains three example groups: `quickstart`, `production_coding_agent`, and `multi_agent_support`.

All other historical examples are retired — the repository is deliberately focused on real, runnable, testable examples to stop documentation from referencing deleted directories.

Unless noted otherwise, examples that need a real LLM use MiniMax's Anthropic-compatible endpoint and expect `MINIMAX_API_KEY` (or equivalent `LLM_API_KEY` / `LLM_API_BASE` / `LLM_MODEL`).

## Which One to Start With

- First time running the repository
  - Start with `quickstart`
- Want a high-density, production-layered *single-agent* example
  - Go to `production_coding_agent`
- Want a complete *multi-agent* application exercising the `agent_router` seam (customer-support triage)
  - Go to `multi_agent_support`
- Want to learn custom plugin / seam development
  - Read [Plugin Development](plugin-development.md) first
  - Then look at `tests/fixtures/` and `examples/production_coding_agent/app/`

## `examples/quickstart/`

Purpose:

- Minimal builtin-only setup
- First confirmation that the kernel runs

Key files:

- `examples/quickstart/agent.json`
- `examples/quickstart/run_demo.py`

Demonstrates:

- `window_buffer`
- `react`
- Builtin search tool
- Consecutive runs within the same session

Run:

```bash
uv run python examples/quickstart/run_demo.py
```

Related tests:

```bash
uv run pytest -q tests/integration/test_runtime_from_config_integration.py
```

## `examples/production_coding_agent/`

Purpose:

- Demonstrates a high-density, production-style coding agent
- Shows how "SDK seams + app-defined protocol" work together
- Shows a rigorous local validation path

Key files:

- `examples/production_coding_agent/agent.json`
- `examples/production_coding_agent/run_demo.py`
- `examples/production_coding_agent/run_benchmark.py`
- `examples/production_coding_agent/app/`
- `examples/production_coding_agent/workspace/`
- `examples/production_coding_agent/outputs/`

Demonstrates:

- Task packet assembly
- Persistent coding memory
- Filesystem boundary enforcement
- Safe tool execution
- Local follow-up semantics
- Structured delivery artifacts
- Benchmark-style local evaluation harness

This is not claiming "local tests mean production ready" — it demonstrates:

- How a growable coding agent should be layered
- What belongs in a seam
- What belongs in the app protocol
- How to write reproducible integration tests

Run:

```bash
uv run python examples/production_coding_agent/run_demo.py
```

Benchmark:

```bash
uv run python examples/production_coding_agent/run_benchmark.py
```

Related tests:

```bash
uv run pytest -q tests/integration/test_production_coding_agent_example.py
```

## `examples/multi_agent_support/`

Purpose:

- A complete multi-agent application that exercises the `agent_router` seam end-to-end
- Customer-support triage scenario: concierge → refund_specialist / tech_support → account_lookup
- Covers every contract in the `agent-router` spec: `delegate` / `transfer`, all three `session_isolation` modes, `max_delegation_depth` enforcement, `AgentNotFoundError`, `default_child_budget` fallback, and `metadata["handoff_from"]` propagation

Key files:

- `examples/multi_agent_support/agent_mock.json` — offline mock config (four agents)
- `examples/multi_agent_support/agent_real.json` — real-LLM config (Anthropic-compatible)
- `examples/multi_agent_support/app/deps.py` — `SupportDeps` (`CustomerStore` + `TicketStore` + `trace`)
- `examples/multi_agent_support/app/plugins.py` — `ToolPlugin` subclasses (lookup, router-bound, action)
- `examples/multi_agent_support/app/protocol.py` — pydantic envelopes (`CustomerIntent`, `TicketDraft`, `DelegationTraceEntry`)
- `examples/multi_agent_support/scenarios.py` — the four scenario functions shared by demo and integration test
- `examples/multi_agent_support/run_demo_mock.py` — offline demo (no API key)
- `examples/multi_agent_support/run_demo_real.py` — real-LLM demo

Demonstrates:

- All three `agent_router.delegate` session isolation modes (shared / isolated / forked)
- `agent_router.transfer` handoff semantics + `HandoffSignal` capture
- Nested delegation depth propagation via `RunRequest.metadata`
- Error paths: `DelegationDepthExceededError` and `AgentNotFoundError`
- How to layer an app-defined protocol (deps, pydantic envelopes, trace log) on top of SDK seams

Run:

```bash
# Offline mock (default CI path)
uv run python examples/multi_agent_support/run_demo_mock.py
```

```bash
# Real LLM (needs .env)
cp examples/multi_agent_support/.env.example examples/multi_agent_support/.env
# edit .env with LLM_API_KEY / LLM_API_BASE / LLM_MODEL
uv run python examples/multi_agent_support/run_demo_real.py
```

Related tests:

```bash
uv run pytest -q tests/integration/test_multi_agent_support_example.py
```

Further reading: [multi-agent-support-example](multi-agent-support-example.en.md) — a walkthrough of the four scenarios, naming the `agent-router` spec requirement each exercises.

## Running Integration Tests

All maintained examples have accompanying integration tests:

```bash
# Run all integration tests
uv run pytest -q tests/integration/
```

## Learning Custom Extensions

Although the repository no longer maintains a collection of standalone demo directories, documentation on customization has not disappeared. The primary reference surfaces are:

- `tests/fixtures/custom_plugins.py`
- `tests/fixtures/runtime_plugins.py`
- `tests/unit/test_plugin_loader.py`
- `tests/unit/test_runtime_orchestration.py`
- `examples/production_coding_agent/app/`
- `openagents/plugins/builtin/tool_executor/filesystem_aware.py` — filesystem execution policy example (`FilesystemAwareToolExecutor`, showing the structure of `evaluate_policy()`)
- `openagents/plugins/builtin/pattern/react.py` — `ReActPattern` source, showing the actual call sites for `resolve_followup()` and `repair_empty_response()`

## Recommended Reading Order

For the most effective path through this repository:

1. `quickstart`
2. `production_coding_agent`
3. `multi_agent_support` (if your use case involves multi-agent coordination)
4. [Plugin Development](plugin-development.md)
5. [Repository Layout](repository-layout.md)

## research_analyst

This example demonstrates how the post-seam-consolidation (2026-04-18) extension approach connects together in a real task.

| Mechanism | Location | Role |
| --- | --- | --- |
| Custom `tool_executor` | `examples/research_analyst/app/executor.py::SandboxedResearchExecutor` | Extends `SafeToolExecutor`, overrides `evaluate_policy()`: embeds `CompositePolicy` to AND-combine filesystem + network allowlist; `execute()` delegates to `RetryToolExecutor(inner=SafeToolExecutor)` for retry + timeout |
| Pattern subclass + `resolve_followup()` override | `FollowupFirstReActPattern` (`examples/research_analyst/app/followup_pattern.py`) | Extends builtin `ReActPattern`, loads `followup_rules.json` and performs regex → template local resolution in `resolve_followup()`; builtin `ReActPattern.execute()` calls it first to short-circuit the LLM |
| `session` | builtin `jsonl_file` | All transcripts / artifacts / checkpoints persisted to `sessions/<sid>.jsonl`; replayable after restart |
| `events` | builtin `file_logging` | All events appended to `sessions/events.ndjson` for audit |

The pattern layer uses `FollowupFirstReActPattern` (`examples/research_analyst/app/followup_pattern.py`) — you only need to override `resolve_followup()`. The builtin `ReActPattern.execute()` is responsible for calling it before the LLM loop. Unlike the old seam, the follow-up call site is now managed by the kernel internally rather than by the app layer explicitly.

### Caveats

- **`HttpRequestTool` does not raise on 5xx**: The tool swallows HTTP error codes internally and returns `{"success": false, "error": "..."}`. `SafeToolExecutor` never sees an exception — so "503 → retry" won't trigger. The example stub instead makes the first two calls **sleep** past the executor timeout so that `ToolTimeoutError` is actually raised, causing the `retry` builtin to take effect.
- **ReAct allows only one tool call per turn**: The builtin `react` pattern allows a single tool call per turn. Multi-tool orchestration requires your own logic in an app-layer pattern.

## pptx-agent (Production-Grade PPT Generator CLI)

Located at `examples/pptx_generator/`. 7-stage interactive wizard (intent → env → research → outline → theme → slides → compile/QA), built on Rich + questionary, using Tavily MCP for research by default.

- Install: `uv add "io-openagent-sdk[pptx]"`
- Run: `pptx-agent new --topic "..."` or `pptx-agent resume <slug>`
- List saved preferences: `pptx-agent memory list`
- Remove a preference: `pptx-agent memory forget <id>`
- Replay a finished run: `openagents replay outputs/<slug>/events.jsonl` (every `new` / `resume` persists an NDJSON event stream with secret-bearing keys redacted)
- CLI guide: [`docs/pptx-agent-cli.en.md`](pptx-agent-cli.en.md) ([CN](pptx-agent-cli.md))

Every stage is interactive: field-by-field intent editing, outline add/remove/reorder/edit, a 3–5 candidate theme gallery with a full custom editor, slide-generator schema validation with retry-and-fallback, and optional cross-session preference capture. See the CLI guide for the walk-through.

## Further Reading

- [Developer Guide](developer-guide.md)
- [Seams and Extension Points](seams-and-extension-points.md)
- [Configuration Reference](configuration.md)
- [Plugin Development](plugin-development.md)
- [API Reference](api-reference.md)

# research_analyst

Offline research agent that exercises the post seam-consolidation (2026-04-18) extension model.

[中文文档](README.zh.md)

| Mechanism | Implementation | Location |
|---|---|---|
| Custom `tool_executor` with multi-policy + retry | `SandboxedResearchExecutor` — `evaluate_policy()` combines filesystem + network allowlist via `CompositePolicy`; `execute()` delegates to `RetryToolExecutor(inner=SafeToolExecutor)` | `app/executor.py` |
| Pattern-subclass follow-up resolution | `FollowupFirstReActPattern` overrides `ReActPattern.resolve_followup()` with rule-based regex → template matching | `app/followup_pattern.py` + `app/followup_rules.json` |
| Session | `jsonl_file` builtin | `agent.json` + `./sessions` |
| Events | `file_logging` builtin | `agent.json` + `./sessions/events.ndjson` |

## Quick start (dev environment)

No real API key or network access is required — the demo spins up an
`aiohttp` stub server on `127.0.0.1` that serves all web content locally.

```bash
# 1. Install dependencies
uv sync

# 2. Run the demo
uv run python examples/research_analyst/run_demo.py
```

## Testing

```bash
# Unit tests (stub server + follow-up pattern, no external services)
uv run pytest -q tests/unit/examples/research_analyst/

# End-to-end integration test (stub server, mock LLM)
uv run pytest -q tests/integration/test_research_analyst_example.py
```

## Relation to the pre-consolidation version

Before 2026-04-18 this example used:

- `execution_policy: composite` with nested `filesystem` + `network_allowlist` — now folded into
  `SandboxedResearchExecutor.evaluate_policy()` (a custom `tool_executor`).
- `followup_resolver: rule_based` — now a `PatternPlugin.resolve_followup()` override on
  `FollowupFirstReActPattern`, invoked automatically by builtin `ReActPattern.execute()`.
- `response_repair_policy: strict_json` — omitted here; the builtin default (abstain) is fine for
  this example. Apps that want repair behavior override `PatternPlugin.repair_empty_response()`
  on their pattern subclass.

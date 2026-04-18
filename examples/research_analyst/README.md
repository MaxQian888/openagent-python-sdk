# research_analyst example

Offline research agent that exercises the post seam-consolidation (2026-04-18) extension model:

| 机制 | 实现 | 位置 |
|---|---|---|
| custom tool_executor with multi-policy + retry | `SandboxedResearchExecutor` (`evaluate_policy()` combines filesystem + network allowlist via `CompositePolicy`; `execute()` delegates to `RetryToolExecutor(inner=SafeToolExecutor)`) | `app/executor.py` |
| pattern-subclass follow-up resolution | `FollowupFirstReActPattern` overrides `ReActPattern.resolve_followup()` with rule-based regex → template matching | `app/followup_pattern.py` + `app/followup_rules.json` |
| session | `jsonl_file` builtin | `agent.json` + `./sessions` |
| events | `file_logging` builtin | `agent.json` + `./sessions/events.ndjson` |

## Run

```bash
uv run python examples/research_analyst/run_demo.py
```

No external network is required; an aiohttp stub server on 127.0.0.1 serves all web content.

## Relation to the pre-consolidation version

Before 2026-04-18 this example used:

- `execution_policy: composite` with nested `filesystem` + `network_allowlist` — now folded into
  `SandboxedResearchExecutor.evaluate_policy()` (a custom `tool_executor`).
- `followup_resolver: rule_based` — now a `PatternPlugin.resolve_followup()` override on
  `FollowupFirstReActPattern`, invoked automatically by builtin `ReActPattern.execute()`.
- `response_repair_policy: strict_json` — omitted here; the builtin default (abstain) is fine for
  this example. Apps that want repair behavior override `PatternPlugin.repair_empty_response()`
  on their pattern subclass.

# Migration: 0.2 → 0.3

`0.3.0` is the second breaking change since the `0.2.0` model modernization (pre-1.0 package; breaking changes are permitted).
This release deepens **existing contracts** only — no new seams are added. All changes are either internal to existing seams or land on kernel protocol objects.

- Corresponding spec: `docs/superpowers/specs/2026-04-16-openagents-sdk-kernel-completeness-design.md`
- Corresponding implementation plan: `docs/superpowers/plans/2026-04-16-openagents-sdk-kernel-completeness-implementation-plan.md`
- Changelog: [CHANGELOG.md](../CHANGELOG.md)

## Breaking Changes Summary

| Change | Scenario | Impact |
|--------|----------|--------|
| `context_assembler: summarizing` → `truncating` | Any config using the old name | **Must change**: old name triggers `PluginLoadError` |
| `_load_plugin` → `load_plugin` (public) | Custom combinator plugins | Needs updating (old name emits `DeprecationWarning`) |
| `tool.succeeded` payload gains `executor_metadata` | Subscribers parsing the payload | Subscribers only reading `tool_id`/`result` are unaffected |
| `_BoundTool.invoke()` returns `ToolExecutionResult` | Custom patterns calling `tool.invoke()` directly | Use `unwrap_tool_result(result)` for compatibility |
| Unknown config keys in builtin plugins now emit warnings | `agent.json` with extra config keys | Check logs; next major version will turn this into an error |
| Coverage floor 90% → 92% | CI in repository forks | Update `pyproject.toml` |

## By Use Case

### Scenario A: I only call `Runtime.run_detailed` with no custom pattern

**Zero changes required.** `RunResult` became `RunResult[Any]`; `final_output: Any` is equivalent to the old behavior.

### Scenario B: I have a custom pattern but don't need `output_type`

**Zero changes required.** `PatternPlugin.finalize()` has a base class default implementation; when `output_type=None` it returns the raw output directly. The runtime's validation retry loop only participates when `output_type` is explicitly set.

### Scenario C: My config uses `context_assembler: summarizing`

**Must change.** 0.3.0 renames it to `truncating` because the old implementation did not actually perform summarization.

```diff
- "context_assembler": {"type": "summarizing"}
+ "context_assembler": {"type": "truncating"}
```

Or use one of the three newly introduced token budget strategies:

- `"head_tail"` — keep the first N messages + tail within budget
- `"sliding_window"` — FIFO: drop from the front until the budget is satisfied
- `"importance_weighted"` — system / recent user / recent tool messages take priority

Loading the old name causes the runtime to immediately raise `PluginLoadError` with a migration hint.

### Scenario D: I want typed structured output

```python
from pydantic import BaseModel
from openagents.interfaces.runtime import RunRequest, RunBudget
from openagents.runtime.runtime import Runtime

class UserProfile(BaseModel):
    name: str
    age: int

runtime = Runtime.from_dict(config)
result = await runtime.run_detailed(
    request=RunRequest(
        agent_id="assistant",
        session_id="s",
        input_text="give me a user profile",
        output_type=UserProfile,
        budget=RunBudget(max_validation_retries=3),
    )
)
# Success: result.final_output is a UserProfile instance
# Exhausted retries: result.stop_reason == FAILED
#                    result.exception is OutputValidationError
```

On validation failure the runtime automatically:

1. Writes the error to `context.scratch["last_validation_error"]`
2. Emits a `validation.retry` event
3. Re-enters `pattern.execute()` (the three builtin patterns read scratch at the start of `execute()` and inject a `role=system` correction message into the transcript)

If a custom pattern needs to support the validation loop, add one line at the start of `execute()`:

```python
class MyPattern(PatternPlugin):
    async def execute(self):
        self._inject_validation_correction()
        # ... your existing logic
```

### Scenario E: I want to track costs / limit costs

```python
from openagents.interfaces.runtime import RunBudget

result = await runtime.run_detailed(
    request=RunRequest(
        agent_id="assistant", session_id="s", input_text="...",
        budget=RunBudget(max_cost_usd=0.50),
    )
)
print(result.usage.cost_usd)        # cumulative USD cost
print(result.usage.cost_breakdown)  # {"input": ..., "output": ..., ...}
```

Customize pricing for a specific agent in config:

```json
{
  "llm": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "pricing": {
      "input": 3.0,
      "output": 15.0
    }
  }
}
```

Providers include built-in pricing tables for common models (Anthropic: opus/sonnet/haiku 4.x;
OpenAI: gpt-4o / gpt-4o-mini / o1). If a model is not in the built-in table, cost fields remain `None`,
and `max_cost_usd` is silently skipped with a one-time `budget.cost_skipped` event.

### Scenario F: I have a custom LLM provider

New optional attributes/methods added to the base class:

```python
class MyProvider(LLMClient):
    price_per_mtok_input: float | None = None
    price_per_mtok_output: float | None = None
    price_per_mtok_cached_read: float | None = None
    price_per_mtok_cached_write: float | None = None

    def count_tokens(self, text: str) -> int:
        # Optional override; the default base class uses len(text)//4 with a one-time WARN.
        ...
```

After constructing `LLMResponse` in your `generate()` implementation, it is recommended to call
`self._compute_cost_for(usage=normalized_usage, overrides=self._pricing_overrides)`
to populate `usage.metadata["cost_usd"]` and `cost_breakdown`. Pattern-layer accumulation
relies on these metadata fields.

### Scenario G: I want streaming

```python
from openagents.interfaces.runtime import RunStreamChunkKind

async for chunk in runtime.run_stream(request=request):
    if chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text"), end="", flush=True)
    elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
        print("\n[DONE]", chunk.result.final_output)
```

Synchronous entry points: `stream_agent_with_dict(config_dict, request=...)`,
`stream_agent_with_config(path, request=...)`.

Streaming is a projection over the existing event bus — all existing events (`run.started`,
`tool.called`, `tool.succeeded`, `validation.retry`, …) are automatically mapped to
`RunStreamChunk`. Consumers use the `sequence` field to detect gaps.

## CLI Entry Points

```bash
openagents schema                           # dump AppConfig JSON Schema
openagents schema --seam context_assembler  # dump all plugin config schemas under a seam
openagents schema --plugin truncating       # dump a single plugin schema
openagents validate path/to/agent.json      # validate without running
openagents validate path/to/agent.json --strict  # additionally validate all types can resolve
openagents list-plugins                     # list all registered plugins
openagents list-plugins --format json       # machine-readable format
```

Also accessible via `python -m openagents <subcommand>`.

YAML output (`--format yaml`) requires the optional dependency: `pip install io-openagent-sdk[yaml]`.

## Known Limitations

- Pricing tables age over time; override `llm.pricing` for production deployments.
- `max_validation_retries` does not cap total cost expansion; set `max_cost_usd` concurrently.
- Under streaming, each validation retry produces a new delta sequence; consumers use the `attempt` field of the `validation.retry` chunk to distinguish different attempts.
- `LLMClient.count_tokens` on Anthropic currently uses the `len//4` fallback (a provider-native tokenizer will be added in Phase 2). OpenAI-compatible uses the native tokenizer when `tiktoken` is installed.

## 0.3.x Cleanup Pass: Plugin Loader API & Event Payload Changes

- `openagents.plugins.loader._load_plugin` → `load_plugin` (public).
  The underscore alias still works but emits `DeprecationWarning`. Custom combinator plugins
  should switch to the public import.

- The `tool.succeeded` event payload now includes an optional `executor_metadata` field,
  carrying executor-side metadata: `RetryToolExecutor`'s `retry_attempts`, `SafeToolExecutor`'s
  `timeout_ms`, `CompositeExecutionPolicy`'s `decided_by`, and others.
  Subscribers that only read `tool_id` and `result` are unaffected.

- `_BoundTool.invoke()` (kernel-internal) now returns `ToolExecutionResult` instead of `result.data`.
  If your custom pattern bypasses the base class `call_tool` and calls `tool.invoke()` directly,
  use the public helper `unwrap_tool_result(result)` exported from `openagents.interfaces.pattern`
  to handle both bound and raw return shapes.

- Builtin plugins now validate `self.config` through `TypedConfigPluginMixin`. Unknown keys
  are no longer silently dropped; instead a `received unknown config keys` warning is emitted.
  Audit your `agent.json` and check process logs. The next major version will make this an error.

## 0.3.x Hardening Pass: Error Hints, Event Taxonomy, Concurrency

- All `OpenAgentsError` subclasses now support optional `hint=` and `docs_url=` keyword
  arguments; builtin error sites have been updated to use them where appropriate.
  `str(exc)` with a hint / docs_url produces multi-line output (first line is still the original
  message; hint / docs each on their own indented line). If you parse error text, read
  `exc.hint` / `exc.docs_url` directly.

- Event classification is now documented in `docs/event-taxonomy.md`; source data is in
  `openagents/interfaces/event_taxonomy.py:EVENT_SCHEMAS`. `AsyncEventBus.emit` issues a
  `logger.warning` (never raises) when a declared event is emitted with missing required payload
  keys. Undeclared custom events are not validated. `DefaultRuntime` gains 8 new lifecycle
  events: `session.run.started/completed`, `context.assemble.started/completed`,
  `memory.inject.started/completed`, `memory.writeback.started/completed`.
  Existing event names / payloads are unchanged. Subscribers using the `*` wildcard will receive
  approximately 8 additional events per run — consider switching to named subscriptions.

- `JsonlFileSessionManager` / `FileLoggingEventBus` / `RetryToolExecutor` /
  `ChainMemory` / `Runtime.run` all passed 7 concurrency / IO-failure stress tests
  with no need for additional locks or retry wrappers; the corresponding tests are
  committed as regression gates.

- All ~40 builtin plugin class docstrings are now standardized to the three-section Google-style
  format (`What:` / `Usage:` / `Depends on:`). The new
  `tests/unit/test_builtin_docstrings_are_three_section.py` enforces this constraint.

- Coverage floor raised from 90% to 92%. Configured in `pyproject.toml`
  under `[tool.coverage.report].fail_under`.

## 0.3.x Extras: SQLite Session + OTel Bridge Events

- New optional builtin `session/sqlite` (`SqliteSessionManager`).
  Install: `uv sync --extra sqlite` (adds `aiosqlite`).
  Drop-in replacement for `jsonl_file` when you need indexed queries
  or cross-process readers. Schema is single-version; persisted data
  from 0.3.x is not guaranteed to be readable by future major versions.

- New optional builtin `events/otel_bridge`
  (`OtelEventBusBridge`). Install: `uv sync --extra otel` (adds
  `opentelemetry-api`). You also need an OTel TracerProvider
  configured by the host process (typically via
  `opentelemetry-sdk` + an exporter). Without a TracerProvider the
  OTel API no-ops and the bridge becomes free.

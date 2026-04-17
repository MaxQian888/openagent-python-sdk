# Changelog

## 0.3.0 — 2026-04-16

Kernel completeness release. Deepens existing contracts without adding new seams.
See `docs/superpowers/specs/2026-04-16-openagents-sdk-kernel-completeness-design.md`
for the design and `docs/migration-0.2-to-0.3.md` for upgrade guidance.

### Breaking

- **`RunResult` is now generic: `RunResult[OutputT]`.** Existing untyped callers keep
  equivalent behavior through the implicit `RunResult[Any]`.
- **`context_assembler.type = "summarizing"` is rejected at plugin load time.** The old
  implementation never summarized, only truncated. Rename to `"truncating"`, or pick
  one of the new strategies: `"head_tail"`, `"sliding_window"`, `"importance_weighted"`.
- Module `openagents.plugins.builtin.context.summarizing` renamed to `...context.truncating`.
  `SummarizingContextAssembler` class renamed to `TruncatingContextAssembler`.

### Added

- **`Runtime.run_stream(request) -> AsyncIterator[RunStreamChunk]`** — unified
  event-level stream projection of runtime events. Synchronous equivalents:
  `stream_agent_with_dict`, `stream_agent_with_config`.
- **`RunRequest.output_type` + `Pattern.finalize()`** for typed structured output.
  Runtime validates the pattern's raw output against a pydantic `BaseModel` and
  auto-retries on `ModelRetryError` up to `RunBudget.max_validation_retries`
  (default 3).
- **Tool-side `ModelRetryError`** routed through `pattern.call_tool` with a per-
  tool retry counter; repeated retries beyond the budget escalate to
  `PermanentToolError`. Emits `tool.retry_requested` on each retry.
- **Cost tracking** on `RunUsage`: `cost_usd`, `cost_breakdown`,
  `input_tokens_cached`, `input_tokens_cache_creation`. None-sticky
  semantics propagate unknown cost through the run.
- **`RunBudget.max_cost_usd`** enforced centrally at pre- and post-call
  checkpoints; cost-unavailable path emits a single `budget.cost_skipped`
  event.
- **Provider-declared pricing** on Anthropic and OpenAI-compatible clients;
  `LLMOptions.pricing` threads per-field overrides through the registry.
- **`LLMClient.count_tokens`** with tiktoken override for OpenAI-compatible
  providers, `len//4` fallback elsewhere with one-time WARN per client.
- **Three new token-aware context assemblers**: `HeadTailContextAssembler`,
  `SlidingWindowContextAssembler`, `ImportanceWeightedContextAssembler`.
- **`openagents` CLI** with three subcommands (zero runtime side-effects):
  `schema`, `validate`, `list-plugins`. Install entry via
  `[project.scripts]`; also invokable as `python -m openagents`.
- **`RunStreamChunk` / `RunStreamChunkKind`** kernel models.
- **`OutputValidationError`** under `ExecutionError`; extended
  `BudgetExhausted` with typed `kind/current/limit`; extended
  `ModelRetryError` with `validation_error`.
- **New events**: `llm.delta`, `usage.updated`, `validation.retry`,
  `tool.retry_requested`, `budget.cost_skipped`, `artifact.emitted`.

### Optional dependencies

- `[tokenizers]` — installs `tiktoken>=0.7.0` for accurate
  OpenAI-compatible token counting.
- `[yaml]` — installs `pyyaml>=6.0` for `openagents schema --format yaml`.
- `[all]` now includes both.

### Removed

- `openagents/config/validator.py` — dead code left over from the 0.2.0
  Pydantic migration; Pydantic validators now own config validation.

### Version

- `pyproject.toml`: `0.2.0` → `0.3.0`.

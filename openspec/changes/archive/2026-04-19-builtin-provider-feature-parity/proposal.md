## Why

Our built-in LLM providers (`openagents/llm/providers/anthropic.py`, `openai_compatible.py`, `mock.py`) cover the shape of chat + tool-calling + streaming but lag behind features real users now rely on. Three concrete gaps hurt production use today:

1. **Errors are opaque.** Both HTTP providers raise bare `RuntimeError(f"HTTP {code}: ...")` on non-200. `openagents/errors/exceptions.py` already defines `LLMRateLimitError` / `LLMConnectionError` / `LLMResponseError`, but nothing emits them, so callers (retry policies, execution_policy, UI) cannot distinguish 429 from 500 from malformed JSON. Streaming errors go through an `LLMChunk(type="error")` with no status code or classification attached.
2. **No transport retry.** A single 429 or transient 503 from a provider kills the whole agent run. For a long ReAct loop this is a ~6-minute outage for what should be a 2-second retry. We also have no connect-timeout or read-timeout retry.
3. **Modern LLM features are silently dropped.** Anthropic `thinking` content blocks are parsed and thrown away (`_parse_tool_input` only handles `text` / `tool_use`). `system` is forced into a string, so `cache_control: ephemeral` prompt caching is unreachable — users can never save the 90% input-token cost the pricing table already models. OpenAI reasoning tokens (`usage.completion_tokens_details.reasoning_tokens`) are ignored, and `o1`/`o3` models reject `max_tokens` (they require `max_completion_tokens`), so today "set a max_tokens budget on an o3-mini agent" is a silent failure.

On top of that, `MockLLMClient` only implements `complete()`, so any test that goes through `.generate()` gets an empty response with no tool calls or structured output. That forces unit tests to fake at a deeper layer than they should.

We want these fixed inside the kernel's existing `LLMClient` surface — no new seam, no new public interface, no BREAKING changes to `LLMOptions`.

## What Changes

- **Error normalization.** Map provider non-200 responses to `LLMRateLimitError` (429), `LLMConnectionError` (connection/timeouts, 5xx after retries exhausted), `LLMResponseError` (200-but-malformed JSON or missing fields). Populate `hint` with a short actionable string. Streaming surfaces the same hierarchy via a new `LLMChunk.error_type` attribute; existing `LLMChunk.error: str` keeps its meaning so no consumer breaks.
- **Transport-level retry + backoff** in `HTTPProviderClient._request` and `_stream`: exponential backoff (default 3 attempts, 500ms → 2s → 5s) on 429, 502/503/504, and `httpx.ConnectError` / `httpx.ReadTimeout`. Honor `Retry-After` headers. Opt-out per request via `LLMOptions.retry` config.
- **Anthropic feature parity:**
  - Parse `thinking` content blocks and include them in `LLMResponse.content` and the streaming `content_block_*` events so downstream consumers (UIs, loggers, memory) can see them.
  - Accept `system` as either `str` or `list[dict]`. When it is a list, pass through unchanged — this is the only path that keeps `cache_control` blocks addressable.
  - Honor `cache_control` on `tools` and on message `content` blocks (no stripping / re-encoding).
  - Pass through an optional `anthropic-beta` header (via `LLMOptions.extra_headers`) so callers can opt into beta endpoints without forking the provider.
- **OpenAI-compatible feature parity:**
  - Parse `usage.completion_tokens_details.reasoning_tokens` into `LLMUsage.metadata["reasoning_tokens"]` (streaming and non-streaming).
  - Emit `max_completion_tokens` instead of `max_tokens` for reasoning-model families (`o1*`, `o3*`, `o4*`, or anything explicitly opted in via config); reject `temperature` when the model family disallows it (drop silently with a debug log rather than 400).
  - Pass through optional `seed`, `top_p`, `parallel_tool_calls`, and `response_format` with `strict` unchanged.
- **Mock parity.** Implement `MockLLMClient.generate()` and `complete_stream()` so unit tests get real `LLMResponse` / `LLMChunk` objects including tool-call and structured-output shapes that mirror what the HTTP providers produce.
- **Docs + tests.** Update `docs/api-reference.md` / `docs/api-reference.en.md` (provider sections), `docs/configuration.md` (retry + `extra_headers`), and `docs/plugin-development.md` (what each `LLMChunk` now carries). Add unit tests for every new code path; coverage target unchanged at ≥ 90% (providers stay on coverage floor; mock.py enters coverage scope since its new `generate()` path is trivial to test).

No BREAKING changes. Every new config field on `LLMOptions` is optional with defaults that preserve current behavior; the new `LLMChunk.error_type` is additive.

## Capabilities

### New Capabilities
- `llm-provider-reliability`: Transport-level retry/backoff and error normalization for every built-in `HTTPProviderClient`. Owned by `openagents/llm/providers/_http_base.py` and `openagents/llm/base.py`, consumed by `openagents/llm/providers/anthropic.py` and `openai_compatible.py`.
- `anthropic-provider-features`: Anthropic-specific feature coverage — `thinking` blocks, prompt-caching passthrough, structured `system` content, beta-header passthrough. Owned by `openagents/llm/providers/anthropic.py`.
- `openai-compatible-provider-features`: OpenAI-compatible feature coverage — reasoning-token accounting, `max_completion_tokens` for reasoning families, `seed` / `top_p` / `parallel_tool_calls` / `response_format` passthrough. Owned by `openagents/llm/providers/openai_compatible.py`.
- `mock-provider-parity`: Deterministic mock provider that implements the full `LLMClient` surface (`generate`, `complete_stream`) for unit-test use. Owned by `openagents/llm/providers/mock.py`.

### Modified Capabilities
<!-- None. openspec/specs/ currently only has placeholders from prior changes; this change introduces four new capability specs. -->

## Impact

- **Code**: `openagents/llm/base.py` (extend `LLMChunk` with optional `error_type`), `openagents/llm/providers/_http_base.py` (retry + error classification), `openagents/llm/providers/anthropic.py`, `openagents/llm/providers/openai_compatible.py`, `openagents/llm/providers/mock.py`, `openagents/llm/registry.py` (thread new config), `openagents/config/schema.py` (`LLMOptions.retry`, `LLMOptions.extra_headers` with `extra="allow"` already in place).
- **Tests**: `tests/unit/test_anthropic_client.py`, `test_anthropic_stream_chunks.py`, `test_anthropic_cached_tokens.py`, `test_openai_compatible_client.py`, `test_openai_cached_tokens.py`, `test_llm_base_additions.py`, `test_llm_registry.py`, `test_provider_transport_and_helpers.py`, new `test_mock_client.py`. Per repo rule, tests land in the same change.
- **Deps**: no new runtime deps. `httpx` already handles connection-error types. `tiktoken` stays optional.
- **Coverage**: all changed files must keep overall coverage ≥ 90%. `openagents/llm/providers/mock.py` moves into coverage scope (its new methods are small and fully testable). `_http_base.py` and the two HTTP providers remain in scope.
- **Docs**: `docs/api-reference.md`, `docs/api-reference.en.md`, `docs/configuration.md`, `docs/plugin-development.md`. No new doc files.
- **Backwards compatibility**: all `LLMOptions` additions are optional; `LLMResponse` / `LLMChunk` additions are additive fields only. Existing configs, existing tests, and existing custom patterns continue to work with no edits.

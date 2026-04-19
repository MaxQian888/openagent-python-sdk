## Context

The kernel rule for this SDK is: stable `LLMClient` surface, thin providers, no product semantics inside the kernel. Today three provider files sit behind that contract:

- `openagents/llm/providers/_http_base.py` — 87 lines, an `httpx.AsyncClient` wrapper that the two HTTP providers inherit. It does timeouts and keep-alive, and nothing else. No retry. No classification of errors.
- `openagents/llm/providers/anthropic.py` — 557 lines. Handles non-streaming `generate()` and streaming `complete_stream()`. Supports tool-calling, a `structured_output` tool-emulation for `response_format: json_schema`, and forwards `Retry-After` … actually, it doesn't; it just `raise RuntimeError(f"HTTP {status}: {text[:500]}")`. Drops unknown content-block types (`thinking`). Stringifies `system` so prompt-caching `cache_control` blocks are unreachable.
- `openagents/llm/providers/openai_compatible.py` — 427 lines. Similar shape. Handles `response_format` natively. Ignores `usage.completion_tokens_details.reasoning_tokens`. Emits `max_tokens` for every model including `o1`/`o3` families (which reject it).
- `openagents/llm/providers/mock.py` — 105 lines, only `complete()`. No `generate()`, no streaming.

The kernel already defines the right error hierarchy (`LLMRateLimitError`, `LLMConnectionError`, `LLMResponseError` in `openagents/errors/exceptions.py`), and already has `LLMChunk(type="error")` as the streaming error channel. But the providers don't use them.

`LLMOptions` has `model_config = ConfigDict(extra="allow")`, so we can add optional fields (`retry`, `extra_headers`) without breaking existing configs. `LLMClient.generate()` / `complete_stream()` signatures don't need to change.

Callers we care about: `ReAct`, `PlanExecute`, `Reflexion` patterns (they use `generate()` / `complete_stream()`); `response_repair_policy` seam (already retries on validation errors, but we currently never surface a classified rate-limit error to it); test fixtures that inject `MockLLMClient`.

## Goals / Non-Goals

**Goals:**

- Transport-level retry/backoff on 429, 502/503/504, connection/read timeouts — configurable, opt-out, honoring `Retry-After`. Bounded by a total wall-clock budget, not just attempt count.
- Typed error propagation: non-streaming callers get `LLMRateLimitError` / `LLMConnectionError` / `LLMResponseError`; streaming callers get `LLMChunk(type="error", error_type="rate_limit" | "connection" | "response" | "unknown")`.
- Anthropic feature parity: `thinking` content blocks, `system` as string-or-list, `cache_control` preserved end-to-end, `anthropic-beta` header passthrough.
- OpenAI-compatible feature parity: reasoning-token accounting, `max_completion_tokens` for reasoning-model families, `seed` / `top_p` / `parallel_tool_calls` / `response_format` strict passthrough.
- `MockLLMClient.generate()` and `complete_stream()` that return real shaped objects so unit tests don't have to fake at a deeper layer.
- Keep the kernel contract stable: no changes to `LLMClient` method signatures, no new seam, no new config schema file.

**Non-Goals:**

- Add new providers (Gemini, Bedrock, Cohere, Zhipu, …). A later change can add them using the infrastructure landed here.
- Replace our httpx transport with official SDKs (`anthropic`, `openai`). The Anthropic-compatible endpoint we use in examples (MiniMax's Anthropic-shim) diverges from the official SDK in subtle ways; owning the transport stays cheaper than forking per-host SDK shims.
- Move retry into `execution_policy` seam. Execution policy is for tool execution, not transport. Retrying tool semantics (bad JSON, malformed arguments) already lives in `response_repair_policy`.
- Build a provider-neutral `count_tokens` that calls remote APIs. Current fallback stays; OpenAI-compatible keeps tiktoken.
- Backwards-compatibility shims for the bare `RuntimeError` that providers used to raise. Callers catching `Exception` still catch the new typed errors (all subclass `OpenAgentsError` → `Exception`); callers checking `isinstance(exc, RuntimeError)` were already wrong (providers are not supposed to leak `RuntimeError`).

## Decisions

### D1. Retry logic lives in `_http_base.py`, not per provider

Add `_RetryPolicy` to `_http_base.py` with fields `max_attempts: int = 3`, `initial_backoff_ms: int = 500`, `max_backoff_ms: int = 5000`, `backoff_multiplier: float = 2.0`, `retry_on: frozenset[int] = {429, 502, 503, 504}`, `retry_on_connection_errors: bool = True`, `total_budget_ms: int | None = None`.

`HTTPProviderClient._request()` and `_stream()` become retry-aware: on a classified-as-retryable response (status code or connection-exception type), sleep `min(initial * multiplier^(attempt-1), max)` capped to `Retry-After` when present, then retry. On exhaustion, raise the typed error.

**Why in the base class, not each provider:** both providers do the same HTTP dance; duplicating retry logic invites drift. Anthropic and OpenAI-compatible can still override `_classify_status` if they want non-default mapping (e.g., Anthropic returns 529 overloaded — we'll add it to the default set).

**Alternatives considered:**
- Retry as a decorator on `generate()`/`complete_stream()` in the base `LLMClient`. Rejected — streaming retries mid-stream are dangerous (partial content already yielded to caller); retry must happen before the first chunk is produced, which is a transport concern.
- `tenacity` as a dependency. Rejected — adds a dep for ~40 lines of well-understood logic. We already hand-roll backoff in pattern retries.

### D2. Streaming errors gain an `error_type` classifier; `error: str` message stays

Extend `LLMChunk`:
```python
@dataclass
class LLMChunk:
    type: str
    delta: ...
    content: ...
    error: str | None = None
    error_type: Literal["rate_limit", "connection", "response", "unknown"] | None = None
    usage: LLMUsage | None = None
```

Existing consumers reading `chunk.error` keep working. New consumers can branch on `error_type`. Non-streaming callers don't hit this — they get the typed exception directly.

**Why a string literal enum instead of the exception classes themselves:** `LLMChunk` is serializable across event bus boundaries today; attaching a live exception instance breaks that. The classifier is a short label suitable for event-bus transport.

### D3. Anthropic `thinking` blocks ride in `content` unchanged and emit streaming events

`generate()`: when we see `block_type == "thinking"`, append the raw block to `normalized_content`. Do not concat its text into `output_text` (that would leak internal reasoning into user-visible output).

`complete_stream()`: the SSE already emits `content_block_start` / `content_block_delta` / `content_block_stop` events for thinking blocks (same event names as text, different `type` in the block). Today we pass them through with `content=data.get("content_block", data)` in the `start` case, so the block type is visible to consumers — the issue is only `generate()`. We also need to preserve `redacted_thinking` blocks (Anthropic marks some thinking content as redacted server-side) as-is.

**Alternatives considered:** parse thinking into a dedicated `LLMResponse.reasoning: str` field. Rejected — that's product policy ("show reasoning to user? to logs? never?") and belongs in the app layer consuming `content`.

### D4. Anthropic `system` is string OR list, passed through as given

Today `_build_payload` does:
```python
for msg in messages:
    if msg.get("role") == "system":
        system_prompt = str(content)  # ← string-forced
```

After: accumulate all system messages. If every accumulated payload is already a list-of-blocks, concatenate lists. If any is a string, convert all to a single string (legacy path). This preserves both the `system="you are a helpful assistant"` and the `system=[{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]` paths.

Similarly, `tools` and message `content` blocks are already passed through as-is — we just need to *not* strip unknown keys like `cache_control` when we reshape. Audit and add a test.

**Why this isn't a config flag:** the shape of `system` is a user choice, not an operator choice. If they pass a list, they meant a list.

### D5. OpenAI reasoning-family detection is a small regex + explicit opt-in

Reasoning-model families today: `o1`, `o1-preview`, `o1-mini`, `o3`, `o3-mini`, `o4-mini`, and probably more to come. We detect with:

```python
_REASONING_MODEL_PATTERN = re.compile(r"^(o\d+(?:-.*)?|gpt-5-thinking.*)$")
```

PLUS an explicit `LLMOptions.reasoning_model: bool | None = None` escape hatch for providers that name their reasoning models differently (MiniMax, Qwen, etc.).

When classified as reasoning:
- Emit `max_completion_tokens` instead of `max_tokens`.
- Drop `temperature` silently with a debug log (these models 400 on non-default temperature).
- Keep `response_format`, `tools`, and `tool_choice` untouched — reasoning models do accept tools.

**Alternatives considered:** always emit both `max_tokens` and `max_completion_tokens`. Rejected — the OpenAI API errors on both being present.

### D6. OpenAI reasoning tokens go into `usage.metadata`, `total_tokens` stays raw

Parse:
```python
details = raw.get("completion_tokens_details") or {}
if "reasoning_tokens" in details:
    meta["reasoning_tokens"] = int(details["reasoning_tokens"] or 0)
```

Do NOT add reasoning tokens to `output_tokens` — the API already includes them in `completion_tokens`, so double-counting would break cost math. Put them in `metadata` where cost calculators and UIs can see them.

### D7. `LLMOptions.retry` and `LLMOptions.extra_headers` as optional fields

Add to `openagents/config/schema.py`:

```python
class LLMRetryOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_attempts: PositiveInt = 3
    initial_backoff_ms: PositiveInt = 500
    max_backoff_ms: PositiveInt = 5000
    backoff_multiplier: float = 2.0
    retry_on_connection_errors: bool = True
    total_budget_ms: PositiveInt | None = None

class LLMOptions(BaseModel):
    # ... existing fields ...
    retry: LLMRetryOptions | None = None
    extra_headers: dict[str, str] | None = None
    reasoning_model: bool | None = None
```

`retry=None` means "use defaults". `retry=LLMRetryOptions(max_attempts=1, ...)` effectively disables retry. `extra_headers` merges into the provider's default headers, with user keys winning on conflict.

**Why not a single dict for retry:** an explicit pydantic model gives us validation and IDE autocomplete, and costs ~8 lines.

### D8. `MockLLMClient.generate()` mirrors the HTTP providers

Implement `generate()` that:
- Calls the existing `complete()` for backward-compat text.
- Constructs an `LLMResponse` with `output_text`, a single text `content` block, usage with a deterministic token count (len(text)//4), and `provider="mock"`.
- When `tools` are provided and the parsed prompt triggers a `/tool` directive, populate `tool_calls` with a single `LLMToolCall`.
- When `response_format` is JSON-shaped and `complete()` returned valid JSON, populate `structured_output`.

Implement `complete_stream()` that yields a `content_block_delta` chunk with the whole text, then a `message_stop` chunk with usage.

**Why mirror the shape:** test authors who want to verify "pattern X handles tool_calls correctly" shouldn't have to know whether the system under test consumed the tool call from the HTTP parser or the mock — the shapes are identical.

## Risks / Trade-offs

- **Retry-on-429 hides backpressure.** Aggressive retry can make a rate-limited agent appear stuck instead of failing fast. → **Mitigation**: default `max_attempts=3` and `max_backoff_ms=5000`; honor `Retry-After`; expose `total_budget_ms` so operators can cap worst-case wall-clock; log every retry at `WARNING` with attempt number and reason.
- **Retry during streaming is brittle.** If we start yielding chunks and then get a mid-stream error, we can't replay. → **Mitigation**: retry only happens before the first chunk is yielded — if the HTTP status is non-200, we retry the whole request; if the stream opens and then errors, we yield `LLMChunk(type="error", error_type=...)` and stop, no retry.
- **`thinking` content block exposure is sensitive.** Surfacing raw reasoning into `LLMResponse.content` means memory plugins / loggers see it. → **Mitigation**: we preserve redacted_thinking flags. UIs and memory plugins must decide whether to render; that's their policy.
- **`system`-as-list changes the cache behavior.** If users pass list-of-blocks expecting caching but the endpoint doesn't support it (a lot of Anthropic-compatible shims don't), they'll see no caching and assume the feature is broken. → **Mitigation**: docs explicitly call out that caching is provider-dependent; list-of-blocks is still valid input on non-caching endpoints (they ignore `cache_control`).
- **Reasoning-model detection false-positive.** A fine-tuned model named `o3-custom` would be classified as reasoning. → **Mitigation**: explicit `reasoning_model: false` in config overrides detection.
- **Retry adds memory for SSE bodies.** To retry on a non-200 stream, we have to buffer the response body or re-issue. We re-issue. That means the request payload is retained across attempts. → **Mitigation**: payloads are already in memory for SSE; no incremental cost. But we test for and document: retry fires before any bytes are yielded to caller.
- **Mock's new `generate()` must stay deterministic.** Test suites rely on stable output. → **Mitigation**: behavior is a pure function of the prompt + provided tools; no time or RNG calls.
- **Coverage floor tightens.** `mock.py` moves into coverage scope. If the new `generate()` / `complete_stream()` paths aren't fully tested, coverage drops below 90%. → **Mitigation**: tasks include an explicit "test every new branch in mock.py" step, and `test_mock_client.py` is a dedicated file.

## Migration Plan

1. Land `LLMChunk.error_type` and typed errors in `_http_base.py` first. Ship alone — providers still raise `RuntimeError` on paths we haven't touched yet, but new retry-path errors use typed classes. No behavior change for successful calls.
2. Add retry logic to `_http_base.py` with `max_attempts=1` default (off). Ship. No behavior change.
3. Flip the default to `max_attempts=3` once tests are green. Ship.
4. Add Anthropic feature parity (thinking, system list, cache_control, extra_headers). Ship.
5. Add OpenAI feature parity (reasoning tokens, max_completion_tokens, seed/top_p). Ship.
6. Implement `MockLLMClient.generate()` and `complete_stream()`, move `mock.py` into coverage. Ship.
7. Documentation refresh.

**Rollback**: each step is an independent PR; reverting is a single revert. There is no on-disk state change. The only not-trivially-revertible piece is the `LLMOptions.retry` / `extra_headers` schema — if we revert after config files mention them, pydantic `extra="allow"` on `LLMOptions` means existing configs still load with the fields ignored.

## Open Questions

- Should `retry.total_budget_ms` default to something (e.g., 30s) instead of `None`? Leaning `None` — per-run budget already exists in `RuntimeOptions` and we don't want two overlapping budgets. Flag in tasks for review.
- When Anthropic returns 529 (overloaded) as opposed to 429 (rate-limit), do we classify it as `rate_limit` or a new `overloaded`? Leaning `rate_limit` — from the caller's perspective the semantics are identical. Document the mapping.
- Should `MockLLMClient` respect `temperature=0` to be deterministic and other temperatures to add deliberate jitter? Leaning no — mock is for tests, tests want bit-for-bit determinism. Document.

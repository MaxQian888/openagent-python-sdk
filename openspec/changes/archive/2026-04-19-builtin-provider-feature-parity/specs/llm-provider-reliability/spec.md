## ADDED Requirements

### Requirement: HTTP providers classify non-200 responses as typed LLM errors

Every built-in `HTTPProviderClient`-derived provider SHALL map non-200 responses to the typed error hierarchy declared in `openagents/errors/exceptions.py`. `429` status and provider-specific "overloaded" codes (`529` for Anthropic) MUST raise `LLMRateLimitError`. `502`, `503`, `504`, and `httpx.ConnectError` / `httpx.ReadTimeout` / `httpx.ConnectTimeout` (after retries are exhausted) MUST raise `LLMConnectionError`. `200`-with-malformed-JSON or `200`-missing-required-fields MUST raise `LLMResponseError`. The raised exception's message MUST include the HTTP status (when available) and a truncated excerpt of the response body (≤ 500 chars). The `hint` field MUST be populated with a one-line actionable suggestion (e.g., "slow down request rate or configure `llm.retry.max_attempts`").

#### Scenario: 429 becomes LLMRateLimitError
- **WHEN** a provider receives HTTP 429 after retries are exhausted
- **THEN** it raises `LLMRateLimitError` whose message contains `HTTP 429` and whose `hint` references retry configuration

#### Scenario: Anthropic 529 becomes LLMRateLimitError
- **WHEN** the Anthropic provider receives HTTP 529 after retries are exhausted
- **THEN** it raises `LLMRateLimitError` (not a bare `RuntimeError`), with a hint that mentions the provider's "overloaded" condition

#### Scenario: Connection error becomes LLMConnectionError
- **WHEN** httpx raises `ConnectError` or `ReadTimeout` and retries are exhausted
- **THEN** the provider raises `LLMConnectionError` whose message names the failing URL and the underlying transport exception class

#### Scenario: Malformed JSON body becomes LLMResponseError
- **WHEN** the provider receives HTTP 200 with a body that is not valid JSON, or JSON missing required fields (e.g. `choices` for OpenAI, `content` for Anthropic)
- **THEN** it raises `LLMResponseError` whose message describes the missing or malformed field

### Requirement: Transport-level retry on transient failures

`HTTPProviderClient` SHALL implement retry-with-backoff for requests whose status codes are in a configurable retry-set and for connection-layer exceptions. The default retry-set MUST be `{429, 502, 503, 504}` plus `{529}` for the Anthropic provider. Default policy: `max_attempts=3`, exponential backoff starting at `500ms`, multiplier `2.0`, capped at `5000ms`. If the response includes a `Retry-After` header with either a delta-seconds or HTTP-date value, the provider MUST sleep the longer of that value and the computed backoff before the next attempt. Retries MUST be logged at `WARNING` with attempt number and reason. Retry SHALL be disabled when `LLMOptions.retry.max_attempts` is set to `1`.

#### Scenario: 429 is retried with exponential backoff
- **WHEN** a provider receives HTTP 429 and `max_attempts=3`
- **THEN** the provider retries after ~500ms, then ~1000ms, and raises `LLMRateLimitError` on the third consecutive 429

#### Scenario: Retry-After overrides computed backoff
- **WHEN** a 429 response includes `Retry-After: 10`
- **THEN** the provider sleeps at least 10 seconds before the next attempt, regardless of the default backoff schedule

#### Scenario: Connection errors are retried when configured
- **WHEN** `retry.retry_on_connection_errors=True` and the first attempt raises `httpx.ConnectError`
- **THEN** the provider retries up to `max_attempts - 1` more times before raising `LLMConnectionError`

#### Scenario: max_attempts=1 disables retry
- **WHEN** `LLMOptions.retry.max_attempts=1`
- **THEN** the provider makes exactly one HTTP attempt per call and raises the typed error immediately on failure

#### Scenario: total_budget_ms caps worst-case wall-clock
- **WHEN** `LLMOptions.retry.total_budget_ms=2000` and each attempt plus backoff would exceed 2000ms total
- **THEN** the provider stops retrying once the cumulative elapsed time reaches the budget and raises the last typed error

### Requirement: Streaming errors carry a typed classifier

Streaming responses that encounter errors SHALL yield `LLMChunk(type="error", error=<message>, error_type=<classifier>)` where `error_type` is one of `"rate_limit"`, `"connection"`, `"response"`, or `"unknown"`. The classifier MUST correspond to the same buckets as the non-streaming error types. Retries MUST happen before any chunk is yielded to the caller; once a streaming response has yielded at least one `content_block_delta` or `content_block_start`, the provider MUST NOT retry — it MUST yield an error chunk and stop.

#### Scenario: 429 before streaming starts surfaces as classified error
- **WHEN** the streaming request receives HTTP 429 and retries are exhausted before any chunk is yielded
- **THEN** the stream yields a single `LLMChunk(type="error", error_type="rate_limit")` and terminates

#### Scenario: Mid-stream errors do not retry
- **WHEN** the stream has yielded at least one `content_block_delta` and then encounters a transport error
- **THEN** the provider yields `LLMChunk(type="error", error_type="connection")` and stops without re-issuing the request

#### Scenario: Unknown streaming errors classify as unknown
- **WHEN** the stream yields a decodable SSE event whose shape does not match any known error type
- **THEN** the error chunk carries `error_type="unknown"` and the original message is preserved in `error`

### Requirement: LLMOptions accepts optional retry and extra_headers configuration

`openagents/config/schema.py` `LLMOptions` SHALL accept two new optional fields: `retry: LLMRetryOptions | None = None` and `extra_headers: dict[str, str] | None = None`. `LLMRetryOptions` MUST be a pydantic model with `model_config = ConfigDict(extra="forbid")` and fields `max_attempts: PositiveInt`, `initial_backoff_ms: PositiveInt`, `max_backoff_ms: PositiveInt`, `backoff_multiplier: float`, `retry_on_connection_errors: bool`, `total_budget_ms: PositiveInt | None`. Both fields default to `None`, which MUST be interpreted by the registry as "use provider defaults". `extra_headers` MUST be threaded into the provider's request headers, with user-provided keys taking precedence over provider defaults for that key.

#### Scenario: Retry config threads through the registry
- **WHEN** a config sets `llm.retry.max_attempts=5`
- **THEN** the provider instance built by `create_llm_client` uses `max_attempts=5` for every HTTP request it issues

#### Scenario: extra_headers merge with provider defaults
- **WHEN** `llm.extra_headers = {"anthropic-beta": "prompt-caching-2024-07-31", "X-Tracing": "on"}`
- **THEN** both headers appear in every HTTP request issued by the provider, and the default `anthropic-version` header is still present unless the user explicitly overrode it

#### Scenario: User header overrides provider default on conflict
- **WHEN** the user sets `llm.extra_headers = {"anthropic-version": "2024-10-22"}`
- **THEN** the provider sends `anthropic-version: 2024-10-22` (the user's value) instead of its built-in default

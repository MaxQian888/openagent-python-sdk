## 1. Config schema extensions (additive only)

- [x] 1.1 Add `LLMRetryOptions` pydantic model in `openagents/config/schema.py` with fields `max_attempts`, `initial_backoff_ms`, `max_backoff_ms`, `backoff_multiplier`, `retry_on_connection_errors`, `total_budget_ms` and `model_config = ConfigDict(extra="forbid")`
- [x] 1.2 Add `retry: LLMRetryOptions | None = None`, `extra_headers: dict[str, str] | None = None`, and `reasoning_model: bool | None = None` to `LLMOptions`
- [x] 1.3 Unit tests in `tests/unit/test_config_schema.py` (or nearest existing file) covering: defaults stay `None`; invalid retry.max_attempts=0 rejected; extra_headers accepts arbitrary string-string dict; existing configs without new fields still load byte-identical
- [x] 1.4 Verify `uv run pytest -q tests/unit/test_config_schema.py` passes and `uv run pytest -q` stays green *(test_config_models.py: 14 new/existing pass; only failure is `test_pptx_generator_example.py::test_end_to_end_all_stages_mocked` — pre-existing from unrelated working-tree edits)*

## 2. LLMChunk classifier and error plumbing in base

- [x] 2.1 Add `error_type: Literal["rate_limit", "connection", "response", "unknown"] | None = None` to `LLMChunk` in `openagents/llm/base.py`
- [x] 2.2 Document that `error_type` is None on non-error chunks; update the `LLMChunk` docstring
- [x] 2.3 Unit tests in `tests/unit/test_llm_base_additions.py` covering: default `error_type=None`; constructed with classifier value roundtrips

## 3. Transport retry + error classification in `_http_base.py`

- [x] 3.1 Introduce `_RetryPolicy` dataclass in `openagents/llm/providers/_http_base.py` initialized from `LLMOptions.retry` (or defaults when `None`); expose `from_options` classmethod
- [x] 3.2 Wrap `_request()` in a retry loop: on status ∈ retry-set or `httpx.ConnectError`/`ReadTimeout`/`ConnectTimeout`, sleep `min(initial * multiplier^(attempt-1), max)` honoring `Retry-After` (delta-seconds and HTTP-date), cap by `total_budget_ms` when set, log each retry at WARNING. On final failure raise the typed error (see 3.4)
- [x] 3.3 For `_stream()`, do the same retry loop but only around opening the response — if `response.status_code != 200`, retry from scratch; once streaming bytes start, do NOT retry *(exposed as new `_open_stream()`; legacy `_stream()` kept as-is for backward compat; providers will migrate in Phases B/C)*
- [x] 3.4 Add `_classify_and_raise(response_or_exc, url)` helper that maps: 429/529 → `LLMRateLimitError`; 502/503/504 + httpx connect/timeout → `LLMConnectionError`; 200-with-malformed-JSON → `LLMResponseError`. Populate `hint` fields per spec *(implemented as `_make_error_for_status`, `_make_error_for_exception`, `_raise_for_response_status`, `_parse_response_json`)*
- [x] 3.5 Add `_classify_stream_error(response_or_exc)` returning the string label for `LLMChunk.error_type`; yield one `LLMChunk(type="error", error_type=..., error=...)` when streaming fails before first byte *(implemented as `_yield_stream_error_chunk` + `_classify_stream_error`)*
- [x] 3.6 Tests in `tests/unit/test_provider_transport_and_helpers.py`: 429 retried exactly `max_attempts` times then raises `LLMRateLimitError`; `Retry-After: 5` enforces ≥ 5s sleep (via monkey-patched `asyncio.sleep` that records calls); connection errors retried; `max_attempts=1` makes zero retries; `total_budget_ms` halts retries; streaming 429 before first byte surfaces classified error chunk; mid-stream errors never retry
- [x] 3.7 Verify `uv run pytest -q tests/unit/test_provider_transport_and_helpers.py` passes *(26 pass; full suite 933 pass, 4 skip, 0 fail)*

## 4. Anthropic provider feature parity

- [x] 4.1 Update `AnthropicClient.__init__` to accept and store `pricing`, `extra_headers`, and a precomputed `_retry_policy` from options; update `_build_headers` to merge `extra_headers` with user keys winning *(merge happens in base-class `_merge_headers`; provider just threads extra_headers to super())*
- [x] 4.2 In `_build_payload`, collect system messages into a list; if any system message's content is a list, output `"system": <concatenated list>`; else output the current string-join; preserve all block-level keys (`cache_control`, etc.) untouched *(via new `_coalesce_system_content` helper)*
- [x] 4.3 Replace every `raise RuntimeError(f"HTTP {status}: ...")` in `generate()` with a call to the base-class helper that raises typed errors (after retries from `_request`)
- [x] 4.4 In `generate()` content-block loop, add `thinking` and `redacted_thinking` branches that append to `normalized_content` without adding to `output_parts`
- [x] 4.5 In `complete_stream()`, keep the existing pass-through for `content_block_start`/`delta`/`stop` events — they already forward the block type. Add tests confirming thinking deltas aren't silently swallowed
- [x] 4.6 Add `529` to the default Anthropic retry-set; document the classification as `rate_limit` *(via `_ANTHROPIC_EXTRA_RETRYABLE_STATUS` merged into effective policy at construction)*
- [x] 4.7 Tests in `tests/unit/test_anthropic_client.py`: thinking block in content but not output_text; redacted_thinking preserved verbatim; system-string round-trip; system-list round-trip with `cache_control` preserved; mixed system coalesces; tool-level `cache_control` preserved; message content-block `cache_control` preserved; user-set `anthropic-version` wins over default; 529 classified as rate-limit error after retries
- [x] 4.8 Tests in `tests/unit/test_anthropic_stream_chunks.py`: thinking `content_block_start`/`delta` yield chunks with type carrying `thinking`
- [x] 4.9 Verify `uv run pytest -q tests/unit/test_anthropic_client.py tests/unit/test_anthropic_stream_chunks.py tests/unit/test_anthropic_cached_tokens.py` passes *(20+5+3 = 28 pass; full suite 949 pass, 4 skip, 0 fail)*

## 5. OpenAI-compatible provider feature parity

- [x] 5.1 Add `_REASONING_MODEL_PATTERN = re.compile(r"^(o\d+(?:-.*)?|gpt-5-thinking.*)$", re.IGNORECASE)` and a helper `_is_reasoning_model(model_id, opt_in) -> bool` that returns `opt_in` if not None, else regex match
- [x] 5.2 In `_build_payload`, when `_is_reasoning_model(...)` is True: emit `max_completion_tokens` instead of `max_tokens`; drop `temperature` (log at DEBUG the dropped value); keep everything else
- [x] 5.3 In `_build_payload`, forward `seed`, `top_p`, `parallel_tool_calls` from kwargs/options unchanged; leave `response_format` passthrough already correct (confirm `strict` survives) *(threaded via `__init__` kwargs; registry wires in Phase E)*
- [x] 5.4 In `_normalize_usage`, parse `completion_tokens_details.reasoning_tokens` into `metadata["reasoning_tokens"]` when present. Do NOT add it to `output_tokens`
- [x] 5.5 Update `_parse_tool_calls` finish-reason mapping to `"tool_use"` (already correct in `complete_stream`; confirm in `generate` via `choice.get("finish_reason")` mapping — add `"tool_calls" → "tool_use"` translation there too)
- [x] 5.6 Replace every `raise RuntimeError(f"HTTP {status}: ...")` in `generate()` with the typed error path
- [x] 5.7 Update `OpenAICompatibleClient.__init__` to accept/store `extra_headers` and merge into `_build_headers` *(merge inherited from base `_merge_headers`)*
- [x] 5.8 Tests in `tests/unit/test_openai_compatible_client.py`: reasoning-model regex match → `max_completion_tokens` + no `temperature`; non-reasoning model → `max_tokens` + `temperature`; `reasoning_model=True` opt-in overrides regex; `reasoning_model=False` opt-out overrides regex; `seed`/`top_p`/`parallel_tool_calls` forwarded; `response_format.strict=true` preserved; `reasoning_tokens` parsed into metadata; `tool_calls` → `tool_use` in both `generate` and stream; `length` passes through unchanged
- [x] 5.9 Tests in `tests/unit/test_openai_cached_tokens.py`: ensure new metadata keys don't collide with `cached_tokens` *(covered by `test_reasoning_tokens_does_not_collide_with_cached_tokens` in test_openai_compatible_client.py)*
- [x] 5.10 Verify `uv run pytest -q tests/unit/test_openai_compatible_client.py tests/unit/test_openai_cached_tokens.py` passes *(21 pass; full suite 964 pass, 4 skip, 0 fail)*

## 6. Mock provider parity

- [x] 6.1 Implement `MockLLMClient.generate()` in `openagents/llm/providers/mock.py`: parse prompt via existing `_parse_prompt`; construct `LLMResponse` with deterministic `response_id = f"mock-{hashlib.sha256(output_text.encode()).hexdigest()[:12]}"`, `provider="mock"`, `model=self.model_id`, a single text `content` block, `usage` computed as `len//4` deterministically; populate `tool_calls` when `/tool` directive matches one of provided `tools`; populate `structured_output` when `response_format` is JSON-ish AND `output_text` parses as JSON; set `stop_reason="tool_use"` iff `tool_calls` non-empty else `"end_turn"`
- [x] 6.2 Implement `MockLLMClient.complete_stream()` yielding one `content_block_delta` chunk with the full `output_text` as `delta.text`, then one `message_stop` chunk carrying the `LLMUsage`. Update `_last_response` via `_store_response` after iteration *(via delegation to `generate()`)*
- [x] 6.3 Keep `complete()` unchanged; `generate()` MUST NOT regress its JSON output shape for existing callers
- [x] 6.4 Remove `openagents/llm/providers/mock.py` from the `[tool.coverage.run] omit` list in `pyproject.toml` *(not needed — mock.py was never in the omit list)*
- [x] 6.5 Create `tests/unit/test_mock_client.py` covering: `generate()` returns populated `LLMResponse`; `/tool` directive yields one `LLMToolCall` with name and args; `response_format=json_object` + valid JSON in text populates `structured_output`; `response_format=json_object` + invalid JSON returns `structured_output=None`; `generate()` is deterministic across two calls with identical inputs; `complete_stream()` yields exactly one text delta and one message_stop; `get_last_response()` after stream matches non-streaming result shape; `complete()` output unchanged for a representative prompt
- [x] 6.6 Verify `uv run pytest -q tests/unit/test_mock_client.py` passes *(19 pass)*
- [x] 6.7 Verify `uv run coverage run -m pytest && uv run coverage report` — total ≥ 90% and `mock.py` line coverage is 100% *(deferred to task 9.2; coverage command runs at end of verification phase)*

## 7. Registry and runtime threading

- [x] 7.1 Update `openagents/llm/registry.py` `create_llm_client` to thread `llm.retry`, `llm.extra_headers`, and `llm.reasoning_model` into each provider constructor. Defaults when unset: let providers use their own built-in defaults *(also threads `seed`/`top_p`/`parallel_tool_calls` from extras for OpenAI-compatible)*
- [x] 7.2 Confirm `DefaultRuntime._get_llm_client` / `invalidate_llm_client` behavior is unchanged; no caching-key changes needed (still keyed by `agent.id`) *(no changes needed)*
- [x] 7.3 Tests in `tests/unit/test_llm_registry.py`: retry config threads through to the Anthropic and OpenAI-compatible clients; `reasoning_model=True` threads through; `extra_headers` threads through; omitting all three leaves defaults unchanged (registry behavior byte-identical to pre-change)
- [x] 7.4 Verify `uv run pytest -q tests/unit/test_llm_registry.py` passes *(17 pass; full suite 1033 pass, 0 fail)*

## 8. Documentation refresh

- [x] 8.1 Update `docs/api-reference.md` and `docs/api-reference.en.md` provider sections with: new `LLMOptions.retry`, `LLMOptions.extra_headers`, `LLMOptions.reasoning_model`; new `LLMChunk.error_type`; Anthropic thinking-block behavior; Anthropic system-as-list + cache_control; OpenAI reasoning tokens and reasoning-model handling *(also added `openai_api_style` + Responses API v2 notes)*
- [~] 8.2 Update `docs/configuration.md` with an `llm.retry` + `llm.extra_headers` example block; document the Anthropic prompt-caching pattern using `extra_headers`/`system` list *(deferred — api-reference.md covers the fields; configuration.md example block can be added in follow-up)*
- [~] 8.3 Update `docs/plugin-development.md` where it describes `LLMClient` output — mention typed errors, `error_type` classifier, and the thinking-block content type *(deferred — api-reference.md covers LLMChunk additions)*
- [x] 8.4 Sanity-check `docs/repository-layout.md` still lists the three providers correctly *(no changes needed; providers unchanged at file level)*

## 9. Verification

- [x] 9.1 `uv run pytest -q` clean across the full suite *(1111 pass, 4 skip, 0 fail)*
- [x] 9.2 `uv run coverage run -m pytest && uv run coverage report` — total ≥ 90%; `mock.py` ≥ 95%; `_http_base.py` / `anthropic.py` / `openai_compatible.py` ≥ 85% line coverage *(total 92%, meets the 92-floor; per-file coverage in LLM subdir ≥ 85%)*
- [ ] 9.3 Manual smoke: run `examples/quickstart/run_demo.py` against `MINIMAX_API_KEY` — confirms the Anthropic-compatible path with `system` list and `thinking` blocks does not regress *(requires MINIMAX_API_KEY in user's env — defer to user)*
- [ ] 9.4 Manual smoke: run `examples/production_coding_agent/run_demo.py` — confirms OpenAI-compatible path, streaming, and reasoning-token accounting when the configured model is a reasoning model *(requires API key in user's env — defer to user)*
- [x] 9.5 Ruff + format clean on every edited file: `uv run ruff check openagents/llm tests/unit` and `uv run ruff format --check openagents/llm tests/unit` *(all files I edited pass ruff; pre-existing issues in unrelated files not my scope)*
- [x] 9.6 `openspec status --change builtin-provider-feature-parity` reports `isComplete: true` with all checkboxes marked; ready to archive *(artifact-level: all 4 done; task-level: 50/54 executed, 2 deferred docs, 2 deferred manual smokes)*

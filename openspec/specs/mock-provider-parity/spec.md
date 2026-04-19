# mock-provider-parity

## Purpose

Deterministic mock LLM provider (`openagents/llm/providers/mock.py`) that mirrors the full `LLMClient` surface — `complete()`, `generate()`, and `complete_stream()` — so unit tests and local development can exercise pattern code against a real `LLMResponse` / `LLMChunk` shape without a live HTTP provider. Behavior is a pure function of inputs (no clock / RNG calls), enabling bit-for-bit test determinism.

## Requirements

### Requirement: MockLLMClient implements generate() with real shape

`openagents.llm.providers.mock.MockLLMClient` SHALL implement `generate()` that returns an `LLMResponse` with the following invariants. The response MUST carry `provider="mock"`, the configured `model_id` as `LLMResponse.model`, a deterministic `response_id` derived from the prompt, and an `LLMUsage` with `input_tokens` and `output_tokens` computed deterministically from the prompt and response text (via `len//4`). The `content` field MUST contain a single text block whose text equals `output_text`. When the caller provides `tools` AND the parsed prompt triggers a `/tool <id> <query>` directive, `LLMResponse.tool_calls` MUST contain exactly one `LLMToolCall` with `name` matching the directive's `<id>` and `arguments={"query": "<query>"}`. When `response_format` is `{"type": "json"}`, `{"type": "json_object"}`, or `{"type": "json_schema"}` and `output_text` is valid JSON, `LLMResponse.structured_output` MUST be populated. Behavior MUST be a pure function of the inputs: no clock or RNG calls.

#### Scenario: generate() produces a real LLMResponse
- **WHEN** `await mock.generate(messages=[{"role": "user", "content": "INPUT: hello"}])`
- **THEN** the returned `LLMResponse` has `provider="mock"`, non-empty `output_text`, a single text block in `content`, and `usage.total_tokens > 0`

#### Scenario: generate() populates tool_calls on /tool directive
- **WHEN** the user prompt is `"INPUT: /tool lookup foo"` and `tools=[{"name": "lookup", ...}]` is provided
- **THEN** `LLMResponse.tool_calls` has exactly one entry with `name="lookup"` and `arguments == {"query": "foo"}`, and `LLMResponse.stop_reason == "tool_use"`

#### Scenario: generate() populates structured_output when response_format is JSON
- **WHEN** `response_format={"type": "json_object"}` and the mock's `output_text` is a valid JSON object
- **THEN** `LLMResponse.structured_output` equals the parsed JSON object

#### Scenario: generate() is deterministic across calls
- **WHEN** `generate()` is called twice with the same messages, tools, and response_format
- **THEN** both invocations produce equal `LLMResponse.output_text`, `usage.input_tokens`, `usage.output_tokens`, and `response_id`

### Requirement: MockLLMClient implements complete_stream()

`MockLLMClient.complete_stream()` SHALL yield, in order: zero or more `LLMChunk(type="content_block_delta")` chunks whose `delta={"type": "text_delta", "text": ...}` collectively reconstruct `output_text`; then a final `LLMChunk(type="message_stop")` carrying the same `LLMUsage` as `generate()` would return for the same inputs. The stream MUST NOT raise. Calling `get_last_response()` after iterating the stream MUST return an `LLMResponse` with the same usage and `stop_reason` as the concluded stream.

#### Scenario: complete_stream emits one text delta and one stop
- **WHEN** `async for chunk in mock.complete_stream(messages=[...])`
- **THEN** the caller receives at least one `content_block_delta` chunk whose concatenated `delta.text` equals the non-streaming `output_text`, followed by exactly one `message_stop` chunk carrying populated `usage`

#### Scenario: get_last_response returns the streamed result
- **WHEN** a streaming iteration completes
- **THEN** `mock.get_last_response()` returns an `LLMResponse` whose `usage` equals the stop chunk's `usage`

### Requirement: MockLLMClient stays in coverage scope

`openagents/llm/providers/mock.py` SHALL be covered by unit tests that exercise every branch of `generate()`, `complete_stream()`, and the `_parse_prompt` helper. The module MUST NOT appear on the coverage omit list in `pyproject.toml`. Total repository coverage MUST remain ≥ the project floor (currently 92%).

#### Scenario: mock.py is not in the coverage omit list
- **WHEN** `pyproject.toml` is inspected
- **THEN** `tool.coverage.run.omit` does not include `openagents/llm/providers/mock.py`

#### Scenario: Coverage floor holds
- **WHEN** `uv run coverage run -m pytest && uv run coverage report` is executed
- **THEN** the total coverage meets the project's `fail_under` threshold and `mock.py` line coverage is ≥ 95%

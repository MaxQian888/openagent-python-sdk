# anthropic-provider-features

## Purpose

Anthropic-specific feature parity beyond the baseline `LLMClient` surface, owned by `openagents/llm/providers/anthropic.py`. Covers: preservation of `thinking` / `redacted_thinking` content blocks, flexible `system` content (string or list-of-blocks), end-to-end `cache_control` passthrough on `tools` and message content, and `extra_headers` merge semantics that enable Anthropic beta endpoints (e.g., prompt caching).

## Requirements

### Requirement: Anthropic preserves thinking content blocks

The Anthropic provider SHALL preserve content blocks whose `type` is `"thinking"` or `"redacted_thinking"` in both non-streaming and streaming responses. In `generate()`, such blocks MUST be appended to `LLMResponse.content` in the order returned by the API. Text from thinking blocks MUST NOT be concatenated into `LLMResponse.output_text`. In `complete_stream()`, thinking-block `content_block_start`, `content_block_delta`, and `content_block_stop` events MUST be yielded as `LLMChunk` instances so consumers can distinguish thinking deltas from user-visible text.

#### Scenario: Thinking blocks appear in content but not output_text
- **WHEN** Anthropic returns a response whose `content` contains a `thinking` block followed by a `text` block
- **THEN** `LLMResponse.content` contains both blocks in order, and `LLMResponse.output_text` contains only the text block's text

#### Scenario: Redacted thinking blocks are preserved verbatim
- **WHEN** the response contains a `redacted_thinking` block
- **THEN** the block appears unchanged in `LLMResponse.content` with its `type="redacted_thinking"` and `data` field intact

#### Scenario: Streaming yields thinking deltas as distinct chunks
- **WHEN** the SSE stream emits `content_block_start` with `content_block.type="thinking"` followed by `content_block_delta` events of type `thinking_delta`
- **THEN** the provider yields `LLMChunk` instances whose `content` / `delta` preserves the `thinking` type, so downstream consumers can filter or render them separately from text deltas

### Requirement: Anthropic accepts system content as string or list

The Anthropic provider SHALL accept the `system` role message `content` as either a `str` or a `list[dict]`. When any accumulated `system` content is a list, the provider MUST pass a list (preserving block-level `cache_control` and other metadata) as the value of the `system` field in the outgoing request. When all accumulated system content is strings, the legacy string-concatenation path MUST be preserved. The provider MUST NOT strip unknown keys (including `cache_control`, `citations`, or `metadata`) from system content blocks.

#### Scenario: String system content uses the legacy string path
- **WHEN** `messages` contains one `system` message with `content="you are helpful"`
- **THEN** the request payload sends `"system": "you are helpful"` (a plain string)

#### Scenario: List system content is forwarded unchanged
- **WHEN** `messages` contains one `system` message with `content=[{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]`
- **THEN** the request payload sends `"system": [{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]` with `cache_control` intact

#### Scenario: Mixed system content concatenates into a single list
- **WHEN** `messages` contains two `system` messages, one string and one list
- **THEN** the provider converts the string to a single text block and concatenates into one list in the order the system messages appeared

### Requirement: Anthropic preserves cache_control on tools and message content

When `cache_control` is present on a tool definition or on a content block inside a user or assistant message, the Anthropic provider SHALL pass it through unchanged in the outgoing payload. The provider MUST NOT reshape or strip any key on tool definitions or content blocks except when the response-format adapter injects the structured-output tool.

#### Scenario: Tool-level cache_control passes through
- **WHEN** `tools=[{"name": "read_file", "input_schema": {...}, "cache_control": {"type": "ephemeral"}}]`
- **THEN** the request payload includes the same dict verbatim (with `cache_control` present) in `tools`

#### Scenario: Message content-block cache_control passes through
- **WHEN** a user message's `content` is a list containing a text block with `cache_control`
- **THEN** the request sends that content list unchanged, with `cache_control` intact on the block

### Requirement: Anthropic headers honor extra_headers

The Anthropic provider SHALL merge `LLMOptions.extra_headers` into its request headers, with user-provided keys taking precedence over the provider's defaults (`Content-Type`, `x-api-key`, `anthropic-version`). This MUST apply to both non-streaming and streaming requests.

#### Scenario: anthropic-beta header is forwarded
- **WHEN** `LLMOptions.extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}`
- **THEN** every Anthropic HTTP request includes `anthropic-beta: prompt-caching-2024-07-31`

#### Scenario: User anthropic-version overrides provider default
- **WHEN** `LLMOptions.extra_headers={"anthropic-version": "2024-10-22"}`
- **THEN** requests send `anthropic-version: 2024-10-22` (user value), not the provider's built-in `2023-06-01`

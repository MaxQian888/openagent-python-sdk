# openai-compatible-provider-features

## Purpose

OpenAI-compatible feature parity beyond the baseline `LLMClient` surface, owned by `openagents/llm/providers/openai_compatible.py`. Covers: reasoning-model detection + `max_completion_tokens` substitution, reasoning-token accounting in `LLMUsage.metadata`, passthrough of `seed` / `top_p` / `parallel_tool_calls` / `response_format` (with `strict`), and unified `finish_reason` → `stop_reason` mapping that matches Anthropic semantics. Also covers the Responses API (v2) variant selected via `openai_api_style`, including payload re-shaping (`messages` → `input`+`instructions`; `max_tokens` → `max_output_tokens`; `response_format` → `text.format`) and response parsing (`output[]` with `message` / `reasoning` / `function_call` items).

## Requirements

### Requirement: OpenAI-compatible provider accounts for reasoning tokens

The OpenAI-compatible provider SHALL parse `usage.completion_tokens_details.reasoning_tokens` from non-streaming responses and from the final `usage` object of streaming responses when `stream_options.include_usage=True`. Reasoning tokens MUST be recorded in `LLMUsage.metadata["reasoning_tokens"]`. Reasoning tokens MUST NOT be added to `LLMUsage.output_tokens` (they are already included in the API's `completion_tokens`).

#### Scenario: Non-streaming response records reasoning_tokens in metadata
- **WHEN** a response's `usage` contains `{"completion_tokens": 120, "completion_tokens_details": {"reasoning_tokens": 90}}`
- **THEN** `LLMResponse.usage.output_tokens == 120` and `LLMResponse.usage.metadata["reasoning_tokens"] == 90`

#### Scenario: Streaming final usage records reasoning_tokens
- **WHEN** a streaming response terminates with a `usage` chunk including `completion_tokens_details.reasoning_tokens=45`
- **THEN** the last `LLMChunk.usage.metadata["reasoning_tokens"] == 45`

#### Scenario: Missing reasoning_tokens key is tolerated
- **WHEN** the response `usage` has no `completion_tokens_details` or has it without `reasoning_tokens`
- **THEN** `LLMUsage.metadata` has no `reasoning_tokens` key and no error is raised

### Requirement: OpenAI-compatible uses max_completion_tokens for reasoning models

The OpenAI-compatible provider SHALL detect reasoning-model families using a regex (`^(o\d+(?:-.*)?|gpt-5-thinking.*)$`, case-insensitive) OR an explicit `LLMOptions.reasoning_model=True` opt-in. When a request targets a reasoning model, the provider MUST emit `max_completion_tokens` instead of `max_tokens` in the request body, and MUST NOT include `temperature` (these models reject non-default temperature). When a request targets a non-reasoning model, existing behavior (`max_tokens`, `temperature` passthrough) MUST be preserved unchanged.

#### Scenario: o3-mini triggers max_completion_tokens
- **WHEN** `model="o3-mini"` and `max_tokens=500`
- **THEN** the outgoing payload contains `max_completion_tokens=500` and has no `max_tokens` key

#### Scenario: o1 drops temperature silently
- **WHEN** `model="o1"` and `temperature=0.3`
- **THEN** the outgoing payload has no `temperature` key and a DEBUG-level log records the drop

#### Scenario: Explicit opt-in triggers reasoning mode
- **WHEN** `model="custom-reasoner"` and `LLMOptions.reasoning_model=True` and `max_tokens=1000`
- **THEN** the payload uses `max_completion_tokens=1000` and drops `temperature` if present

#### Scenario: Explicit opt-out overrides regex detection
- **WHEN** `model="o3-custom-fine-tune"` (matches the regex) and `LLMOptions.reasoning_model=False`
- **THEN** the payload uses `max_tokens` and includes `temperature`, as for non-reasoning models

#### Scenario: Non-reasoning models are unchanged
- **WHEN** `model="gpt-4o"` and `max_tokens=200` and `temperature=0.5`
- **THEN** the payload uses `max_tokens=200` and includes `temperature=0.5`

### Requirement: OpenAI-compatible passes through seed, top_p, parallel_tool_calls, and response_format

The OpenAI-compatible provider SHALL forward any of `seed`, `top_p`, `parallel_tool_calls`, and `response_format` that the caller provides, unchanged, into the request payload. For reasoning models these fields MUST still pass through (the OpenAI API accepts them). The caller MUST be able to set `response_format={"type": "json_schema", "json_schema": {"name": "...", "schema": {...}, "strict": true}}` and have `strict` preserved.

#### Scenario: seed and top_p are forwarded
- **WHEN** `LLMOptions.extra` or the per-call kwargs set `seed=42` and `top_p=0.9`
- **THEN** the outgoing payload contains `seed=42` and `top_p=0.9`

#### Scenario: parallel_tool_calls false is preserved
- **WHEN** the caller passes `parallel_tool_calls=False` alongside tools
- **THEN** the outgoing payload includes `parallel_tool_calls: false`

#### Scenario: response_format json_schema strict is preserved
- **WHEN** `response_format={"type": "json_schema", "json_schema": {"name": "X", "schema": {...}, "strict": true}}`
- **THEN** the payload sends the exact same structure unchanged, including `strict: true`

### Requirement: OpenAI-compatible normalizes finish_reason consistently

The OpenAI-compatible provider SHALL map `finish_reason="tool_calls"` to `stop_reason="tool_use"` in both non-streaming and streaming responses, matching the Anthropic provider's mapping. Other finish reasons (`stop`, `length`, `content_filter`) MUST pass through unchanged.

#### Scenario: tool_calls becomes tool_use
- **WHEN** a response has `finish_reason="tool_calls"`
- **THEN** `LLMResponse.stop_reason == "tool_use"` and the streaming `message_stop` chunk carries `stop_reason="tool_use"`

#### Scenario: length passes through unchanged
- **WHEN** a response has `finish_reason="length"`
- **THEN** `LLMResponse.stop_reason == "length"` without renaming

### Requirement: OpenAI-compatible supports the Responses API (v2) via api_style

The OpenAI-compatible provider SHALL accept `api_style: Literal["chat_completions", "responses"] | None` at construction (wired from `LLMOptions.openai_api_style`). When `None`, the provider MUST auto-detect from `api_base` — a suffix of `/responses` selects `"responses"`, otherwise `"chat_completions"`. When `"responses"` is active, the provider MUST:

- Route to the Responses API endpoint (`{api_base}/responses` or `{api_base}/v1/responses`).
- Split the incoming `messages` into `instructions` (all `system`-role content, joined with newlines) and `input` (the remaining messages).
- Emit `max_output_tokens` instead of `max_tokens` (including for reasoning models — the Responses API does not expose `max_completion_tokens`).
- Translate `response_format={"type": "json_schema", "json_schema": {"name": ..., "schema": ..., "strict": ...}}` to `text.format={"type": "json_schema", "name": ..., "schema": ..., "strict": ...}` (flattened, no nested wrapper). `{"type": "json_object"}` / `{"type": "text"}` pass through under `text.format`.
- Parse `response.output[]` for item types `message` (extract `output_text` text blocks into `LLMResponse.output_text`), `reasoning` (preserve in `content` but DO NOT contribute to `output_text`), and `function_call` (emit `LLMToolCall` with `type="tool_use"`).
- Parse `usage.input_tokens` / `usage.output_tokens` (not `prompt_tokens` / `completion_tokens`) and `usage.output_tokens_details.reasoning_tokens` into `LLMUsage.metadata`.

Streaming parity for the Responses API is out of scope for this capability: `complete_stream()` in `"responses"` style MUST fall back to a single non-streaming call and emit `[content_block_delta, message_stop]` chunks so higher-level streaming consumers still see a well-formed event sequence.

#### Scenario: Default api_style is chat_completions
- **WHEN** `OpenAICompatibleClient(api_base="https://api.openai.com/v1", model="gpt-4o")` is constructed without `api_style`
- **THEN** `client.api_style == "chat_completions"` and requests go to `/v1/chat/completions`

#### Scenario: api_base ending in /responses auto-selects responses style
- **WHEN** `api_base="https://api.openai.com/v1/responses"` with no explicit `api_style`
- **THEN** `client.api_style == "responses"` and requests go to `/v1/responses`

#### Scenario: Explicit api_style overrides auto-detection
- **WHEN** `api_base` ends in `/responses` but `api_style="chat_completions"` is passed explicitly
- **THEN** `client.api_style == "chat_completions"` and requests go to `/chat/completions`

#### Scenario: Responses payload splits system into instructions
- **WHEN** `api_style="responses"` and `messages=[{"role": "system", "content": "be helpful"}, {"role": "user", "content": "hi"}]`
- **THEN** the outgoing payload contains `input=[{"role": "user", "content": "hi"}]` and `instructions="be helpful"`, with no `messages` key

#### Scenario: Responses payload uses max_output_tokens
- **WHEN** `api_style="responses"` and the caller passes `max_tokens=500`
- **THEN** the outgoing payload contains `max_output_tokens=500` and no `max_tokens` / `max_completion_tokens`

#### Scenario: response_format translates to flattened text.format
- **WHEN** `api_style="responses"` and `response_format={"type": "json_schema", "json_schema": {"name": "X", "schema": {...}, "strict": true}}`
- **THEN** the outgoing payload contains `text={"format": {"type": "json_schema", "name": "X", "schema": {...}, "strict": true}}` with the `json_schema` wrapper removed

#### Scenario: Responses output parsing extracts message text
- **WHEN** the response body has `output=[{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hello."}]}]`
- **THEN** `LLMResponse.output_text == "Hello."`

#### Scenario: Responses output parsing preserves reasoning blocks outside output_text
- **WHEN** the response body includes a `reasoning` item followed by a `message` item with text "Answer"
- **THEN** `LLMResponse.output_text == "Answer"` and `LLMResponse.content` contains the reasoning block with `type="reasoning"`

#### Scenario: Responses output parsing emits tool_use for function_call items
- **WHEN** the response body contains `{"type": "function_call", "call_id": "c1", "name": "search", "arguments": "{\"q\":\"x\"}"}`
- **THEN** `LLMResponse.tool_calls` contains a single `LLMToolCall(name="search", arguments={"q":"x"}, type="tool_use")` and `LLMResponse.stop_reason == "tool_use"`

#### Scenario: Responses usage parsing handles input_tokens / output_tokens naming
- **WHEN** the response has `usage={"input_tokens": 12, "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 2}}`
- **THEN** `LLMResponse.usage.input_tokens == 12`, `LLMResponse.usage.output_tokens == 5`, and `LLMResponse.usage.metadata["reasoning_tokens"] == 2`

#### Scenario: Responses streaming falls back to non-streaming shape
- **WHEN** `api_style="responses"` and the caller calls `complete_stream()`
- **THEN** the stream yields exactly `[content_block_delta, message_stop]` with the full `output_text` as the delta's text and the `stop_reason` on the `message_stop` chunk

## ADDED Requirements

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

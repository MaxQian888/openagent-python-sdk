# OpenAgents SDK

Config-as-code Agent SDK with plugin-driven `memory`, `pattern`, and `tool`.

## What It Provides

- `agent.json` as the single source of agent configuration.
- Pluggable `memory`, `pattern`, and `tool` via:
  - `type` for builtin plugins
  - `impl` for custom import path plugins
- LLM-aware pattern execution via `llm` config (`mock` and `openai_compatible`).
- Runtime as the only execution entrypoint.
- Session isolation:
  - same `session_id` runs serially
  - different `session_id` runs concurrently
- Memory strategy ownership:
  - inject and writeback strategy are implemented by memory plugins
  - runtime only triggers lifecycle timing

## Install And Dev

- Sync deps: `uv sync --extra dev`
- Run tests: `uv run --extra dev pytest -q`

## Quickstart

Use the provided config file:

- `examples/quickstart/agent.json`
- Runnable script: `examples/quickstart/run_demo.py`
- Command: `uv run python examples/quickstart/run_demo.py`

Run an agent:

```python
import asyncio

from openagents.runtime import Runtime


async def main() -> None:
    runtime = Runtime.from_config("examples/quickstart/agent.json")

    out1 = await runtime.run(
        agent_id="assistant",
        session_id="demo",
        input_text="hello",
    )
    print(out1)

    out2 = await runtime.run(
        agent_id="assistant",
        session_id="demo",
        input_text="/tool search memory injection",
    )
    print(out2)


asyncio.run(main())
```

## Config Rules

- Each plugin ref must set exactly one of `type` or `impl`.
- For each agent, `tools[].id` must be unique.
- `runtime.max_steps` and `runtime.step_timeout_ms` must be positive integers.
- `memory.on_error` supports:
  - `continue` (default): do not block main flow
  - `fail`: stop run on memory failure
- Optional `llm`:
  - `provider`: `mock` or `openai_compatible`
  - `openai_compatible` requires `api_base`
  - `timeout_ms` must be positive

## LLM Config Example

```json
{
  "llm": {
    "provider": "openai_compatible",
    "model": "gpt-4o-mini",
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.2,
    "max_tokens": 512,
    "timeout_ms": 30000
  }
}
```

Real-call example in repo:

- `examples/openai_compatible/agent.json`
- `examples/openai_compatible/run_demo.py`
- `examples/openai_compatible/.env.example`

`.env` fields:

- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`

For local/offline development, use:

```json
{
  "llm": {
    "provider": "mock",
    "model": "mock-react-v1"
  }
}
```

## Builtin Plugin Names

- Memory:
  - `buffer`
  - `window_buffer`
- Pattern:
  - `react`
- Tool:
  - `builtin_search`

## Custom Plugin Example

In config:

```json
{
  "memory": { "impl": "my_plugins.memory.MyMemory" },
  "pattern": { "impl": "my_plugins.pattern.MyPattern" },
  "tools": [
    { "id": "weather", "impl": "my_plugins.tools.WeatherTool" }
  ]
}
```

Runnable custom example:

- Config: `examples/custom_impl/agent.json`
- Plugins: `examples/custom_impl/plugins.py`
- Script: `examples/custom_impl/run_demo.py`
- Command: `uv run python examples/custom_impl/run_demo.py`

Minimal contract:

- Memory plugin:
  - expose `capabilities` (e.g. `memory.inject`, `memory.writeback`)
  - implement `inject(context)` and optional `writeback(context)` behavior
- Pattern plugin:
  - expose `pattern.react`
  - implement `react(context)` and return action dict:
    - `{"type":"final","content":"..."}`
    - `{"type":"continue"}`
    - `{"type":"tool_call","tool":"<tool_id>","params":{...}}`
- Tool plugin:
  - expose `tool.invoke`
  - implement `invoke(params, context)`

## Test Scope

Current suite covers:

- config parsing and strict validation
- plugin loading and capability checks
- runtime orchestration (inject/react/writeback)
- memory error policy (`continue` and `fail`)
- session pressure tests
- output constraint tests
- integration tests from file-based config

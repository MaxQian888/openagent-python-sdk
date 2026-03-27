# OpenAgents SDK

<p align="center">
  <img src="https://img.shields.io/pypi/v/openagents-sdk" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/openagents-sdk" alt="Python">
</p>

<p align="center">
  <strong>Agent is Loop. 配置驱动的 Agent 开发框架</strong>
</p>

---

## 什么是 Agent？

Agent 本质上是一个 Loop：

```
Input -> LLM (思考) -> Tool (行动) -> Output -> 循环
```

OpenAgents SDK 把这个 Loop 拆成可配置、可替换、可观测的组件：Memory、Pattern、Tools、Runtime、Session、Events。

## 核心特性

- 声明式配置：一份 JSON 定义 Agent 行为
- 插件架构：Memory、Pattern、Tool、Runtime、Session、Events 都可替换
- 装饰器注册：`@tool`、`@memory`、`@pattern`、`@runtime`、`@session`
- 多 LLM 支持：`mock`、`openai_compatible`、`anthropic`
- MCP 支持：内置 `mcp` tool
- 可观测：Event Bus + runtime lifecycle 事件

## 快速开始

```bash
uv add openagents-sdk
```

运行仓库内示例：

```bash
uv run python examples/quickstart/run_demo.py
```

## 配置结构

顶层配置：

```json
{
  "version": "1.0",
  "runtime": {"type": "default"},
  "session": {"type": "in_memory"},
  "events": {"type": "async"},
  "agents": [
    {
      "id": "assistant",
      "name": "demo-agent",
      "memory": {"type": "window_buffer", "on_error": "continue"},
      "pattern": {"type": "react"},
      "llm": {"provider": "mock"},
      "tools": [{"id": "search", "type": "builtin_search"}],
      "runtime": {
        "max_steps": 16,
        "step_timeout_ms": 30000,
        "session_queue_size": 1000,
        "event_queue_size": 2000
      }
    }
  ]
}
```

说明：

- 顶层 `runtime` / `session` / `events` 选择全局插件实现
- agent 内的 `runtime` 是运行参数，不是 runtime 插件替换入口
- 插件引用至少要提供一个 `type` 或 `impl`；两者同时提供时 `impl` 优先
- `llm` 是可选的；未配置时，Pattern 需要自己处理无 LLM 场景

## LLM 配置

本地或测试场景：

```json
{
  "llm": {
    "provider": "mock",
    "model": "mock-react-v1"
  }
}
```

OpenAI 兼容接口：

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

Anthropic 兼容接口：

```json
{
  "llm": {
    "provider": "anthropic",
    "model": "claude-3-haiku-20240307",
    "api_key_env": "ANTHROPIC_API_KEY",
    "timeout_ms": 30000
  }
}
```

## 自定义插件

使用 `impl`：

```json
{
  "runtime": {"impl": "my_plugins.runtime.CustomRuntime"},
  "agents": [
    {
      "id": "assistant",
      "name": "assistant",
      "memory": {"impl": "my_plugins.memory.MyMemory"},
      "pattern": {"impl": "my_plugins.pattern.MyPattern"},
      "tools": [
        {"id": "weather", "impl": "my_plugins.tools.WeatherTool"}
      ]
    }
  ]
}
```

使用装饰器注册后，也可以通过 `type` 引用：

```python
from openagents import runtime

@runtime(name="custom")
class CustomRuntime:
    ...
```

```json
{
  "runtime": {"type": "custom"}
}
```

## 示例

- Quickstart: `examples/quickstart/agent.json`
  - `uv run python examples/quickstart/run_demo.py`
- Custom plugins (`impl`): `examples/custom_impl/agent.json`
  - `uv run python examples/custom_impl/run_demo.py`
- OpenAI-compatible real call: `examples/openai_compatible/agent.json`
  - `uv run python examples/openai_compatible/run_demo.py`
- Research agent: `examples/research_agent/agent.json`

## 文档

- [开发指南](docs/developer-guide.md)
- [配置参考](docs/configuration.md)
- [插件开发](docs/plugin-development.md)
- [API 参考](docs/api-reference.md)

## 开发

安装依赖：

```bash
uv sync --extra dev
```

运行测试：

```bash
uv run --extra dev pytest -q
```

## 当前测试覆盖

- config parsing / validation
- plugin loading / capability checks
- runtime orchestration
- memory error policy
- reload / hot reload handler behavior
- file-based integration examples

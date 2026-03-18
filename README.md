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

Agent 本质上是一个 **Loop**：

```
Input → LLM (思考) → Tool (行动) → Output → 循环
```

每一次循环，LLM 决定是继续行动还是返回结果。这个看似简单的模式，构成了 ChatGPT、Claude、Cursor 等一切 AI 应用的基石。

**OpenAgents SDK** 让这个 Loop 变得可配置、可扩展、可观测。

---

## 为什么选择 OpenAgents SDK？

### 1. 插件化的 Agent Loop

传统 Agent 开发：写代码 → 改代码 → 调试
OpenAgents SDK：写配置 → 加载 → 运行

```json
{
  "pattern": "react",      // 推理模式
  "memory": "mem0",      // 记忆策略
  "tools": ["search", "http"]  // 工具集
}
```

每一个组件都是**可插拔**的：
- 想换推理模式？改 `pattern` 字段
- 想换记忆方式？改 `memory` 字段
- 想加新工具？加到 `tools` 列表

### 2. 生产级运行时

Runtime 是 Agent 的"操作系统"，我们提供完整生产特性：

| 特性 | 说明 |
|------|------|
| **Session 管理** | 并发控制、状态持久化、串行保障 |
| **Event 总线** | 可观测性、调试钩子、审计日志 |
| **Graceful Shutdown** | 优雅停机、确保任务完成 |
| **错误恢复** | 重试、降级、异常捕获 |

### 3. 灵活的扩展性

```
           ┌─────────────┐
           │   Runtime   │  ← 运行时
           └──────┬──────┘
                  │
    ┌────────────┼────────────┐
    │            │            │
┌───┴───┐  ┌────┴────┐  ┌──┴────┐
│Memory │  │ Pattern │  │ Tools │
└───────┘  └─────────┘  └───────┘
```

- **Memory** - 记忆层：窗口缓冲、向量检索、持久化存储
- **Pattern** - 推理层：ReAct、Plan-Execute、Reflexion...
- **Tools** - 能力层：14+ 内置工具、MCP 协议支持

全部可自定义，全部可替换。

---

## 核心特性

- **声明式配置** - 一份 JSON 定义 Agent 行为
- **插件架构** - Tool、Pattern、Memory、Runtime 均可替换
- **装饰器开发** - `@tool`、`@memory`、`@pattern` 快速定义插件
- **多 LLM 支持** - OpenAI、Anthropic 兼容接口
- **MCP 协议** - 无缝对接 Model Context Protocol
- **可观测** - 完整 Event Bus 支持调试和审计

---

## 快速开始

```bash
uv add openagents-sdk
```

```bash
# 运行示例
uv run examples/quickstart/run_demo.py
```

详细文档：[开发指南](docs/developer-guide.md)

---

## 架构概览

```
┌─────────────────────────────────────────────┐
│              agent.json                      │
│  (声明式配置：Memory / Pattern / Tools)     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│                Runtime                       │
│  ┌──────────────┬──────────────┐          │
│  │   Session    │    Event     │          │
│  │   Manager    │      Bus      │          │
│  └──────────────┴──────────────┘          │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│              Agent Loop                      │
│                                          │
│   ┌─────┐    ┌─────┐    ┌─────┐         │
│   │ LLM │ ←→ │Tool │ ←→ │Memory│        │
│   └─────┘    └─────┘    └─────┘         │
│        ↑____________________↓              │
│              (循环)                         │
└─────────────────────────────────────────────┘
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [开发指南](docs/developer-guide.md) | 完整开发指南 |
| [API 参考](docs/api-reference.md) | API 文档 |
| [插件开发](docs/plugin-development.md) | 自定义插件 |
| [配置参考](docs/configuration.md) | 配置选项详解 |

---

## 开发

```bash
# 安装开发依赖
uv sync --extra dev

# 运行测试
uv run --extra dev pytest -q
```
uv sync --extra dev

# 运行测试
uv run --extra dev pytest -q
```

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

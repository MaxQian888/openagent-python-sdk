# OpenAgents SDK 开发指南

## 概述

OpenAgents SDK 是一个 **Config-as-Code** 的 Agent 开发框架。通过 `agent.json` 声明式配置 Agent，支持灵活的插件系统。

---

## 快速开始

### 1. 安装

```bash
pip install openagents
```

### 2. 创建 Agent 配置

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "assistant",
      "name": "My Agent",
      "memory": {"type": "window_buffer", "config": {"window_size": 20}},
      "pattern": {"type": "react"},
      "llm": {"provider": "mock"},
      "tools": [
        {"id": "search", "type": "builtin_search"}
      ]
    }
  ]
}
```

### 3. 运行 Agent

```python
import asyncio
from openagents import Runtime

async def main():
    runtime = Runtime.from_config("agent.json")
    result = await runtime.run(
        agent_id="assistant",
        session_id="demo",
        input_text="hello"
    )
    print(result)

asyncio.run(main())
```

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     agent.json                              │
├─────────────────────────────────────────────────────────────┤
│  plugins:                                                  │
│  ├── memory   → 记忆存储 (buffer, window_buffer)           │
│  ├── pattern  → 推理模式 (react, plan_execute, reflexion) │
│  ├── tool     → 工具集 (14+ 内置工具)                      │
│  ├── runtime  → 运行时 (可自定义)                          │
│  ├── session  → 会话管理 (可分布式)                        │
│  └── events  → 事件总线 (可扩展)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 内置插件

### Memory

| 类型 | 描述 | 配置 |
|------|------|------|
| `buffer` | 简单缓冲记忆 | `max_items` |
| `window_buffer` | 滑动窗口记忆 | `window_size` |

### Pattern

| 类型 | 描述 | 配置 |
|------|------|------|
| `react` | ReAct 推理循环 | `max_steps`, `step_timeout_ms` |
| `plan_execute` | 先计划后执行 | `max_steps`, `step_timeout_ms` |
| `reflexion` | 带反思的推理 | `max_steps`, `max_retries` |

### Tool

**文件操作**
- `read_file`, `write_file`, `list_files`, `delete_file`

**文本处理**
- `grep_files`, `ripgrep`, `json_parse`, `text_transform`

**HTTP**
- `http_request`

**系统**
- `execute_command`, `get_env`, `set_env`

**日期时间**
- `current_time`, `date_parse`, `date_diff`

**随机数**
- `random_int`, `random_choice`, `random_string`, `uuid`

**网络**
- `url_parse`, `url_build`, `query_param`, `host_lookup`

**数学**
- `calc`, `percentage`, `min_max`

---

## 自定义插件

### 1. 自定义 Tool

```python
from openagents.interfaces.tool import ToolPlugin
from openagents.interfaces.capabilities import TOOL_INVOKE

class MyTool(ToolPlugin):
    def __init__(self, config=None):
        super().__init__(
            config=config or {},
            capabilities={TOOL_INVOKE}
        )

    async def invoke(self, params, context):
        # your logic
        return {"result": "..."}
```

在配置中使用：

```json
{
  "tools": [
    {
      "id": "my_tool",
      "impl": "mypackage.mymodule.MyTool"
    }
  ]
}
```

### 2. 自定义 Pattern

```python
from openagents.interfaces.pattern import PatternPlugin
from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT

class MyPattern(PatternPlugin):
    def __init__(self, config=None):
        super().__init__(
            config=config or {},
            capabilities={PATTERN_EXECUTE, PATTERN_REACT}
        )

    async def execute(self, context):
        # Main execution loop
        action = await self.react(context)
        return action.get("content")

    async def react(self, context):
        # Single step decision
        return {"type": "final", "content": "hello"}
```

### 3. 自定义 Memory

```python
from openagents.interfaces.memory import MemoryPlugin
from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK

class MyMemory(MemoryPlugin):
    def __init__(self, config=None):
        super().__init__(
            config=config or {},
            capabilities={MEMORY_INJECT, MEMORY_WRITEBACK}
        )

    async def inject(self, context):
        # Inject memory into context
        context.memory_view["history"] = []

    async def writeback(self, context):
        # Save memory from context
        pass
```

### 4. 自定义 Runtime

```python
from openagents.interfaces.runtime import RuntimePlugin
from openagents.interfaces.capabilities import RUNTIME_RUN

class MyRuntime(RuntimePlugin):
    def __init__(self, config=None):
        super().__init__(
            config=config or {},
            capabilities={RUNTIME_RUN}
        )

    async def run(self, *, agent_id, session_id, input_text, app_config, agents_by_id):
        # Custom runtime logic
        pass
```

---

## 高级特性

### Fallback 机制

在 Pattern 中处理 Tool 调用失败：

```python
class MyPattern(PatternPlugin):
    async def execute(self, context):
        for step in range(max_steps):
            action = await self.react(context)

            if action["type"] == "tool_call":
                try:
                    await context.call_tool(action["tool"], action["params"])
                except Exception as e:
                    # Fallback logic
                    return {"type": "final", "content": f"Tool failed: {e}"}
```

### 事件监听

```python
async def on_tool_succeeded(event):
    print(f"Tool succeeded: {event.payload}")

runtime.event_bus.subscribe("tool.succeeded", on_tool_succeeded)
```

### 会话管理

```python
# 获取会话状态
state = await runtime.session_manager.get_state("session_id")

# 列出所有会话
sessions = await runtime.session_manager.list_sessions()
```

---

## 配置参考

### Agent 配置

```json
{
  "id": "agent_id",
  "name": "Agent Name",
  "memory": {
    "type": "window_buffer",
    "config": {"window_size": 20}
  },
  "pattern": {
    "type": "react",
    "config": {"max_steps": 16}
  },
  "llm": {
    "provider": "openai_compatible",
    "model": "gpt-4",
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY"
  },
  "tools": [
    {"id": "search", "type": "builtin_search"}
  ]
}
```

### 全局配置

```json
{
  "version": "1.0",
  "runtime": {"type": "default"},
  "session": {"type": "in_memory"},
  "events": {"type": "async"},
  "agents": [...]
}
```

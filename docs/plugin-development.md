# 插件开发指南

本文档详细介绍如何开发自定义插件。

## 概述

OpenAgents SDK 采用**插件化架构**，支持自定义以下组件：

| 组件 | 说明 | 装饰器 |
|------|------|--------|
| Tool | 工具扩展 | `@tool` |
| Memory | 记忆系统 | `@memory` |
| Pattern | 推理模式 | `@pattern` |
| Runtime | 运行时 | `@runtime` |
| Session | 会话管理 | `@session` |

## 开发方式

### 方式一：装饰器（推荐）

使用 `@tool`, `@memory`, `@pattern` 装饰器定义插件。

### 方式二：Protocol

直接实现 Protocol 接口，无需继承。

### 方式三：继承基类

继承 `ToolPlugin`, `MemoryPlugin` 等（保留兼容）。

---

## 开发 Tool

### 基本结构

```python
from openagents import tool

@tool(name="my_tool", description="工具描述")
class MyTool:
    def __init__(self, config=None):
        # 必须：定义 config
        self.config = config or {}
        # 必须：定义 capabilities
        self.capabilities = {"tool.invoke"}

    async def invoke(self, params, context):
        """执行工具逻辑"""
        return {"result": "ok"}
```

### 完整示例

```python
from openagents import tool
from openagents.interfaces.tool import RetryableToolError, PermanentToolError

@tool(name="weather", description="查询天气")
class WeatherTool:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"tool.invoke"}
        self.api_key = config.get("api_key") if config else None
        self._cache = {}

    async def invoke(self, params, context):
        city = params.get("city")
        if not city:
            raise PermanentToolError("city is required", tool_name="weather")

        # 检查缓存
        if city in self._cache:
            return self._cache[city]

        # 调用 API（这里用模拟数据）
        result = {
            "city": city,
            "temperature": 25,
            "condition": "sunny"
        }
        self._cache[city] = result
        return result

    def schema(self):
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }

    async def fallback(self, error, params, context):
        """失败时返回降级数据"""
        return {
            "city": params.get("city", "unknown"),
            "temperature": 20,
            "condition": "unknown",
            "from_cache": True,
            "error": str(error)
        }
```

### 在配置中使用

```json
{
  "tools": [
    {
      "id": "weather",
      "impl": "mypackage.weather.WeatherTool",
      "config": {"api_key": "xxx"}
    }
  ]
}
```

---

## 开发 Memory

### 接口说明

Memory 插件有三个核心方法：

| 方法 | 调用时机 | 说明 |
|------|----------|------|
| `inject` | Pattern 执行前 | 注入记忆到 context |
| `writeback` | Pattern 执行后 | 保存当前交互 |
| `retrieve` | 任何时候 | 检索相关记忆 |

### 基本结构

```python
from openagents import memory

@memory
class MyMemory:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {
            "memory.inject",
            "memory.writeback",
            "memory.retrieve"
        }
```

### 完整示例：持久化记忆

```python
import json
from pathlib import Path
from openagents import memory

@memory
class PersistentMemory:
    """持久化记忆，支持关键词搜索"""

    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {
            "memory.inject",
            "memory.writeback",
            "memory.retrieve"
        }
        self.storage_dir = config.get("storage_dir", ".memory") if config else ".memory"
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id):
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return Path(self.storage_dir) / f"{safe_id}.json"

    def _load(self, session_id):
        path = self._get_path(session_id)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return []

    def _save(self, session_id, data):
        path = self._get_path(session_id)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def inject(self, context):
        """注入历史到 context"""
        history = self._load(context.session_id)
        context.memory_view["history"] = history[-10:]  # 最近 10 条

    async def writeback(self, context):
        """保存当前交互"""
        history = self._load(context.session_id)
        history.append({
            "input": context.input_text,
            "output": context.state.get("_runtime_last_output")
        })
        self._save(context.session_id, history)

    async def retrieve(self, query, context):
        """关键词搜索"""
        history = self._load(context.session_id)
        query = query.lower()
        results = []
        for item in history:
            if query in item.get("input", "").lower():
                results.append(item)
        return results[:5]
```

---

## 开发 Pattern

### 接口说明

Pattern 插件有执行和单步决策两个核心方法：

| 方法 | 说明 |
|------|------|
| `execute` | 主执行循环 |
| `react` | 单步决策 |

Pattern 可以访问 `self.context` 获取运行时数据，并使用内置方法：

| 方法 | 说明 |
|------|------|
| `self.emit()` | 发送事件 |
| `self.call_tool()` | 调用工具 |
| `self.call_llm()` | 调用 LLM |

### 基本结构

```python
from openagents import pattern

@pattern
class MyPattern:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"pattern.execute", "pattern.react"}
```

### 完整示例：带 Fallback 的问答

```python
from openagents import pattern
import json

@pattern
class QAPattern:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"pattern.execute", "pattern.react"}
        self.max_steps = config.get("max_steps", 3) if config else 3
        self.fallback_enabled = config.get("fallback_enabled", True)

    async def execute(self):
        """主执行流程"""
        try:
            # 构建提示词
            messages = self._build_prompt()
            # 调用 LLM
            response = await self.call_llm(messages=messages)
            # 解析响应
            return self._parse_response(response)
        except Exception as e:
            if self.fallback_enabled:
                return await self._fallback(str(e))
            raise

    async def react(self):
        """单步决策（ReAct 模式用）"""
        ctx = self.context

        # 调用 LLM
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": ctx.input_text}
        ]
        response = await self.call_llm(messages=messages)

        try:
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            return {"type": "final", "content": response}

    def _build_prompt(self):
        ctx = self.context
        history = ctx.memory_view.get("history", [])

        user_content = ctx.input_text
        if history:
            history_text = "\n".join(
                f"User: {h.get('input')}\nAssistant: {h.get('output', '')}"
                for h in history
            )
            user_content = f"Conversation history:\n{history_text}\n\nCurrent: {ctx.input_text}"

        return [
            {"role": "user", "content": user_content}
        ]

    def _parse_response(self, response):
        try:
            data = json.loads(response)
            return data.get("content", response)
        except json.JSONDecodeError:
            return response

    async def _fallback(self, error):
        """降级到记忆搜索"""
        history = self.context.memory_view.get("history", [])
        if history:
            return f"I encountered an error: {error}. Based on our conversation: {history[-1]}"
        return f"I encountered an error and have no history to fall back on: {error}"
```

---

## 测试插件

```python
import pytest
from openagents import Runtime, load_config_dict

@pytest.mark.asyncio
async def test_my_tool():
    config = load_config_dict({
        "version": "1.0",
        "agents": [{
            "id": "test",
            "memory": {"type": "buffer"},
            "pattern": {"type": "react"},
            "llm": {"provider": "mock"},
            "tools": [{
                "id": "my_tool",
                "impl": "mypackage.MyTool",
                "config": {}
            }]
        }]
    })
    runtime = Runtime(config)
    result = await runtime.run("test", "s1", "test")
    assert result
```

---

## 注册表访问

```python
from openagents import (
    get_tool, get_memory, get_pattern,
    list_tools, list_memories, list_patterns
)

# 获取已注册插件
MyTool = get_tool("my_tool")
MyMemory = get_memory("my_memory")
MyPattern = get_pattern("my_pattern")

# 列出所有插件
print(list_tools())    # ["weather", "search", ...]
print(list_memories()) # ["buffer", "window_buffer", ...]
```

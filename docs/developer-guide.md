# OpenAgents SDK 开发指南

## 概述

OpenAgents SDK 是一个 **Config-as-Code** 的 Agent 开发框架。通过 JSON 配置文件声明式定义 Agent，无需编写大量代码即可创建功能强大的 AI Agent。

### 核心理念

- **声明式配置**：通过 `agent.json` 定义 Agent 行为，配置即代码
- **插件化架构**：Tool、Pattern、Memory、Runtime 均可插拔替换
- **异步优先**：核心 API 采用异步设计，同时提供同步封装
- **开箱即用**：内置 14+ 工具、3 种推理模式、多维度记忆系统

### 适用场景

- 构建问答 Agent
- 创建自动化工作流
- 开发多工具协同的 AI 助手
- 实现具有长期记忆的对话系统
- 连接外部 MCP 服务器扩展能力

---

## 快速开始

### 1. 安装

```bash
# 基础安装
pip install openagents

# 安装 MCP 支持（可选）
pip install openagents[mcp]
```

### 2. 创建 Agent 配置

创建 `agent.json` 文件：

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "assistant",
      "name": "My Agent",
      "memory": {
        "type": "window_buffer",
        "config": {"window_size": 20}
      },
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

**异步用法（推荐）**

```python
import asyncio
from openagents import Runtime

async def main():
    # 从配置文件加载 Runtime
    runtime = Runtime.from_config("agent.json")

    # 运行 Agent
    result = await runtime.run(
        agent_id="assistant",    # Agent ID，对应配置中的 agents[].id
        session_id="demo",       # 会话 ID，用于区分不同会话
        input_text="hello"       # 输入文本
    )
    print(result)

asyncio.run(main())
```

**同步用法（简单脚本）**

```python
from openagents import run_agent

result = run_agent(
    "agent.json",
    agent_id="assistant",
    session_id="demo",
    input_text="hello"
)
print(result)
```

---

## 架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        agent.json                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  agents:                                                        │
│  ├── id: "assistant"                                            │
│  ├── memory ──────────► 记忆存储层                              │
│  │      ├── buffer          (简单缓冲)                         │
│  │      ├── window_buffer   (滑动窗口，保留最近 N 条)          │
│  │      └── mem0            (向量语义记忆)                     │
│  │                                                                  │
│  ├── pattern ─────────► 推理模式层                              │
│  │      ├── react           (ReAct 循环)                       │
│  │      ├── plan_execute    (先计划后执行)                     │
│  │      └── reflexion       (带反思的推理)                     │
│  │                                                                  │
│  ├── tool ───────────► 工具层 (14+ 内置工具)                   │
│  │      ├── file_ops        (文件操作)                         │
│  │      ├── http_ops        (HTTP 请求)                        │
│  │      ├── system_ops      (系统命令)                         │
│  │      ├── mcp             (MCP 客户端)                       │
│  │      └── ...                                                │
│  │                                                                  │
│  ├── skill ───────────► 行为层 (可选)                           │
│  │      ├── researcher      (研究专家)                         │
│  │      ├── coder           (编程专家)                         │
│  │      └── ...                                                │
│  │                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  runtime:  Runtime   ──► 运行时 (默认/自定义)                  │
│  session:  Session   ──► 会话管理 (内存/分布式)               │
│  events:   EventBus  ──► 事件总线 (异步/同步)                  │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户输入
    │
    ▼
Runtime.run()
    │
    ├─► Memory.inject()    ──► 注入历史记忆到 context
    │
    ├─► Pattern.execute()  ──► 推理循环
    │       │
    │       ├─► LLM 调用 ──► 决定 action
    │       │
    │       └─► Tool.invoke()  ──► 执行工具
    │
    ├─► Memory.writeback() ──► 保存记忆
    │
    ▼
返回结果
```

### 核心组件

| 组件 | 说明 | 可自定义 |
|------|------|----------|
| `Runtime` | 入口类，负责加载配置和调度 | ✅ |
| `Memory` | 记忆存储，影响上下文 | ✅ |
| `Pattern` | 推理模式，决定 Agent 行为逻辑 | ✅ |
| `Tool` | 工具集，扩展 Agent 能力 | ✅ |
| `Skill` | 预定义行为，提供系统提示词 | ✅ |
| `Session` | 会话管理，保存状态 | ✅ |
| `EventBus` | 事件系统，监控运行状态 | ✅ |

---

## 配置详解

### Agent 配置

每个 Agent 需要配置以下字段：

```json
{
  "id": "assistant",
  "name": "My Agent",
  "enabled": true,
  "memory": {
    "type": "window_buffer",
    "config": {"window_size": 20}
  },
  "pattern": {
    "type": "react",
    "config": {"max_steps": 16, "step_timeout_ms": 30000}
  },
  "llm": {
    "provider": "openai_compatible",
    "model": "gpt-4",
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY"
  },
  "tools": [
    {"id": "search", "type": "builtin_search", "enabled": true}
  ],
  "skill": {
    "type": "assistant",
    "config": {"personality": "helpful"}
  }
}
```

**字段说明**

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `id` | ✅ | string | Agent 唯一标识 |
| `name` | - | string | Agent 显示名称 |
| `enabled` | - | boolean | 是否启用，默认 true |
| `memory` | ✅ | object | 记忆配置 |
| `pattern` | ✅ | object | 推理模式配置 |
| `llm` | ✅ | object | LLM 配置 |
| `tools` | - | array | 工具列表 |
| `skill` | - | object | Skill 配置 |

### LLM Provider 配置

**Mock (测试用)**

```json
{
  "llm": {"provider": "mock"}
}
```

**OpenAI**

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

**OpenAI Compatible (兼容接口)**

```json
{
  "llm": {
    "provider": "openai_compatible",
    "model": "gpt-4",
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

支持 `api_base` 指向任何兼容 OpenAI API 的服务，如：
- Azure OpenAI
- Ollama
- LocalAI
- 通义千问
- 智谱清言

### 全局配置

```json
{
  "version": "1.0",
  "runtime": {
    "type": "default"
  },
  "session": {
    "type": "in_memory"
  },
  "events": {
    "type": "async"
  },
  "agents": [...]
}
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `runtime.type` | "default" | 运行时实现 |
| `session.type` | "in_memory" | 会话存储 |
| `events.type` | "async" | 事件总线 |

---

## 内置插件详解

### Memory 插件

| 类型 | 描述 | 配置参数 |
|------|------|----------|
| `buffer` | 简单缓冲，保存所有历史 | `max_items`: 最大保存条数 |
| `window_buffer` | 滑动窗口，只保留最近 N 条 | `window_size`: 窗口大小 |
| `mem0` | 向量语义记忆，支持语义搜索 | `collection_name`: 集合名<br>`search_limit`: 召回数量 |

**buffer 用法**

```json
{
  "memory": {
    "type": "buffer",
    "config": {"max_items": 100}
  }
}
```

**window_buffer 用法**

```json
{
  "memory": {
    "type": "window_buffer",
    "config": {"window_size": 20}
  }
}
```

**mem0 用法** (复用 agent LLM，无需额外配置)

```json
{
  "memory": {
    "type": "mem0",
    "config": {
      "collection_name": "my_agent_memory",
      "search_limit": 5
    }
  }
}
```

### Pattern 插件

| 类型 | 描述 | 配置参数 |
|------|------|----------|
| `react` | ReAct (Reason + Act) 推理循环 | `max_steps`: 最大步数<br>`step_timeout_ms`: 单步超时 |
| `plan_execute` | 先计划后执行 | `max_steps`: 最大步数<br>`step_timeout_ms`: 单步超时 |
| `reflexion` | 带自我反思的推理 | `max_steps`: 最大步数<br>`max_retries`: 最大重试次数 |

**ReAct Pattern** (默认)

```json
{
  "pattern": {
    "type": "react",
    "config": {
      "max_steps": 16,
      "step_timeout_ms": 30000
    }
  }
}
```

ReAct 模式工作流程：
1. LLM 分析输入，决定是调用工具还是返回最终答案
2. 如果调用工具，执行工具后继续步骤 1
3. 如果返回答案，流程结束

**Plan-Execute Pattern**

```json
{
  "pattern": {
    "type": "plan_execute",
    "config": {
      "max_steps": 16,
      "step_timeout_ms": 30000
    }
  }
}
```

Plan-Execute 模式工作流程：
1. **Plan 阶段**: LLM 先生成执行计划
2. **Execute 阶段**: 按计划逐步执行
3. 每步可调用工具，最终返回结果

**Reflexion Pattern**

```json
{
  "pattern": {
    "type": "reflexion",
    "config": {
      "max_steps": 16,
      "max_retries": 2
    }
  }
}
```

Reflexion 模式工作流程：
1. 执行每步后，LLM 会反思结果
2. 如果失败，自动调整参数重试
3. 适合需要自我纠错的复杂任务

### Tool 插件

#### 文件操作

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `read_file` | 读取文件 | `path`: 文件路径 |
| `write_file` | 写入文件 | `path`: 文件路径<br>`content`: 内容<br>`mode`: "w" 或 "a" |
| `list_files` | 列出文件 | `path`: 目录<br>`pattern`: 通配符<br>`recursive`: 是否递归 |
| `delete_file` | 删除文件 | `path`: 路径 |

**read_file 示例**

```python
# 调用方式
result = await context.call_tool("read_file", {"path": "/path/to/file.txt"})
# 返回: {"path": "...", "content": "...", "size": 123}
```

**write_file 示例**

```python
result = await context.call_tool("write_file", {
    "path": "/path/to/file.txt",
    "content": "Hello World",
    "mode": "w"  # "w" 覆盖, "a" 追加
})
# 返回: {"path": "...", "bytes_written": 11, "mode": "w"}
```

#### 文本处理

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `grep_files` | 多文件搜索 | `pattern`: 正则<br>`paths`: 目录列表 |
| `ripgrep` | 快速文本搜索 | `pattern`: 模式<br>`path`: 目录 |
| `json_parse` | JSON 解析/格式化 | `content`: JSON 字符串<br>`format`: 是否格式化 |
| `text_transform` | 文本转换 | `content`: 文本<br>`transform`: 转换类型 |

#### HTTP 请求

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `http_request` | 发送 HTTP 请求 | `url`: URL<br>`method`: GET/POST/PUT/DELETE<br>`headers`: 请求头<br>`body`: 请求体 |

**http_request 示例**

```python
result = await context.call_tool("http_request", {
    "url": "https://api.example.com/data",
    "method": "GET",
    "headers": {"Authorization": "Bearer token"}
})
```

#### 系统操作

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `execute_command` | 执行 shell 命令 | `command`: 命令<br>`timeout`: 超时(秒) |
| `get_env` | 获取环境变量 | `name`: 变量名 |
| `set_env` | 设置环境变量 | `name`: 变量名<br>`value`: 值 |

#### 日期时间

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `current_time` | 获取当前时间 | `timezone`: 时区 |
| `date_parse` | 解析日期 | `date_string`: 日期字符串 |
| `date_diff` | 日期差计算 | `date1`, `date2`: 日期 |

#### 随机数

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `random_int` | 生成随机整数 | `min`, `max`: 范围 |
| `random_choice` | 随机选择 | `choices`: 选项列表 |
| `random_string` | 生成随机字符串 | `length`: 长度 |
| `uuid` | 生成 UUID | - |

#### 网络工具

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `url_parse` | 解析 URL | `url`: URL 字符串 |
| `url_build` | 构建 URL | `scheme`, `host`, `path`, `params` |
| `query_param` | URL 查询参数 | `url`, `action`: get/set/del |
| `host_lookup` | DNS 查询 | `hostname`: 主机名 |

#### 数学计算

| 工具 ID | 功能 | 主要参数 |
|---------|------|----------|
| `calc` | 数学计算 | `expression`: 表达式 |
| `percentage` | 百分比计算 | `value`, `total`, `operation` |
| `min_max` | 最大最小值 | `numbers`: 数字列表 |

#### MCP (Model Context Protocol)

| 工具 ID | 功能 |
|---------|------|
| `mcp` | 连接外部 MCP 服务器 |

---

## 自定义插件

推荐使用**装饰器**方式定义插件，无需继承任何类。

### 1. 自定义 Tool (装饰器方式)

```python
from openagents import tool
from typing import Any

@tool(name="weather", description="查询天气")
class WeatherTool:
    """天气查询工具"""

    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"tool.invoke"}
        self.api_key = self.config.get("api_key")

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        city = params.get("city")
        if not city:
            raise ValueError("'city' parameter is required")

        # 调用外部 API
        return {
            "city": city,
            "temperature": 25,
            "condition": "sunny"
        }

    # 可选：定义 schema
    def schema(self):
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }

    # 可选：fallback
    async def fallback(self, error, params, context):
        return {"city": params.get("city"), "error": str(error)}
```

**配置中使用**

```json
{
  "tools": [
    {
      "id": "weather",
      "impl": "mypackage.weather.WeatherTool",
      "config": {"api_key_env": "WEATHER_API_KEY"}
    }
  ]
}
```

### 2. 自定义 Tool (Protocol 方式)

如果不想用装饰器，可以直接实现 Protocol：

```python
from typing import Any

class WeatherTool:
    """天气查询工具 - Protocol 实现"""

    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"tool.invoke"}

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        city = params.get("city")
        return {"city": city, "temperature": 25}

# Loader 会自动验证 config 和 capabilities 属性
```

### 3. 自定义 Pattern (装饰器方式)

```python
from openagents import pattern
from typing import Any

@pattern
class MyPattern:
    """自定义推理模式"""

    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"pattern.execute", "pattern.react"}
        self.max_steps = config.get("max_steps", 10) if config else 10

    async def execute(self) -> Any:
        """主执行循环"""
        for step in range(self.max_steps):
            action = await self.react()
            if action["type"] == "final":
                return action.get("content")
        return "Max steps reached"

    async def react(self) -> dict[str, Any]:
        """单步决策"""
        # 使用 self.context 访问运行时数据
        # 使用 await self.call_tool() 调用工具
        # 使用 await self.call_llm() 调用 LLM
        # 使用 await self.emit() 发送事件
        return {"type": "final", "content": "Done"}
```

### 4. 自定义 Memory (装饰器方式)

Memory 接口现在有三个方法：
- `inject(context)` - 注入记忆到执行上下文
- `writeback(context)` - 保存当前交互
- `retrieve(query, context)` - 检索相关记忆

```python
from openagents import memory
from typing import Any

@memory
class PersistentMemory:
    """持久化记忆"""

    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"memory.inject", "memory.writeback", "memory.retrieve"}
        self.storage_path = config.get("storage_path", "./memory")

    async def inject(self, context: Any) -> None:
        """注入记忆到 context"""
        # 从存储加载历史
        history = self._load_history(context.session_id)
        context.memory_view["history"] = history

    async def writeback(self, context: Any) -> None:
        """保存当前交互"""
        record = {
            "input": context.input_text,
            "output": context.state.get("_runtime_last_output")
        }
        self._save_record(context.session_id, record)

    async def retrieve(self, query: str, context: Any) -> list[dict]:
        """检索相关记忆"""
        # 实现语义搜索、关键词匹配等
        history = context.memory_view.get("history", [])
        results = []
        for item in history:
            if query.lower() in str(item.get("input", "")).lower():
                results.append(item)
        return results[:5]
```

### 5. 自定义 Runtime

```python
from openagents import runtime

@runtime
class MyRuntime:
    """自定义运行时"""

    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"runtime.run"}

    async def run(self, *, agent_id, session_id, input_text, app_config, agents_by_id):
        """执行 Agent"""
        agent = agents_by_id[agent_id]
        # 自定义执行逻辑
        return "Custom result"
```

### 6. 三种实现方式对比

| 方式 | 优点 | 缺点 |
|------|------|------|
| **装饰器 (@tool)** | 最简单，自动注册 | 需要 import |
| **Protocol** | 无需继承，自由灵活 | 需要手动定义 config/capabilities |
| **继承 BasePlugin** | 有默认实现 | 紧耦合 |

推荐使用**装饰器**方式，代码最简洁。

---

## 高级特性

### Fallback 机制

在 Tool 中实现 fallback 方法：

```python
from openagents import tool
from openagents.interfaces.tool import RetryableToolError, PermanentToolError

@tool
class WeatherTool:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"tool.invoke"}

    async def invoke(self, params, context):
        # 尝试调用真实 API
        if random.random() < 0.1:  # 10% 失败率
            raise RetryableToolError("API timeout")
        return {"temp": 25}

    async def fallback(self, error, params, context):
        # 返回降级数据
        return {"temp": 20, "from_cache": True, "error": str(error)}

# Pattern 会自动调用 fallback
```

### 事件监听

```python
from openagents import Runtime

runtime = Runtime.from_config("agent.json")

async def on_tool_called(event):
    print(f"Tool called: {event.payload}")

runtime.event_bus.subscribe("tool.called", on_tool_called)
```
class MyPattern(PatternPlugin):
    async def execute(self, context: Any) -> Any:
        for step in range(self.max_steps):
            action = await self.react(context)

            if action["type"] == "tool_call":
                tool_id = action.get("tool")
                params = action.get("params", {})

                try:
                    result = await context.call_tool(tool_id, params)
                except Exception as e:
                    # Fallback: 尝试备用工具或返回错误
                    fallback_result = await self._fallback(tool_id, params, e)
                    if fallback_result:
                        continue
                    return {"type": "final", "content": f"Tool failed: {e}"}

                continue

            if action["type"] == "final":
                return action.get("content")

        return "Max steps reached"

    async def _fallback(self, tool_id: str, params: dict, error: Exception) -> Any:
        """Fallback 逻辑"""
        # 示例: 尝试简化参数重试
        return None
```

### 事件监听

通过事件总线监听 Agent 运行状态：

```python
# 创建 Runtime
runtime = Runtime.from_config("agent.json")

# 订阅事件
async def on_tool_called(event):
    print(f"工具调用: {event.payload}")

async def on_tool_succeeded(event):
    print(f"工具成功: {event.payload}")

async def on_tool_failed(event):
    print(f"工具失败: {event.payload}")

async def on_step_started(event):
    print(f"步骤开始: step={event.payload.get('step')}")

async def on_step_finished(event):
    print(f"步骤完成: step={event.payload.get('step')}")

# 注册监听器
runtime.event_bus.subscribe("tool.called", on_tool_called)
runtime.event_bus.subscribe("tool.succeeded", on_tool_succeeded)
runtime.event_bus.subscribe("tool.failed", on_tool_failed)
runtime.event_bus.subscribe("pattern.step_started", on_step_started)
runtime.event_bus.subscribe("pattern.step_finished", on_step_finished)

# 运行 Agent
result = await runtime.run(agent_id="assistant", session_id="demo", input_text="hello")
```

**可用事件**

| 事件名 | 触发时机 | payload |
|--------|----------|---------|
| `runtime.run_started` | 开始运行 | agent_id, session_id |
| `runtime.run_completed` | 运行完成 | agent_id, result |
| `runtime.run_failed` | 运行失败 | agent_id, error |
| `pattern.step_started` | 步骤开始 | step |
| `pattern.step_finished` | 步骤结束 | step, action |
| `tool.called` | 工具调用 | tool_id, params |
| `tool.succeeded` | 工具成功 | tool_id, result |
| `tool.failed` | 工具失败 | tool_id, error |
| `memory.inject_called` | 记忆注入 | - |
| `memory.writeback_called` | 记忆保存 | - |

### 会话管理

```python
runtime = Runtime.from_config("agent.json")

# 获取会话状态
state = await runtime.session_manager.get_state("session_id")
print(state)
# 返回: {"input_text": "...", "tool_results": [...], "state": {...}}

# 列出所有会话
sessions = await runtime.session_manager.list_sessions()
print(sessions)
# 返回: [{"session_id": "...", "agent_id": "...", ...}]

# 删除会话
await runtime.session_manager.delete_state("session_id")
```

---

## MCP (Model Context Protocol) 支持

MCP 是 Anthropic 推出的标准化协议，用于将 AI 模型连接到外部工具和数据源。

### 安装 MCP 依赖

```bash
pip install openagents[mcp]
# 或
pip install mcp>=1.0.0
```

### 连接本地 MCP 服务器 (stdio)

适用于本地的 Python/Node.js MCP 服务器：

```json
{
  "tools": [
    {
      "id": "mcp_filesystem",
      "type": "mcp",
      "config": {
        "server": {
          "command": "python",
          "args": ["/path/to/mcp_server.py"],
          "env": {"KEY": "value"}
        },
        "tools": ["read_file", "write_file"]
      }
    }
  ]
}
```

**参数说明**

| 参数 | 说明 |
|------|------|
| `server.command` | 可执行命令 (python, node, npx) |
| `server.args` | 命令参数列表 |
| `server.env` | 环境变量 (可选) |
| `tools` | 暴露的工具列表 (空=全部) |

### 连接远程 MCP 服务器 (HTTP/SSE)

适用于托管的 MCP 服务：

```json
{
  "tools": [
    {
      "id": "remote_mcp",
      "type": "mcp",
      "config": {
        "server": {
          "url": "https://example.com/mcp",
          "headers": {
            "Authorization": "Bearer your-token"
          }
        }
      }
    }
  ]
}
```

**参数说明**

| 参数 | 说明 |
|------|------|
| `server.url` | MCP 服务器 URL |
| `server.headers` | HTTP 请求头 |

### 调用 MCP 工具

MCP 工具的调用方式与普通工具相同：

```python
result = await context.call_tool("mcp_filesystem", {
    "tool": "read_file",
    "arguments": {"path": "/path/to/file.txt"}
})
```

---

## Skill 支持

Skill 是可复用的 Agent 行为定义，提供预定义的 system prompt 和工具集。

### 内置 Skill

| 类型 | 描述 | 配置参数 |
|------|------|----------|
| `researcher` | 研究专家 | `focus`: general / academic / news |
| `coder` | 编程专家 | `languages`: [python, javascript]<br>`strict`: true/false |
| `writer` | 写作专家 | `style`: informative / creative<br>`tone`: professional / casual |
| `analyst` | 数据分析专家 | `detail_level`: low / medium / high |
| `assistant` | 通用助手 | `personality`: helpful / funny / concise |

### 使用 Skill

```json
{
  "agents": [
    {
      "id": "researcher",
      "name": "Research Agent",
      "memory": {"type": "window_buffer", "config": {"window_size": 20}},
      "pattern": {"type": "react"},
      "llm": {"provider": "mock"},
      "skill": {
        "type": "researcher",
        "config": {"focus": "academic"}
      },
      "tools": [
        {"id": "search", "type": "builtin_search"},
        {"id": "http", "type": "http_request"}
      ]
    }
  ]
}
```

### 自定义 Skill

```python
from openagents.interfaces.skill import SkillPlugin
from openagents.interfaces.capabilities import (
    SKILL_EXECUTE,
    SKILL_GET_PROMPT,
    SKILL_GET_TOOLS
)
from typing import Any

class CustomerSupportSkill(SkillPlugin):
    """客服 Skill"""

    def __init__(self, config=None):
        super().__init__(
            config=config or {},
            capabilities={SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS}
        )
        self.company_name = self.config.get("company_name", "Our Company")

    async def execute(self, context: Any) -> Any:
        """执行 Skill"""
        return {"status": "ready", "skill": "customer_support"}

    def get_system_prompt(self, context: Any | None = None) -> str:
        """获取系统提示词"""
        return (
            f"You are a customer support representative for {self.company_name}. "
            "Your role is to help customers with their inquiries, "
            "provide product information, and resolve issues professionally.\n\n"
            "Guidelines:\n"
            "- Be polite and patient\n"
            "- Ask clarifying questions when needed\n"
            "- Provide accurate information\n"
            "- Escalate complex issues when necessary\n"
            "- Always maintain a positive attitude"
        )

    def get_tools(self) -> list[str]:
        """获取需要的工具"""
        return [
            "read_file",      # 读取产品文档
            "http_request",   # 查询订单
            "current_time"    # 查询营业时间
        ]
```

**在配置中使用**

```json
{
  "skill": {
    "impl": "mypackage.skills.CustomerSupportSkill",
    "config": {"company_name": "Acme Inc"}
  }
}
```

---

## 常见用例

### 用例 1: 简单的问答 Agent

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "qa",
      "name": "Q&A Agent",
      "memory": {"type": "buffer", "config": {"max_items": 50}},
      "pattern": {"type": "react"},
      "llm": {"provider": "mock"},
      "tools": []
    }
  ]
}
```

### 用例 2: 带搜索功能的 Agent

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "search_assistant",
      "name": "Search Assistant",
      "memory": {"type": "window_buffer", "config": {"window_size": 10}},
      "pattern": {"type": "react"},
      "llm": {"provider": "openai_compatible", "model": "gpt-4", "api_base": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
      "tools": [
        {"id": "search", "type": "builtin_search"},
        {"id": "http", "type": "http_request"}
      ]
    }
  ]
}
```

### 用例 3: 文件处理 Agent

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "file_processor",
      "name": "File Processor",
      "memory": {"type": "buffer", "config": {"max_items": 20}},
      "pattern": {"type": "plan_execute"},
      "llm": {"provider": "mock"},
      "tools": [
        {"id": "read", "type": "read_file"},
        {"id": "write", "type": "write_file"},
        {"id": "list", "type": "list_files"},
        {"id": "grep", "type": "grep_files"}
      ]
    }
  ]
}
```

### 用例 4: 带长期记忆的 Agent

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "remembering_assistant",
      "name": "Remembering Assistant",
      "memory": {"type": "mem0", "config": {"search_limit": 5}},
      "pattern": {"type": "react"},
      "llm": {"provider": "mock"},
      "tools": []
    }
  ]
}
```

---

## 最佳实践

### 1. 配置管理

- 使用环境变量存储敏感信息 (API keys)
- 将配置分为开发/生产环境
- 版本控制配置文件

```json
{
  "llm": {
    "provider": "openai",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

### 2. 工具安全

- 谨慎使用 `execute_command` 工具
- 限制文件操作范围
- 添加工具调用日志

### 3. 记忆策略

- 对话简短使用 `buffer`
- 对话长使用 `window_buffer`
- 需要语义搜索使用 `mem0`

### 4. 错误处理

- 在 Pattern 中添加 try-catch
- 设置合理的 `max_steps`
- 监听 `tool.failed` 事件

### 5. 性能优化

- 减少不必要的历史记录
- 适时清理会话
- 监控工具调用次数

---

## 故障排查

### 问题: Agent 无响应

**可能原因**
1. LLM 配置错误
2. 网络问题
3. 超时设置过短

**排查方法**
```python
# 检查 LLM 配置
runtime = Runtime.from_config("agent.json")

# 增加超时时间
pattern_config = {
    "type": "react",
    "config": {"step_timeout_ms": 60000}
}
```

### 问题: 工具调用失败

**可能原因**
1. 工具参数错误
2. 权限问题
3. 外部服务不可用

**排查方法**
```python
# 监听工具失败事件
async def on_tool_failed(event):
    print(f"工具 {event.payload['tool_id']} 失败: {event.payload['error']}")

runtime.event_bus.subscribe("tool.failed", on_tool_failed)
```

### 问题: 记忆不工作

**可能原因**
1. Memory 插件未正确配置
2. Mem0 未安装

**排查方法**
```bash
# 安装 mem0
pip install mem0ai
```

### 问题: MCP 连接失败

**可能原因**
1. MCP 服务器未运行
2. 命令/路径错误
3. 依赖未安装

**排查方法**
```bash
# 测试 MCP 服务器
python /path/to/mcp_server.py
```

---

## API 参考

### 核心类

#### Runtime

```python
from openagents import Runtime

# 从配置文件创建
runtime = Runtime.from_config("agent.json")

# 或从 AppConfig 创建
from openagents import load_config
config = load_config("agent.json")
runtime = Runtime(config)

# 异步运行
result = await runtime.run(agent_id="...", session_id="...", input_text="...")

# 同步运行
result = runtime.run_sync(agent_id="...", session_id="...", input_text="...")

# 访问组件
runtime.event_bus
runtime.session_manager
```

#### load_config

```python
from openagents import load_config

config = load_config("agent.json")
# 返回: AppConfig 对象
```

### 同步入口函数

#### run_agent

```python
from openagents import run_agent

result = run_agent(
    "agent.json",
    agent_id="assistant",
    session_id="demo",
    input_text="hello"
)
```

#### run_agent_with_config

```python
from openagents import load_config, run_agent_with_config

config = load_config("agent.json")
result = run_agent_with_config(
    config,
    agent_id="assistant",
    session_id="demo",
    input_text="hello"
)
```

---

## 相关资源

- GitHub: https://github.com/openagents/openagent-py-sdk
- MCP 规范: https://modelcontextprotocol.io
- Mem0: https://github.com/mem0ai/mem0

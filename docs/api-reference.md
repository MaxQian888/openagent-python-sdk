# API 参考

## 核心类

### Runtime

Agent 运行时入口。

```python
from openagents import Runtime
```

#### 方法

##### `Runtime.from_config(config_path: str | Path) -> Runtime`

从配置文件创建 Runtime。

```python
runtime = Runtime.from_config("agent.json")
```

##### `runtime.run(agent_id: str, session_id: str, input_text: str) -> Any`

运行 Agent。

```python
result = await runtime.run(
    agent_id="assistant",
    session_id="demo",
    input_text="Hello!"
)
```

##### `runtime.close() -> None`

关闭 Runtime，释放资源。

```python
await runtime.close()
```

#### 属性

##### `runtime.event_bus -> EventBusPlugin`

事件总线实例。

```python
runtime.event_bus.subscribe("tool.called", handler)
```

##### `runtime.session_manager -> SessionManagerPlugin`

会话管理器实例。

```python
state = await runtime.session_manager.get_state("session_id")
```

---

### 加载配置

```python
from openagents import load_config, AppConfig
```

##### `load_config(path: str | Path) -> AppConfig`

从 JSON 文件加载配置。

```python
config = load_config("agent.json")
```

---

## 装饰器

### `@tool`

定义一个 Tool 插件。

```python
from openagents import tool

@tool(name="my_tool", description="Tool description")
class MyTool:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"tool.invoke"}

    async def invoke(self, params, context):
        return {"result": "ok"}

    # 可选方法
    async def fallback(self, error, params, context):
        return {"error": str(error)}

    def schema(self):
        return {"type": "object", "properties": {}}
```

### `@memory`

定义一个 Memory 插件。

```python
from openagents import memory

@memory
class MyMemory:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"memory.inject", "memory.writeback", "memory.retrieve"}

    async def inject(self, context):
        context.memory_view["history"] = []

    async def writeback(self, context):
        # 保存交互
        pass

    async def retrieve(self, query, context):
        return []
```

### `@pattern`

定义一个 Pattern 插件。

```python
from openagents import pattern

@pattern
class MyPattern:
    def __init__(self, config=None):
        self.config = config or {}
        self.capabilities = {"pattern.execute", "pattern.react"}

    async def execute(self):
        return await self.react()

    async def react(self):
        return {"type": "final", "content": "Done"}
```

---

## 接口定义

### ToolPlugin

```python
from openagents.interfaces.tool import ToolPlugin, ToolError, RetryableToolError, PermanentToolError
```

#### 属性

- `config: dict` - 配置
- `capabilities: set` - 能力集合
- `tool_name: str` - 工具名称

#### 方法

##### `async invoke(params: dict, context: Any) -> Any`

执行工具。

##### `async invoke_stream(params: dict, context: Any) -> AsyncIterator[dict]`

流式执行工具。

##### `def schema() -> dict`

返回 JSON Schema。

##### `def describe() -> dict`

返回工具描述。

##### `async fallback(error: Exception, params: dict, context: Any) -> Any`

失败时的降级处理。

### MemoryPlugin

```python
from openagents.interfaces.memory import MemoryPlugin
```

#### 方法

##### `async inject(context: Any) -> None`

注入记忆到执行上下文。

##### `async writeback(context: Any) -> None`

保存当前交互。

##### `async retrieve(query: str, context: Any) -> list[dict]`

检索相关记忆。

##### `async close() -> None`

清理资源。

### PatternPlugin

```python
from openagents.interfaces.pattern import PatternPlugin, ExecutionContext
```

#### 属性

- `context: ExecutionContext | None` - 执行上下文

#### 方法

##### `async setup(agent_id, session_id, input_text, state, tools, llm_client, llm_options, event_bus) -> None`

初始化上下文。

##### `async execute() -> Any`

执行主逻辑。

##### `async react() -> dict`

单步决策。

##### `async emit(event_name: str, **payload) -> None`

发送事件。

##### `async call_tool(tool_id: str, params: dict) -> Any`

调用工具。

##### `async call_llm(messages: list, model: str, temperature: float, max_tokens: int) -> str`

调用 LLM。

### ExecutionContext

```python
from openagents.interfaces.pattern import ExecutionContext
```

#### 属性

- `agent_id: str` - Agent ID
- `session_id: str` - 会话 ID
- `input_text: str` - 输入文本
- `state: dict` - 会话状态
- `tools: dict` - 工具字典
- `llm_client: Any` - LLM 客户端
- `llm_options: Any` - LLM 配置
- `event_bus: EventBusPlugin` - 事件总线
- `memory_view: dict` - 记忆视图
- `tool_results: list` - 工具结果列表
- `scratch: dict` - 临时存储

---

## 能力常量

```python
from openagents.interfaces.capabilities import (
    MEMORY_INJECT,
    MEMORY_WRITEBACK,
    MEMORY_RETRIEVE,
    PATTERN_EXECUTE,
    PATTERN_REACT,
    TOOL_INVOKE,
    RUNTIME_RUN,
)
```

---

## 事件

```python
from openagents.interfaces.events import RuntimeEvent

# 生命周期事件
RUNTIME_SHUTDOWN_REQUESTED
RUNTIME_SHUTDOWN_STARTED
RUNTIME_SHUTDOWN_COMPLETED

# 运行事件
RUN_REQUESTED
RUN_VALIDATED
SESSION_ACQUIRED
CONTEXT_CREATED
MEMORY_INJECTED
MEMORY_INJECT_FAILED
MEMORY_WRITEBACK_SUCCEEDED
MEMORY_WRITEBACK_FAILED
RUN_COMPLETED
RUN_FAILED
```

---

## 异常

```python
from openagents.errors.exceptions import ConfigError, PluginLoadError
```

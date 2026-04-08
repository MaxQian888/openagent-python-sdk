# 插件开发

这份文档说明 plugin 是如何被发现和实例化的、每类 plugin 需要声明哪些 capabilities，以及怎样写出能被当前 loader 正常加载的自定义组件。

## Plugin Loader 怎么工作

核心逻辑在 `openagents.plugins.loader`。

解析顺序：

1. 如果配置里有 `impl`，优先按 Python dotted path 导入并实例化。
2. 否则如果有 `type`，再去 builtin registry 或 decorator registry 查找。
3. 校验必需 capabilities。
4. 校验声明过 capability 的方法是否真的存在。

实例化策略依次尝试：

- `factory(config=config)`
- `factory(config)`
- `factory()`

因此对当前代码来说，class-based plugin 最稳。

## Plugin 来源

一个 plugin 当前可以来自三类位置：

- `openagents.plugins.registry` 里的 builtin registry
- `openagents.decorators` 维护的 decorator registry
- 配置里的 `impl` Python 导入路径

## Capability 要求

| Plugin 类型 | 必需 capability | 必需方法 |
| --- | --- | --- |
| memory | 不强制固定集合，但 loader 会检查声明过的方法 | 声明了就要实现 `inject` / `writeback` |
| pattern | `pattern.execute` | `execute` |
| tool | `tool.invoke` | `invoke` |
| runtime | `runtime.run` | `run` |
| session | `session.manage` | `session` |
| events | `event.emit`，且实际还要求可订阅 | `emit`、`subscribe` |

常用 capability 常量在 `openagents.interfaces.capabilities`。

## Agent 级执行 Seam

除了 `memory / pattern / tool / skill` 这些直接业务构件之外，当前 SDK 还有三类 agent 级执行 seam：

- `tool_executor`
- `execution_policy`
- `context_assembler`

它们控制的是执行策略，不是业务能力本身。

当前这三类 seam 的约束是：

- builtin 可以用 `type`
- 自定义实现可以用 `impl`
- 当前不提供 decorator registry，也没有对应的 `get_*` / `list_*` API

## 推荐写法

优先使用 class-based plugin，并显式声明：

- `config`
- `capabilities`

`@tool` 虽然支持 function-style 注册，但当前 runtime loader 是按“实例化 plugin”这个模型工作的，所以真正用于配置加载时，class-based Tool 更可靠。

## 自定义 Tool

```python
from __future__ import annotations

from typing import Any

from openagents import tool
from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin


@tool(name="echo_tool")
class EchoTool(ToolPlugin):
    name = "echo_tool"
    description = "回显输入文本。"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})
        self._prefix = self.config.get("prefix", "echo")

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        text = str(params.get("text", "")).strip()
        return {"text": text, "output": f"{self._prefix}: {text}"}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要回显的文本"}
            },
            "required": ["text"],
        }
```

配置引用：

```json
{
  "tools": [
    {
      "id": "echo",
      "impl": "mypackage.plugins.EchoTool",
      "config": {"prefix": "custom"}
    }
  ]
}
```

## 自定义 Memory

```python
from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK
from openagents.interfaces.memory import MemoryPlugin


class CustomMemory(MemoryPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={MEMORY_INJECT, MEMORY_WRITEBACK})
        self._state_key = self.config.get("state_key", "custom_history")

    async def inject(self, context: Any) -> None:
        history = context.state.get(self._state_key, [])
        context.memory_view["history"] = list(history)

    async def writeback(self, context: Any) -> None:
        history = list(context.state.get(self._state_key, []))
        history.append(
            {
                "input": context.input_text,
                "output": context.state.get("_runtime_last_output", ""),
            }
        )
        context.state[self._state_key] = history
```

## 自定义 Pattern

pattern 通过 `setup()` 收到运行时上下文，通常会保存在 `self.context` 上。

```python
from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT
from openagents.interfaces.pattern import ExecutionContext


class CustomPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_EXECUTE, PATTERN_REACT}
        self.context: ExecutionContext | None = None

    async def setup(self, agent_id, session_id, input_text, state, tools, llm_client, llm_options, event_bus) -> None:
        self.context = ExecutionContext(
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
            state=state,
            tools=tools,
            llm_client=llm_client,
            llm_options=llm_options,
            event_bus=event_bus,
        )

    async def react(self) -> dict[str, Any]:
        assert self.context is not None
        return {"type": "final", "content": self.context.input_text}

    async def execute(self) -> Any:
        action = await self.react()
        self.context.state["_runtime_last_output"] = action["content"]
        return action["content"]
```

## 自定义 Runtime / Session / Event Bus

只有当 builtin 的 `default`、`in_memory`、`async` 不够用时，才建议写这三类组件。

### Runtime

必须声明 `runtime.run`，并实现 `run(...)`。

### Session manager

必须声明 `session.manage`，并实现 `session(...)`。

如果你希望行为接近 builtin 实现，最好同时实现：

- `get_state()`
- `set_state()`
- `delete_session()`
- `list_sessions()`

### Event bus

必须实现：

- `subscribe(event_name, handler)`
- `emit(event_name, **payload)`

如果要对齐 builtin 功能，最好再实现：

- `get_history()`
- `clear_history()`

## 自定义 Tool Executor

适用场景：

- 想统一 tool timeout
- 想统一 tool error 规范化
- 想对 `invoke` / `invoke_stream` 做额外包装

最小契约：

- `execute(request) -> ToolExecutionResult`
- `execute_stream(request)`

配置示例：

```json
{
  "tool_executor": {
    "impl": "mypackage.runtime.SafeLikeToolExecutor",
    "config": {"default_timeout_ms": 2000}
  }
}
```

## 自定义 Execution Policy

适用场景：

- 文件访问边界
- tool allow/deny
- 按 workspace/env 决定某个 tool 是否能执行

最小契约：

- `evaluate(request) -> PolicyDecision`

配置示例：

```json
{
  "execution_policy": {
    "impl": "mypackage.runtime.WorkspacePolicy",
    "config": {"read_roots": ["workspace"]}
  }
}
```

## 自定义 Context Assembler

适用场景：

- 裁剪 transcript
- 裁剪 session artifacts
- 注入 assembly metadata
- 在 run 前后做轻量 context bookkeeping

最小契约：

- `assemble(request, session_state, session_manager) -> ContextAssemblyResult`
- `finalize(request, session_state, session_manager, result) -> result`

配置示例：

```json
{
  "context_assembler": {
    "impl": "mypackage.runtime.CustomContextAssembler",
    "config": {"max_messages": 20}
  }
}
```

## Decorator 注册

decorator 注册的本质，是把符号加入当前进程内的 registry。

```python
from openagents import memory, pattern, runtime, session, event_bus, tool
```

可用装饰器：

- `@tool(name="...")`
- `@memory(name="...")`
- `@pattern(name="...")`
- `@runtime(name="...")`
- `@session(name="...")`
- `@event_bus(name="...")`

然后在配置里通过 `type` 引用这个注册名。

## 如何测试 Plugin

最小测试流程：

1. 构造一个 config dict。
2. 用 `load_config_dict()` 加载。
3. 创建 `Runtime(config)`。
4. 运行目标 agent。
5. 断言输出、session state、事件或 tool results。

示例：

```python
import pytest

from openagents.config.loader import load_config_dict
from openagents.runtime.runtime import Runtime


@pytest.mark.asyncio
async def test_custom_tool_plugin():
    config = load_config_dict(
        {
            "version": "1.0",
            "agents": [
                {
                    "id": "test",
                    "name": "test",
                    "memory": {"type": "buffer"},
                    "pattern": {"impl": "tests.fixtures.custom_plugins.CustomPattern"},
                    "llm": {"provider": "mock"},
                    "tools": [
                        {"id": "custom_tool", "impl": "tests.fixtures.custom_plugins.CustomTool"}
                    ],
                }
            ],
        }
    )
    runtime = Runtime(config)
    result = await runtime.run(agent_id="test", session_id="s1", input_text="hello")
    assert result
```

仓库里的 `examples/custom_impl/` 是一个很好的真实参考。

## 相关文档

- [配置参考](configuration.md)
- [开发指南](developer-guide.md)
- [API 参考](api-reference.md)

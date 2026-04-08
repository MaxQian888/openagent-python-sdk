# API 参考

本文档覆盖当前对外导出的 package API，以及最关键的接口契约。

## Package Exports

```python
from openagents import (
    AppConfig,
    Runtime,
    load_config,
    run_agent,
    run_agent_with_config,
    tool,
    memory,
    pattern,
    runtime,
    skill,
    session,
    event_bus,
    get_tool,
    get_memory,
    get_pattern,
    get_runtime,
    get_skill,
    get_session,
    get_event_bus,
    list_tools,
    list_memories,
    list_patterns,
    list_runtimes,
    list_skills,
    list_sessions,
    list_event_buses,
)
```

## Runtime

### `Runtime(config: AppConfig, _skip_plugin_load: bool = False, _config_path: Path | None = None)`

主入口。内部持有 app config、全局 runtime / session / events 组件，以及 session 级插件缓存。

### `Runtime.from_config(config_path: str | Path) -> Runtime`

从磁盘读取 JSON，完成校验，然后构造 runtime。

### `await runtime.run(*, agent_id: str, session_id: str, input_text: str) -> Any`

执行一次 agent run。

可能抛出：

- `ConfigError`：`agent_id` 不存在
- 下游 runtime / pattern / tool / provider 自己抛出的异常

### `await runtime.run_detailed(*, request: RunRequest) -> RunResult`

结构化执行入口。

相比 `run()`：

- 输入是显式 `RunRequest`
- 输出是显式 `RunResult`
- 更适合上层 runtime / framework / product 做编排

### `runtime.run_sync(*, agent_id: str, session_id: str, input_text: str) -> Any`

`run()` 的同步封装，内部使用 `asyncio.run()`。

### `await runtime.reload() -> None`

重新加载最初用于构造 runtime 的配置文件。

行为要点：

- 会更新发生变化的 agent 配置
- 会保留现有的全局 runtime / session / events 组件
- 顶层组件发生变化时会抛出 `ConfigError`

### `await runtime.reload_agent(agent_id: str) -> None`

清理该 agent 在所有活跃 session 下的插件缓存。

### `runtime.get_session_count() -> int`

返回 runtime 当前维护的 session 数量。

### `await runtime.list_agents() -> list[dict[str, Any]]`

返回已加载 agent 的最小信息列表，只包含 id 和 name。

### `await runtime.get_agent_info(agent_id: str) -> dict[str, Any] | None`

返回 agent 配置摘要，以及当前是否已经加载出具体 plugin 实例。

### `await runtime.close_session(session_id: str) -> None`

关闭单个 session，并在可用时调用 `memory.close()`。

### `await runtime.close() -> None`

关闭所有 session memory，然后依次关闭 runtime / session / events 组件（如果它们实现了 `close()`）。

### `runtime.event_bus`

属性，返回当前配置的 event bus 实例。

### `runtime.session_manager`

属性，返回当前配置的 session manager 实例。

## Config Loading

### `load_config(path: str | Path) -> AppConfig`

从磁盘读取 JSON，做结构和语义校验，然后返回 `AppConfig`。

可能抛出：

- `ConfigError`：文件不存在、JSON 非法、schema 错误、验证失败

### `AppConfig`

主要字段：

- `version: str`
- `agents: list[AgentDefinition]`
- `runtime: RuntimeRef`
- `session: SessionRef`
- `events: EventBusRef`

### `AgentDefinition`

主要字段：

- `id: str`
- `name: str`
- `memory: MemoryRef`
- `pattern: PatternRef`
- `llm: LLMOptions | None`
- `skill: SkillRef | None`
- `tool_executor: ToolExecutorRef | None`
- `execution_policy: ExecutionPolicyRef | None`
- `context_assembler: ContextAssemblerRef | None`
- `tools: list[ToolRef]`
- `runtime: RuntimeOptions`

### `RuntimeOptions`

agent 级 runtime 限制：

- `max_steps`
- `step_timeout_ms`
- `session_queue_size`
- `event_queue_size`

### `LLMOptions`

provider 配置：

- `provider`
- `model`
- `api_base`
- `api_key_env`
- `temperature`
- `max_tokens`
- `timeout_ms`
- `extra`

## Sync Helpers

### `run_agent(config_path, *, agent_id, session_id="default", input_text) -> Any`

从文件路径构造 runtime，然后立即调用 `run_sync()`。

### `run_agent_with_config(config, *, agent_id, session_id="default", input_text) -> Any`

从已加载的 config 对象构造 runtime，然后立即调用 `run_sync()`。

## Decorators

### `@tool(name: str | None = None, description: str = "")`

把 tool 符号注册进 decorator registry。

### `@memory(name: str | None = None)`

注册 memory class。

### `@pattern(name: str | None = None)`

注册 pattern class。

### `@runtime(name: str | None = None)`

注册 runtime class。

### `@session(name: str | None = None)`

注册 session manager class。

### `@event_bus(name: str | None = None)`

注册 event bus class。

## Registry Helpers

查询 helper：

- `get_tool(name)`
- `get_memory(name)`
- `get_pattern(name)`
- `get_runtime(name)`
- `get_session(name)`
- `get_event_bus(name)`

列表 helper：

- `list_tools()`
- `list_memories()`
- `list_patterns()`
- `list_runtimes()`
- `list_sessions()`
- `list_event_buses()`

注意：这些 helper 面向 decorator registry，不等于完整 builtin registry。

## 接口契约

### `ExecutionContext`

pattern 和 tool 可访问的主要字段：

- `agent_id`
- `session_id`
- `input_text`
- `state`
- `tools`
- `llm_client`
- `llm_options`
- `event_bus`
- `memory_view`
- `tool_results`
- `scratch`
- `transcript`
- `session_artifacts`
- `assembly_metadata`
- `run_request`
- `tool_executor`
- `execution_policy`
- `usage`
- `artifacts`

### `ToolPlugin`

主要方法：

- `async invoke(params, context) -> Any`
- `async invoke_stream(params, context)`
- `schema() -> dict`
- `describe() -> dict`
- `validate_params(params) -> tuple[bool, str | None]`
- `get_dependencies() -> list[str]`
- `async fallback(error, params, context) -> Any`
- `execution_spec() -> ToolExecutionSpec`

### `ToolExecutorPlugin`

主要方法：

- `async execute(request) -> ToolExecutionResult`
- `async execute_stream(request)`

### `ExecutionPolicyPlugin`

主要方法：

- `async evaluate(request) -> PolicyDecision`

### `MemoryPlugin`

主要方法：

- `async inject(context) -> None`
- `async writeback(context) -> None`
- `async retrieve(query, context) -> list[dict[str, Any]]`
- `async close() -> None`

### `PatternPlugin`

主要方法：

- `async setup(...) -> None`
- `async execute() -> Any`
- `async react() -> dict[str, Any]`
- `async emit(event_name, **payload) -> None`
- `async call_tool(tool_id, params=None) -> Any`
- `async call_llm(messages, model=None, temperature=None, max_tokens=None) -> str`
- `async compress_context() -> None`
- `add_artifact(...) -> None`

### `SkillPlugin`

主要方法：

- `get_system_prompt(context=None) -> str`
- `get_tools() -> list[Any]`
- `get_metadata() -> dict[str, Any]`
- `augment_context(context) -> None`
- `filter_tools(tools, context=None) -> dict[str, Any]`
- `async before_run(context) -> None`
- `async after_run(context, result) -> Any`

### `ContextAssemblerPlugin`

主要方法：

- `async assemble(request, session_state, session_manager) -> ContextAssemblyResult`
- `async finalize(request, session_state, session_manager, result) -> result`

### `RuntimePlugin`

主要方法：

- `async initialize() -> None`
- `async validate() -> None`
- `async health_check() -> bool`
- `async run(...) -> Any`
- `async pause() -> None`
- `async resume() -> None`
- `async close() -> None`

### `SessionManagerPlugin`

主要方法：

- `async with session(session_id)`
- `async get_state(session_id) -> dict[str, Any]`
- `async set_state(session_id, state) -> None`
- `async delete_session(session_id) -> None`
- `async list_sessions() -> list[str]`
- `async append_message(session_id, message) -> None`
- `async load_messages(session_id) -> list[dict[str, Any]]`
- `async save_artifact(session_id, artifact) -> None`
- `async list_artifacts(session_id) -> list[SessionArtifact]`
- `async create_checkpoint(session_id, checkpoint_id) -> SessionCheckpoint`
- `async load_checkpoint(session_id, checkpoint_id) -> SessionCheckpoint | None`
- `async close() -> None`

### `EventBusPlugin`

主要方法：

- `subscribe(event_name, handler) -> None`
- `async emit(event_name, **payload) -> RuntimeEvent`
- `async get_history(event_name=None, limit=None) -> list[RuntimeEvent]`
- `async clear_history() -> None`
- `async close() -> None`

## Capability 常量

常用 capability 常量位于 `openagents.interfaces.capabilities`：

- `MEMORY_INJECT`
- `MEMORY_WRITEBACK`
- `MEMORY_RETRIEVE`
- `PATTERN_EXECUTE`
- `PATTERN_REACT`
- `TOOL_INVOKE`

runtime、session、events 相关 capability 常量分别位于它们自己的 interface module。

## Event Names

builtin runtime 相关事件名位于 `openagents.interfaces.events`：

- `run.requested`
- `run.validated`
- `session.acquired`
- `context.created`
- `memory.injected`
- `memory.inject_failed`
- `memory.writeback_succeeded`
- `memory.writeback_failed`
- `run.completed`
- `run.failed`
- `runtime.shutdown_requested`
- `runtime.shutdown_started`
- `runtime.shutdown_completed`

## 异常类型

定义在 `openagents.errors.exceptions`：

- `OpenAgentsError`
- `ConfigError`
- `PluginLoadError`
- `CapabilityError`

## 相关文档

- [配置参考](configuration.md)
- [开发指南](developer-guide.md)
- [插件开发](plugin-development.md)

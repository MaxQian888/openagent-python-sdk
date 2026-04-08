# 开发指南

这份文档关注运行时行为、仓库本地开发方式，以及 builtin 实现当前做了什么、没做什么。

## 执行流程

一次 `Runtime.run()` 的主流程如下：

1. 根据 `agent_id` 找到目标 agent。
2. 在当前 `session_id` 下解析或复用该 agent 的插件实例。
3. 把执行委托给配置好的 runtime plugin。
4. 通过 session manager 获取并锁定 session state。
5. 构建 `ExecutionContext`，挂上 tools、LLM client 和 event bus。
6. 调用 memory `inject()`。
7. 调用 pattern `execute()`。
8. 调用 memory `writeback()`。
9. 把输出写入 session state，并发出生命周期事件。

builtin runtime 实现在 `openagents/plugins/builtin/runtime/default_runtime.py`。

## Session 隔离

session 隔离由两层共同保证：

- `Runtime` 维护按 `session_id` 和 `agent_id` 分组的插件缓存
- `InMemorySessionManager` 为每个 `session_id` 使用一个 async lock

这意味着：

- 同一 session：串行执行
- 不同 session：可以并发执行
- memory 实例：按 session 隔离
- tool 实例：按 session 隔离

## Hot Reload

`Runtime.reload()` 会重新从磁盘加载最初使用的配置文件，并把变更应用到未来请求。

它会更新：

- 发生变化的 agent 定义
- 被移除 agent 的插件缓存
- 发生变化 agent 的 runtime 级 LLM client cache

它不会热切换：

- 顶层 `runtime`
- 顶层 `session`
- 顶层 `events`

这些顶层组件一旦变化，`Runtime.reload()` 会抛出 `ConfigError`。

`Runtime.reload_agent(agent_id)` 更窄，只会清理该 agent 在各个 session 下的插件缓存，不会替换全局组件。

## Builtin Runtime 行为

`DefaultRuntime` 负责：

- 为每个 agent 创建或复用 LLM client
- 发出 run 生命周期事件
- 按策略处理 memory inject / writeback
- 依赖 session manager 提供锁和 state

builtin memory 错误策略由 `memory.on_error` 决定：

- `continue`：发失败事件，但继续执行
- `fail`：直接向上抛错并终止本轮 run

## Builtin Pattern 说明

### `react`

`ReActPattern` 当前有两种模式。

有 LLM 时：

- 给模型发送严格的 JSON-only prompt
- 只接受 `final`、`continue`、`tool_call` 三种 action
- 对 `tool_call` 会暂存 pending tool id，下一步把结果格式化成 `Tool[tool_id] => ...`

没有 LLM 时：

- `/tool <tool_id> <query>` 会触发一次 tool call，参数形如 `{"query": "..."}`
- 其他输入会走 echo fallback，并带上 conversation history

### `plan_execute`

- 先用 LLM 生成 plan
- 把 plan 放在 `context.scratch["_plan"]`
- 然后按步骤执行
- 没有 LLM 时基本没有实际价值

### `reflexion`

- 会根据最近的 tool results 做反思
- 可以产出带调整参数的 retry
- 到达 `max_retries` 或 `max_steps` 后停止

## Builtin Memory 说明

### `buffer`

- 把交互历史保存在 session state 里
- 默认 state key：`memory_buffer`
- 默认 memory view key：`history`
- 写回字段包括 `input`、`tool_results`，以及可选的 `output`

### `window_buffer`

- 基于 `buffer` 实现
- 会把 `window_size` 转成 `max_items`
- 注入到 `memory_view` 的始终是最近一段窗口数据

### `mem0`

- 需要额外安装 `mem0` 依赖
- 不单独配置 memory 专用 API key，而是复用 agent 的 LLM 配置
- 会把命中的语义记忆写入 `memory_view["mem0_history"]` 和 `memory_view["history"]`

### `chain`

- 通过 `config.memories` 组合多个 memory refs
- 适合把短期 buffer 和记忆 backend 组合使用

## Events

builtin event bus 会把事件历史保存在内存中，并支持 `*` wildcard subscriber。

runtime 发出的生命周期事件包括：

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

pattern 侧常见事件包括：

- `pattern.step_started`
- `pattern.step_finished`
- `tool.called`
- `tool.succeeded`
- `tool.failed`
- `llm.called`
- `llm.succeeded`

## 本地开发

安装开发依赖：

```bash
uv sync --extra dev
```

运行测试：

```bash
uv run pytest -q
```

运行 quickstart：

```bash
uv run python examples/quickstart/run_demo.py
```

运行真实 provider 示例：

```bash
uv run python examples/openai_compatible/run_demo.py
uv run python examples/longcat/run_demo.py
```

## 常见问题

### `Unknown agent id`

传给 `Runtime.run()` 的 `agent_id` 跟配置里的 `agents[].id` 不一致。

### `llm.api_base is required for provider 'openai_compatible'`

`openai_compatible` 在运行前就会被校验，必须在 JSON 里配置 `llm.api_base`。

### mock 能跑，但去掉 `llm` 后 pattern 不工作

不是所有 pattern 都能在没有 LLM 的情况下正常工作：

- `react`：可以，有 non-LLM fallback
- `plan_execute`：基本不行
- `reflexion`：没有 LLM 时只会返回 `continue`，不会产生有效结果

### MCP tool 导入失败

安装 MCP extra：

```bash
uv add "openagents-sdk[mcp]"
```

### Mem0 memory 一直是空

安装 Mem0 extra，并保证 agent 的 LLM 凭据可用：

```bash
uv add "openagents-sdk[mem0]"
```

## 延伸阅读

- [配置参考](configuration.md)
- [插件开发](plugin-development.md)
- [API 参考](api-reference.md)
- [示例说明](examples.md)

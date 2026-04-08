# 配置参考

本文档描述 `openagents.config.load_config()` 和 `Runtime.from_config()` 当前接受的 JSON 配置格式。

## 根结构

```json
{
  "version": "1.0",
  "runtime": {"type": "default"},
  "session": {"type": "in_memory"},
  "events": {"type": "async"},
  "agents": []
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | string | 否 | `"1.0"` | 必须是非空字符串 |
| `runtime` | object | 否 | `{ "type": "default" }` | App 级 runtime plugin selector |
| `session` | object | 否 | `{ "type": "in_memory" }` | App 级 session manager selector |
| `events` | object | 否 | `{ "type": "async" }` | App 级 event bus selector |
| `agents` | array | 是 | 无 | 至少要有一个 agent |

## Selector 规则

配置里有两种 selector：

- `type`：选择 builtin plugin 或 decorator 注册名
- `impl`：通过 Python dotted path 导入符号

但不同位置的规则不完全一样。

### 顶层 selector

顶层 `runtime`、`session`、`events` 只能提供一个 selector。

合法：

```json
{"runtime": {"type": "default"}}
```

```json
{"runtime": {"impl": "mypkg.runtime.CustomRuntime"}}
```

非法：

```json
{"runtime": {"type": "default", "impl": "mypkg.runtime.CustomRuntime"}}
```

### Agent 级 selector

agent 内的 `memory`、`pattern`、`tools[]` 至少要提供一个 `type` 或 `impl`。

如果两者同时出现，loader 以 `impl` 为准，`type` 会被忽略。

## App 级组件

### `runtime`

```json
{
  "runtime": {
    "type": "default",
    "config": {}
  }
}
```

当前 builtin runtime：

- `default`

### `session`

```json
{
  "session": {
    "type": "in_memory",
    "config": {}
  }
}
```

当前 builtin session manager：

- `in_memory`

### `events`

```json
{
  "events": {
    "type": "async",
    "config": {}
  }
}
```

当前 builtin event bus：

- `async`

## Agent 结构

```json
{
  "id": "assistant",
  "name": "demo-agent",
  "memory": {"type": "window_buffer"},
  "pattern": {"type": "react"},
  "llm": {"provider": "mock"},
  "tools": [],
  "runtime": {
    "max_steps": 16,
    "step_timeout_ms": 30000,
    "session_queue_size": 1000,
    "event_queue_size": 2000
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | `Runtime.run()` 用它定位 agent |
| `name` | string | 是 | 展示名称 |
| `memory` | object | 是 | Memory plugin selector 和 config |
| `pattern` | object | 是 | Pattern plugin selector 和 config |
| `llm` | object | 否 | 可选的 LLM provider 配置 |
| `tool_executor` | object | 否 | agent 级 tool execution seam selector |
| `execution_policy` | object | 否 | agent 级 execution policy seam selector |
| `context_assembler` | object | 否 | agent 级 context assembly seam selector |
| `tools` | array | 否 | Tool selectors，禁用项不会被加载 |
| `runtime` | object | 否 | agent 级 runtime 参数，不是 plugin selector |

## Memory

```json
{
  "memory": {
    "type": "window_buffer",
    "config": {
      "window_size": 20
    },
    "on_error": "continue"
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `type` / `impl` | string | 无 | 至少要有一个 |
| `config` | object | `{}` | plugin 自己消费的配置 |
| `on_error` | string | `"continue"` | 只能是 `continue` 或 `fail` |

当前 builtin memory：

- `buffer`：把交互历史追加到 session state 的 `memory_buffer`
- `window_buffer`：在 `buffer` 基础上只保留最近 `window_size` 条
- `mem0`：可选的语义记忆 backend，复用 agent 的 LLM 配置
- `chain`：通过 `config.memories` 组合多个 memory plugin

常见 config：

- `buffer`
  - `state_key`
  - `view_key`
  - `max_items`
- `window_buffer`
  - `window_size`
- `mem0`
  - `collection_name`
  - `search_limit`
- `chain`
  - `memories`

## Pattern

```json
{
  "pattern": {
    "type": "react",
    "config": {
      "max_steps": 8,
      "step_timeout_ms": 30000
    }
  }
}
```

当前 builtin pattern：

- `react`
  - 默认对话 pattern
  - 没有 LLM 时可回退到 echo / `/tool` 模式
  - 有 LLM 时要求模型输出结构化 JSON action
- `plan_execute`
  - 先规划再执行
  - 没有 LLM 时基本没有意义
- `reflexion`
  - 会对最近 tool 结果做反思，并可能重试

通用 config：

- `max_steps`
- `step_timeout_ms`

`react` 额外支持：

- `tool_prefix`
- `echo_prefix`

## LLM

`llm` 是可选字段。不配时，所选 pattern 必须自己处理没有 `llm_client` 的情况。

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

支持的 provider：

- `mock`
- `openai_compatible`
- `anthropic`

校验规则：

- `provider` 必须是上面三种之一
- `openai_compatible` 必须提供 `api_base`
- `timeout_ms` 必须是正整数
- `max_tokens` 如果提供，必须是正整数
- 未知附加字段会保留在 `LLMOptions.extra`

factory 使用的默认值：

- `mock`
  - 不需要网络依赖
- `openai_compatible`
  - 默认 model：`gpt-4o-mini`
  - 默认 key env：`OPENAI_API_KEY`
- `anthropic`
  - 默认 API base：`https://api.anthropic.com`
  - 默认 model：`claude-3-haiku-20240307`
  - 默认 key env：`ANTHROPIC_API_KEY`

## Tools

单个 tool 的结构：

```json
{
  "id": "search",
  "type": "builtin_search",
  "enabled": true,
  "config": {}
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 无 | pattern 调用它时使用的 id |
| `type` / `impl` | string | 条件必填 | 无 | 至少要有一个 |
| `enabled` | boolean | 否 | `true` | `false` 时不会被加载 |
| `config` | object | 否 | `{}` | plugin 自定义配置 |

当前 builtin tool ids：

- Search：`builtin_search`
- Files：`read_file`、`write_file`、`list_files`、`delete_file`
- Text：`grep_files`、`ripgrep`、`json_parse`、`text_transform`
- HTTP / network：`http_request`、`url_parse`、`url_build`、`query_param`、`host_lookup`
- System：`execute_command`、`get_env`、`set_env`
- Time：`current_time`、`date_parse`、`date_diff`
- Random：`random_int`、`random_choice`、`random_string`、`uuid`
- Math：`calc`、`percentage`、`min_max`
- MCP bridge：`mcp`

## Agent 级执行 Seam

这三类配置都写在 agent 下面，不是顶层 App 级组件。

### `tool_executor`

```json
{
  "tool_executor": {
    "type": "safe",
    "config": {"default_timeout_ms": 2000}
  }
}
```

用途：

- 负责 tool 的实际执行方式
- 做参数校验、timeout、stream passthrough、错误规范化

当前 builtin：

- `safe`

### `execution_policy`

```json
{
  "execution_policy": {
    "type": "filesystem",
    "config": {
      "read_roots": ["workspace"],
      "write_roots": ["workspace"],
      "allow_tools": ["read_file", "write_file"]
    }
  }
}
```

用途：

- 在 tool 执行前决定 allow / deny
- 适合文件边界、工具白名单、工具黑名单这类策略

当前 builtin：

- `filesystem`

### `context_assembler`

```json
{
  "context_assembler": {
    "type": "summarizing",
    "config": {
      "max_messages": 10,
      "max_artifacts": 5,
      "include_summary_message": true
    }
  }
}
```

用途：

- 组装当前 run 的 transcript / session artifacts
- 控制 working set，而不是 memory 存储本身

当前 builtin：

- `summarizing`

### 兼容说明

当前 builtin runtime 仍兼容旧的 `runtime.config.tool_executor` / `execution_policy` / `context_assembler` 写法，但文档主路径是 agent 级：

- `agents[].tool_executor`
- `agents[].execution_policy`
- `agents[].context_assembler`

## Agent 级 Runtime 参数

这个块必须写在每个 agent 下面：

```json
{
  "runtime": {
    "max_steps": 16,
    "step_timeout_ms": 30000,
    "session_queue_size": 1000,
    "event_queue_size": 2000
  }
}
```

默认值：

- `max_steps`：`16`
- `step_timeout_ms`：`30000`
- `session_queue_size`：`1000`
- `event_queue_size`：`2000`

四个值都必须是正整数。

## 完整示例

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
      "memory": {"type": "window_buffer", "config": {"window_size": 20}, "on_error": "continue"},
      "pattern": {"type": "react", "config": {"max_steps": 8}},
      "llm": {"provider": "mock"},
      "tool_executor": {"type": "safe"},
      "execution_policy": {"type": "filesystem", "config": {"read_roots": ["workspace"], "allow_tools": ["read_file"]}},
      "context_assembler": {"type": "summarizing", "config": {"max_messages": 10, "max_artifacts": 5}},
      "tools": [
        {"id": "search", "type": "builtin_search"},
        {"id": "calc", "type": "calc"}
      ],
      "runtime": {"max_steps": 16, "step_timeout_ms": 30000, "session_queue_size": 1000, "event_queue_size": 2000}
    }
  ]
}
```

## 相关文档

- [开发指南](developer-guide.md)
- [插件开发](plugin-development.md)
- [API 参考](api-reference.md)

# 配置参考

本文档详细介绍 `agent.json` 的所有配置选项。

## 顶层配置

```json
{
  "version": "1.0",
  "runtime": { ... },
  "session": { ... },
  "events": { ... },
  "agents": [ ... ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | 是 | 配置版本，当前为 `1.0` |
| `runtime` | object | 否 | 运行时配置 |
| `session` | object | 否 | 会话管理器配置 |
| `events` | object | 否 | 事件总线配置 |
| `agents` | array | 是 | Agent 列表 |

---

## Runtime 配置

```json
{
  "runtime": {
    "type": "default",
    "config": {
      "max_steps": 16,
      "step_timeout_ms": 30000
    }
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | "default" | 运行时类型 |
| `config.max_steps` | int | 16 | 最大执行步数 |
| `config.step_timeout_ms` | int | 30000 | 单步超时(毫秒) |

---

## Session 配置

```json
{
  "session": {
    "type": "in_memory",
    "config": {}
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | "in_memory" | 会话管理器类型 |

---

## Events 配置

```json
{
  "events": {
    "type": "async",
    "config": {}
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | "async" | 事件总线类型 |

---

## Agent 配置

```json
{
  "id": "assistant",
  "name": "My Agent",
  "memory": { ... },
  "pattern": { ... },
  "llm": { ... },
  "tools": [ ... ],
  "runtime": { ... }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | Agent 唯一标识 |
| `name` | string | 是 | Agent 显示名称 |
| `memory` | object | 是 | 记忆配置 |
| `pattern` | object | 是 | 推理模式配置 |
| `llm` | object | 否 | LLM 配置 |
| `tools` | array | 否 | 工具列表 |
| `runtime` | object | 否 | 运行时覆盖配置 |

---

## Memory 配置

### 内置类型

| 类型 | 说明 |
|------|------|
| `buffer` | 简单缓冲，保存所有历史 |
| `window_buffer` | 滑动窗口，保留最近 N 条 |
| `mem0` | 向量语义记忆 |

### 配置示例

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

| 字段 | 说明 |
|------|------|
| `type` | 内存类型 (`buffer`/`window_buffer`/`mem0`) |
| `config.window_size` | 窗口大小 |
| `config.max_items` | 最大保存条数 |
| `config.state_key` | 状态存储键名 |
| `config.view_key` | 视图键名 |
| `on_error` | 错误处理 (`continue`/`fail`) |

### 自定义 Memory

```json
{
  "memory": {
    "impl": "mypackage.MyMemory",
    "config": {
      "storage_path": "./memory"
    }
  }
}
```

---

## Pattern 配置

### 内置类型

| 类型 | 说明 |
|------|------|
| `react` | ReAct 推理循环 |
| `plan_execute` | 先计划后执行 |
| `reflexion` | 带反思的推理 |

### 配置示例

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

| 字段 | 说明 |
|------|------|
| `type` | 推理模式类型 |
| `config.max_steps` | 最大步数 |
| `config.step_timeout_ms` | 单步超时 |

---

## LLM 配置

### Provider

| Provider | 说明 |
|-----------|------|
| `mock` | 测试用 Mock LLM |
| `openai_compatible` | OpenAI 兼容 API |
| `anthropic` | Anthropic 兼容 API |

### Mock

```json
{
  "llm": {
    "provider": "mock"
  }
}
```

### OpenAI 兼容

```json
{
  "llm": {
    "provider": "openai_compatible",
    "model": "gpt-4o-mini",
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout_ms": 60000
  }
}
```

### Anthropic

```json
{
  "llm": {
    "provider": "anthropic",
    "model": "claude-3-haiku-20240307",
    "api_key_env": "ANTHROPIC_API_KEY",
    "temperature": 0.7,
    "max_tokens": 1024
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | LLM 提供商 |
| `model` | string | 模型名称 |
| `api_base` | string | API 端点 (openai_compatible 需要) |
| `api_key_env` | string | 环境变量名 |
| `temperature` | float | 采样温度 |
| `max_tokens` | int | 最大 token 数 |
| `timeout_ms` | int | 超时时间(毫秒) |

---

## Tools 配置

### 内置工具

| 类型 | 说明 |
|------|------|
| `builtin_search` | 搜索 |
| `read_file` | 读取文件 |
| `write_file` | 写入文件 |
| `list_files` | 列出文件 |
| `delete_file` | 删除文件 |
| `grep_files` | 文件搜索 |
| `http_request` | HTTP 请求 |
| `calc` | 计算器 |
| `mcp` | MCP 客户端 |

### 配置示例

```json
{
  "tools": [
    {
      "id": "search",
      "type": "builtin_search",
      "enabled": true,
      "config": {}
    },
    {
      "id": "weather",
      "impl": "mypackage.WeatherTool",
      "config": {
        "api_key": "xxx"
      }
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 工具唯一标识 |
| `type` | string | 内置工具类型 |
| `impl` | string | 自定义实现路径 |
| `enabled` | boolean | 是否启用 |
| `config` | object | 工具配置 |

---

## 完整示例

```json
{
  "version": "1.0",
  "runtime": {
    "type": "default",
    "config": {
      "max_steps": 16,
      "step_timeout_ms": 30000
    }
  },
  "session": {
    "type": "in_memory"
  },
  "events": {
    "type": "async"
  },
  "agents": [
    {
      "id": "assistant",
      "name": "My Agent",
      "memory": {
        "type": "window_buffer",
        "config": {
          "window_size": 20
        },
        "on_error": "continue"
      },
      "pattern": {
        "type": "react",
        "config": {
          "max_steps": 16,
          "step_timeout_ms": 30000
        }
      },
      "llm": {
        "provider": "openai_compatible",
        "model": "gpt-4o-mini",
        "api_base": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.7
      },
      "tools": [
        {
          "id": "search",
          "type": "builtin_search",
          "enabled": true
        }
      ]
    }
  ]
}
```


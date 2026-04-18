# 可观测性与日志

OpenAgents SDK 在 `openagents.observability` 模块中内置了结构化日志系统，与 `openagents.*` logger 命名空间绑定。日志系统支持：

- 全局级别控制与按 logger 名称精细覆盖
- Rich 富文本渲染（需要 `[rich]` extra）
- 运行时数据脱敏（API key、token、password 等）
- 前缀白名单/黑名单过滤
- 环境变量驱动配置，无需修改代码

如需观测运行时事件（tool 调用、LLM 调用、run 生命周期），请参阅本页末尾的 [Event Bus 可观测性](#event-bus-可观测性) 一节。

---

## LoggingConfig 字段参考

`LoggingConfig` 是一个 Pydantic 模型，所有字段均可通过配置文件或环境变量设置。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_configure` | `bool` | `false` | 若为 `true`，`Runtime.__init__` 时自动调用 `configure()` |
| `level` | `str` | `"INFO"` | 根 logger 级别（`CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG`/`NOTSET`） |
| `per_logger_levels` | `dict[str, str]` | `{}` | 按 logger 名称覆盖级别，仅对 `openagents.*` 命名空间有效 |
| `pretty` | `bool` | `false` | 启用 Rich 富文本渲染（需要 `[rich]` extra） |
| `stream` | `"stdout"` \| `"stderr"` | `"stderr"` | 日志输出流 |
| `include_prefixes` | `list[str]` \| `null` | `null` | Logger 白名单；`null` 表示允许全部 |
| `exclude_prefixes` | `list[str]` | `[]` | Logger 黑名单；匹配前缀的 logger 消息将被过滤 |
| `redact_keys` | `list[str]` | `["api_key", "authorization", "token", "secret", "password"]` | 脱敏字段名列表（大小写不敏感） |
| `max_value_length` | `int` | `500` | 日志输出中字符串值的最大字符数，超出部分被截断 |
| `show_time` | `bool` | `true` | Rich 模式下显示时间列 |
| `show_path` | `bool` | `false` | Rich 模式下显示代码路径列 |

---

## 启用方式

### 方式 1：配置文件中的 `auto_configure`

在 `agent.json`（或其他配置文件）中设置 `logging` 块，并将 `auto_configure` 设为 `true`，Runtime 初始化时会自动调用 `configure()`：

```json
{
  "logging": {
    "auto_configure": true,
    "level": "DEBUG",
    "pretty": true,
    "stream": "stderr",
    "show_time": true,
    "show_path": false
  }
}
```

### 方式 2：代码调用

适合需要程序化控制日志配置的场景：

```python
from openagents.observability.logging import configure
from openagents.observability.config import LoggingConfig

configure(LoggingConfig(
    level="DEBUG",
    pretty=True,
    per_logger_levels={
        "openagents.llm": "DEBUG",
        "openagents.plugins": "WARNING",
    },
))
```

也可以直接从环境变量构建配置：

```python
from openagents.observability.logging import configure_from_env

configure_from_env()  # 读取所有 OPENAGENTS_LOG_* 环境变量
```

### 方式 3：纯环境变量

无需修改任何代码，只需设置环境变量并在配置文件或代码中启用 `auto_configure`：

```bash
export OPENAGENTS_LOG_LEVEL=DEBUG
export OPENAGENTS_LOG_PRETTY=true
export OPENAGENTS_LOG_AUTOCONFIGURE=true
```

---

## 环境变量完整参考

所有环境变量均可与配置文件字段混合使用：环境变量优先级高于配置文件（通过 `merge_env_overrides()` 合并）。

| 环境变量 | 对应字段 | 类型 | 示例值 |
|---------|---------|------|--------|
| `OPENAGENTS_LOG_AUTOCONFIGURE` | `auto_configure` | 布尔 | `true` |
| `OPENAGENTS_LOG_LEVEL` | `level` | 字符串 | `DEBUG` |
| `OPENAGENTS_LOG_LEVELS` | `per_logger_levels` | 逗号分隔键值对 | `openagents.llm=DEBUG,openagents.plugins=WARNING` |
| `OPENAGENTS_LOG_PRETTY` | `pretty` | 布尔 | `true` |
| `OPENAGENTS_LOG_STREAM` | `stream` | 字符串 | `stdout` |
| `OPENAGENTS_LOG_INCLUDE` | `include_prefixes` | 逗号分隔列表 | `openagents.runtime,openagents.llm` |
| `OPENAGENTS_LOG_EXCLUDE` | `exclude_prefixes` | 逗号分隔列表 | `openagents.observability` |
| `OPENAGENTS_LOG_REDACT` | `redact_keys` | 逗号分隔列表 | `api_key,secret,token` |
| `OPENAGENTS_LOG_MAX_VALUE_LENGTH` | `max_value_length` | 整数 | `200` |

布尔类型接受 `1`、`true`、`yes`、`on`（大小写不敏感）为真值，其余值均为假。

---

## Rich 富文本渲染

Rich 模式提供带颜色高亮、时间列、代码路径列的终端日志输出，适合本地开发和调试。

### 安装

```bash
uv sync --extra rich
# 或者
pip install "io-openagent-sdk[rich]"
```

### 启用

```json
{
  "logging": {
    "auto_configure": true,
    "pretty": true,
    "show_time": true,
    "show_path": false
  }
}
```

或通过环境变量：

```bash
export OPENAGENTS_LOG_PRETTY=true
```

!!! warning "缺少 rich 时会报错"
    若 `pretty=true` 但 `rich` 未安装，`configure()` 会立即抛出 `RichNotInstalledError`，提示安装命令。这是有意为之——显式报错比静默回退为纯文本更容易排查问题。

### Rich 模式专属字段

| 字段 | 说明 |
|------|------|
| `show_time` | 在每行左侧显示时间戳（默认 `true`） |
| `show_path` | 在每行右侧显示代码文件名和行号（默认 `false`，会使输出变宽） |

---

## 脱敏机制

`RedactFilter` 在日志输出时对匹配 `redact_keys` 的 key 进行遮蔽，原始数据对象不受影响。

**默认脱敏字段**（大小写不敏感）：`api_key`、`authorization`、`token`、`secret`、`password`

**脱敏示例**：

```python
import logging
logger = logging.getLogger("openagents.mymodule")
logger.info("Calling API", extra={"api_key": "sk-abc123", "model": "claude-3"})
# 输出：api_key=*** model=claude-3
```

**值截断**：超过 `max_value_length`（默认 500）字符的字符串值在日志中会被截断，但原始数据不变。

**自定义脱敏字段**：

```json
{
  "logging": {
    "redact_keys": ["api_key", "authorization", "token", "secret", "password", "x_api_secret"]
  }
}
```

---

## 前缀过滤

通过 `include_prefixes` 和 `exclude_prefixes` 可以精确控制哪些 logger 的消息会出现在输出中：

```json
{
  "logging": {
    "level": "DEBUG",
    "include_prefixes": ["openagents.runtime", "openagents.llm"],
    "exclude_prefixes": ["openagents.observability"]
  }
}
```

- `include_prefixes` 为 `null`（默认）时，允许所有 `openagents.*` 下的消息通过。
- `exclude_prefixes` 优先级高于 `include_prefixes`：若一个 logger 名同时匹配两者，黑名单胜出。

---

## 按 Logger 精细控制级别

通过 `per_logger_levels` 可以让某个 logger 比根级别更详细或更安静：

```json
{
  "logging": {
    "level": "INFO",
    "per_logger_levels": {
      "openagents.llm": "DEBUG",
      "openagents.plugins.loader": "WARNING"
    }
  }
}
```

!!! note "仅作用于 openagents.* 命名空间"
    `per_logger_levels` 中填写 `openagents.*` 以外的 logger 名会被忽略，并打印一条警告。SDK 从不修改第三方 logger 或根 logger。

---

## configure() 的幂等性与重载

`configure()` 是幂等的：可安全地从 `Runtime.reload()` 中重复调用。每次调用前都会先执行 `reset_logging()`，移除所有由 SDK 安装的 handler，然后重新安装新配置的 handler。

`reset_logging()` 会：

1. 移除所有带有 `_openagents_installed=True` 标记的 handler
2. 将 `openagents` logger 的 `propagate` 恢复为 `True`
3. 清除根级别回到 `NOTSET`
4. 重置所有由 `per_logger_levels` 设置过的子 logger 级别

**SDK 作为库使用时**：若应用不调用 `configure()`，`openagents.*` logger 下的所有消息会静默（`propagate=True` 且无 handler）。应用自己的 logging 配置完全不受 SDK 影响。

---

## Event Bus 可观测性

除结构化日志外，运行时事件（tool 调用、LLM 调用、run 生命周期等）通过 Event Bus 传播。以下内置 Event Bus 实现支持可观测性集成：

| type 键 | 说明 |
|---------|------|
| `file_logging` | 将运行时事件以 NDJSON 格式追加写入文件，适合离线分析 |
| `otel_bridge` | 将运行时事件映射为 OpenTelemetry span，集成 Jaeger/Tempo 等后端 |
| `rich_console` | 将运行时事件以富文本格式打印到终端（需要 `[rich]` extra） |

Event Bus 在配置文件的顶层 `events` 字段配置，参见[配置参考](configuration.md)。

### 示例：file_logging

```json
{
  "events": {
    "type": "file_logging",
    "config": {
      "path": "logs/runtime_events.ndjson"
    }
  }
}
```

### 示例：rich_console（开发调试用）

```json
{
  "events": {
    "type": "rich_console",
    "config": {
      "show_payload": true
    }
  }
}
```

---

## 相关文档

- [配置参考](configuration.md) — `logging` 块和 `events` 块的完整 JSON schema
- [插件开发指南](plugin-development.md) — 自定义 Event Bus 插件
- [Seams 与扩展点](seams-and-extension-points.md) — `events` seam 的决策树

# CLI 参考

OpenAgents SDK 附带一个命令行工具 `openagents`，提供配置校验、Schema 导出和插件枚举等实用功能。所有子命令均可通过以下两种方式调用：

```bash
openagents <子命令> [选项]
# 或
python -m openagents <子命令> [选项]
```

!!! note "调用方式"
    两种调用方式完全等价。在 `uv` 管理的项目中，推荐使用 `uv run openagents <子命令>` 以确保使用项目虚拟环境中的依赖。

---

## 子命令一览

| 子命令 | 说明 |
|--------|------|
| [`schema`](#schema) | 导出 AppConfig 或各插件的 JSON/YAML Schema |
| [`validate`](#validate) | 加载并校验 `agent.json`，不实际运行 agent |
| [`list-plugins`](#list-plugins) | 列出所有已注册的插件（按 seam 分组） |

---

## `openagents schema` {#schema}

导出整个 `AppConfig` 的 JSON Schema，或者某个插件 / 某个 seam 的配置 Schema。这对于了解配置文件结构、生成文档或在 IDE 中配置 JSON Schema 校验非常有用。

### 用法

```bash
openagents schema [--plugin NAME] [--seam SEAM] [--format {json,yaml}] [--out FILE]
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--plugin NAME` | 字符串 | — | 按名称导出单个插件的配置 Schema。若同时指定 `--seam`，则在该 seam 范围内查找。 |
| `--seam SEAM` | 字符串 | — | 限定在某个 seam 范围内（例如 `context_assembler`）。单独使用时导出该 seam 下所有插件的 Schema。 |
| `--format` | `json` \| `yaml` | `json` | 输出格式。`yaml` 需要安装 `[yaml]` 额外依赖（见下方说明）。 |
| `--out FILE` | 文件路径 | — | 将输出写入文件而非 stdout。 |

### 行为说明

- **无参数**：输出完整的 `AppConfig` JSON Schema（包含所有顶级字段）。
- **仅 `--seam`**：输出该 seam 下所有内置插件的配置 Schema，以 `{ seam: { plugin_name: schema } }` 格式组织。
- **`--plugin`**（可选搭配 `--seam`）：输出指定插件的配置 Schema。若插件未声明 `Config` 内部类，则报错退出（exit code 2）。
- **`--out`**：写入文件时自动补全末尾换行符。

### 示例

```bash
# 导出完整 AppConfig Schema（JSON 格式，输出到 stdout）
openagents schema

# 导出 context_assembler seam 下所有插件的 Schema
openagents schema --seam context_assembler

# 导出名为 head_tail 的插件的配置 Schema
openagents schema --plugin head_tail

# 在 context_assembler seam 范围内查找 head_tail 插件的 Schema
openagents schema --seam context_assembler --plugin head_tail

# 导出 YAML 格式并写入文件
openagents schema --format yaml --out schema.yaml

# 导出完整 Schema 并写入 JSON 文件
openagents schema --out appconfig-schema.json
```

### 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `2` | 插件未找到，或插件未声明配置 Schema，或 YAML 依赖未安装 |

---

## `openagents validate` {#validate}

加载并校验 `agent.json` 配置文件，但不实际启动 agent 或进行任何网络调用。适合在 CI 流水线中用于配置文件的预检查。

### 用法

```bash
openagents validate <path> [--strict] [--show-resolved]
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | 位置参数（必填） | — | 要校验的 `agent.json` 文件路径。 |
| `--strict` | 开关 | `false` | 严格模式：额外验证每个 `type` 字段均能解析到已注册的内置插件。涉及 seam：`memory`、`pattern`、`tool_executor`、`context_assembler`。 |
| `--show-resolved` | 开关 | `false` | 校验成功后，将完整解析后的 `AppConfig`（JSON 格式）打印到 stdout。 |

### 行为说明

命令首先通过 `load_config(path)` 加载配置文件，捕获以下错误类型并以 exit code 2 退出：

- `ConfigLoadError`：文件不存在或无法解析
- `ConfigValidationError`：Pydantic 校验失败（字段类型错误、缺少必填字段等）
- `ConfigError`：其他配置错误

校验成功后，输出摘要信息：

```
OK: agent.json is valid (2 agents, 3 seams configured)
```

启用 `--strict` 时，会进一步检查每个 agent 中 `memory`、`pattern`、`tool_executor`、`context_assembler` 的 `type` 值是否能在内置注册表中找到对应实现。对于使用 `impl`（Python 点路径）的自定义插件，此检查会跳过。

!!! warning "装饰器注册插件"
    `--strict` 只检查**内置注册表**（`builtin` source）中的插件。通过 `@context_assembler` 等装饰器注册的自定义插件需要模块先被导入，才能出现在注册表中。若验证脚本中未导入对应模块，严格模式可能误报 unresolved。

### 示例

```bash
# 基本校验
openagents validate agent.json

# 严格模式校验（验证 type 字段均可解析）
openagents validate agent.json --strict

# 校验并打印完整解析后的配置
openagents validate agent.json --show-resolved

# 在 CI 中使用（利用退出码）
openagents validate agent.json --strict && echo "Config OK"
```

### 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 校验通过 |
| `2` | 文件无法加载、Schema 校验失败，或严格模式下存在无法解析的 `type` |

---

## `openagents list-plugins` {#list-plugins}

列出所有已注册的插件，按 seam 分组展示。同时显示来源（内置 vs 装饰器注册）、实现路径以及是否声明了配置 Schema。

### 用法

```bash
openagents list-plugins [--seam SEAM] [--source {builtin,decorator,all}] [--format {table,json}]
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--seam SEAM` | 字符串 | — | 只列出指定 seam 的插件。可用值：`memory`、`pattern`、`tool`、`tool_executor`、`context_assembler`、`runtime`、`session`、`events`。 |
| `--source` | `builtin` \| `decorator` \| `all` | `all` | 按来源过滤。`builtin` = 内置注册表；`decorator` = 通过装饰器（`@tool`、`@memory` 等）注册的插件；`all` = 两者都包含。 |
| `--format` | `table` \| `json` | `table` | 输出格式。`json` 格式输出包含完整字段的数组，适合脚本消费。 |

### 输出字段

| 字段 | 说明 |
|------|------|
| `seam` | 插件所属的 seam 名称 |
| `name` | 插件的注册名（在配置文件 `type` 字段中使用） |
| `source` | `builtin`（内置）或 `decorator`（装饰器注册） |
| `has_config_schema` | 插件是否声明了 `Config` 内部类（即是否支持配置 Schema 导出） |

`json` 格式额外包含 `impl_path` 字段，为插件类的完整 Python 模块路径（`module.ClassName`）。

### 示例

```bash
# 列出所有已注册的插件（表格格式）
openagents list-plugins

# 只列出 context_assembler seam 的插件
openagents list-plugins --seam context_assembler

# 只列出内置插件
openagents list-plugins --source builtin

# 以 JSON 格式输出（适合脚本处理）
openagents list-plugins --format json

# 组合使用：只看 memory seam 的内置插件，JSON 格式
openagents list-plugins --seam memory --source builtin --format json
```

### 表格输出示例

```
seam              name                source    has_config_schema
----------------  ------------------  --------  -----------------
context_assembler head_tail           builtin   True
memory            noop                builtin   False
pattern           react               builtin   True
tool_executor     default             builtin   False
```

### 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功（即使结果为空） |

---

## YAML 输出依赖 {#yaml-extra}

`openagents schema --format yaml` 需要 `PyYAML`，它包含在 `[yaml]` 可选依赖组中：

=== "pip"

    ```bash
    pip install "io-openagent-sdk[yaml]"
    ```

=== "uv"

    ```bash
    uv add "io-openagent-sdk[yaml]"
    ```

若未安装 `PyYAML` 而使用 `--format yaml`，命令会打印以下提示并以 exit code 2 退出：

```
yaml output requires PyYAML; install with: pip install io-openagent-sdk[yaml]
```

---

## 相关文档

- [配置参考](configuration.md) — `agent.json` 的完整字段说明
- [插件开发指南](plugin-development.md) — 如何编写并注册自定义插件
- [Seam 与扩展点](seams-and-extension-points.md) — 各 seam 的职责与决策树
- [API 参考](api-reference.md) — `Runtime`、`RunRequest`、`RunResult` 等核心类型

# OpenAgents SDK

**OpenAgents SDK**（v0.3.0）是一个面向 Python 的 **config-as-code 单智能体运行时内核**。它提供了一个极简、可组合的基础层，让开发者通过 JSON 配置文件声明 agent，并通过插件 seam 注入记忆、工具、执行策略、上下文组装等所有产品语义——而不是把产品逻辑硬编码进内核。

SDK 刻意**不**拥有多智能体团队、审批 UX、邮箱或产品工作流——这些全部由上层应用通过 seam 协议扩展实现。

---

## 安装

=== "推荐（uv）"

    ```bash
    uv sync
    ```

=== "pip"

    ```bash
    pip install io-openagent-sdk
    ```

=== "含可选依赖"

    ```bash
    # YAML 输出支持
    pip install "io-openagent-sdk[yaml]"
    ```

---

## 快速开始

```python
from openagents import Runtime

# 从 JSON 配置文件加载 runtime
runtime = Runtime.from_config("agent.json")

# 同步运行（适合脚本和测试）
result = runtime.run_sync(
    agent_id="assistant",
    session_id="s1",
    input_text="Hello",
)
print(result)
```

!!! tip "agent.json 最小示例"
    ```json
    {
      "agents": [
        {
          "id": "assistant",
          "llm": {
            "provider": "anthropic",
            "model": "claude-opus-4-5"
          }
        }
      ]
    }
    ```

---

## 三层架构

OpenAgents SDK 以三层分层设计为核心，保持内核稳定、扩展点清晰、产品语义完全下沉到应用层。

| 层次 | 主要类型 / 接口 | 特征 |
|------|----------------|------|
| **Kernel Protocol**（内核协议） | `RunRequest`、`RunResult`、`RunContext[DepsT]`、`ToolExecutionRequest`、`ContextAssemblyResult`、`SessionArtifact`、`StopReason` | 稳定数据类，很少改变 |
| **SDK Seams**（8 个扩展点） | `memory`、`pattern`、`tool`、`tool_executor`、`context_assembler`、`runtime`、`session`、`events`、`skills` | 运行时插件扩展点，每个 seam 都有内置默认实现 |
| **App-Defined Protocol**（应用层协议） | task envelopes、permission state、coding plans、artifact taxonomies、planner state | 产品语义，通过 `RunContext.state`/`.scratch`/`.assembly_metadata`、`RunRequest.context_hints`、`RunArtifact.metadata` 在应用层实现 |

!!! warning "核心原则"
    **不要把产品语义推进内核。** 新增一个 seam 的前提：跨应用复用、影响运行时行为、需要独立选择器和生命周期，且有内置默认实现和测试。否则，保留在应用层。

---

## 快速导航

<div class="grid cards" markdown>

- **开发者指南**

    ---

    环境配置、测试命令、完整开发流程

    [:octicons-arrow-right-24: developer-guide.md](getting-started/developer-guide.md)

- **Seam 与扩展点**

    ---

    各 seam 的职责、决策树、如何选择正确的扩展点

    [:octicons-arrow-right-24: seams-and-extension-points.md](architecture/seams-and-extension-points.md)

- **配置参考**

    ---

    `agent.json` 的完整 schema、所有字段说明

    [:octicons-arrow-right-24: configuration.md](configuration/configuration.md)

- **插件开发**

    ---

    如何编写自定义插件，注册到 seam，测试和发布

    [:octicons-arrow-right-24: plugin-development.md](plugins/plugin-development.md)

- **API 参考**

    ---

    `Runtime`、`RunRequest`、`RunResult`、`RunContext` 等核心类型的完整 API

    [:octicons-arrow-right-24: api-reference.md](reference/api-reference.md)

- **CLI 参考**

    ---

    `openagents schema`、`openagents validate`、`openagents list-plugins` 命令详解

    [:octicons-arrow-right-24: cli-reference.md](cli/cli-reference.md)

- **示例**

    ---

    quickstart 与 production_coding_agent 示例的运行说明

    [:octicons-arrow-right-24: examples.md](getting-started/examples.md)

- **迁移指南**

    ---

    从 0.2.x 升级到 0.3.x 的变更说明与迁移步骤

    [:octicons-arrow-right-24: migration-0.2-to-0.3.md](migration/migration-0.2-to-0.3.md)

</div>

---

## 快速判断：我该用哪个 seam？

| 需求 | 选择 |
|------|------|
| 在对话中注入和持久化记忆 | `memory` seam |
| 控制 LLM 调用主循环（ReAct、few-shot 等） | `pattern` seam |
| 注册和执行工具（函数调用） | `tool` + `tool_executor` seam |
| 定制上下文窗口的组装方式 | `context_assembler` seam |
| 自定义会话存储或锁 | `session` seam |
| 拦截或发布运行时事件 | `events` seam |
| 打包可复用的 agent 能力 | `skills` seam |
| 产品任务信封、权限模型、规划状态 | **不用 seam** — 放在 `RunContext.state` 里 |

!!! note "详细决策树"
    参见 [seams-and-extension-points.md](architecture/seams-and-extension-points.md) 获取完整的决策树和各 seam 的生命周期说明。

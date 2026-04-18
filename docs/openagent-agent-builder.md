# OpenAgent Agent Builder

`openagent-agent-builder` 是一个 **app-layer skill**，坐在 OpenAgents SDK 之上，通过顶层 `skills` 组件（`LocalSkillsManager`）被发现和执行，不是 runtime 内的 seam。

## 安装与配置

Skill 位于仓库根目录的 `skills/openagent-agent-builder/`，无需额外安装。在你的 `agent.json` 中加入以下 `skills` 配置即可启用：

```json
{
  "skills": {
    "type": "local",
    "config": {
      "search_paths": ["skills"],
      "enabled": ["openagent-agent-builder"]
    }
  }
}
```

`search_paths` 中填入相对于配置文件的路径，`LocalSkillsManager` 会自动发现 `openagent-agent-builder` 目录并注册 skill。

!!! tip
    如果在仓库根目录运行，`search_paths: ["skills"]` 直接指向 `skills/openagent-agent-builder/`。
    如果在自己的项目中引用，请调整为对应相对路径或绝对路径。

它的目标是帮助主 agent 或开发者一次拿到：

- 一个可运行的 single-agent `sdk_config`（完整的 `AppConfig` 负载）
- 一次真实的 smoke run 结果（默认用 mock LLM，零依赖）
- 这个 agent 放进 team 里的接入建议

## 它负责什么

- build 一个 `subagent`
- build 一个 `agent-team` 里的单角色 agent（`team-role`）
- 推导 `memory / pattern / llm / tools / runtime` 四件套
- 根据 `workspace_root` 自动注入 `filesystem` 执行策略
- 输出 handoff contract 和 integration hints
- 用 `Runtime.from_dict(...).run_detailed(...)` 做一次 smoke run

## 它不负责什么

- 整个 team 的 scheduler、mailbox、approval UX
- background jobs、cancel/resume、跨 session 的持久化
- 全局 retry/cancel/resume 策略
- 跨 agent 生命周期管理
- 多 agent 之间的 handoff 执行（它只告诉你 contract 长啥样）

## Core I/O

输入是 `OpenAgentSkillInput`：

- `task_goal`（必填）
- `agent_role`（必填，取值：`planner` | `coder` | `reviewer` | `researcher`）
- `agent_mode`（必填，取值：`subagent` | `team-role`）
- `workspace_root`
- `available_tools`
- `constraints`（`max_steps`、`step_timeout_ms` 等会合并进 agent 的 `runtime`；`read_only: true` 会抑制 `write_roots`）
- `handoff_expectation`（`{input, output, artifact_format}`）
- `overrides`（按 seam 维度的深合并；`tools` 为 list 时整体替换）
- `smoke_run`（默认 `true`）

输出是 `OpenAgentSkillOutput`：

- `agent_spec`
- `agent_prompt_summary`
- `design_rationale`
- `handoff_contract`
- `integration_hints`
- `smoke_result`（`status` ∈ `"passed" | "failed" | "skipped"`）
- `next_actions`

## Agent Spec Shape

`agent_spec` 直接贴合 `openagents.config.schema.AppConfig`（当前 `version = "1.0"`），不额外发明 DSL。字段包含：

- `agent_key`
- `purpose`
- `sdk_config`：完整的 `AppConfig`，含顶层 `runtime / session / events / skills` 选择器 + `agents[0]`
- `run_request_template`：可以直接喂给 `RunRequest(...)` 的字段骨架

因此可以直接：

- `runtime = Runtime.from_dict(spec["agent_spec"]["sdk_config"])`
- `result = await runtime.run_detailed(request=RunRequest(**template_payload))`

## Archetypes

当前支持四个 archetype（见 `skills/openagent-agent-builder/src/openagent_agent_builder/archetypes.py`）：

| 角色 | Pattern | 默认工具 | 备注 |
| --- | --- | --- | --- |
| `planner` | `plan_execute` | search、read_file、list_files | 上游岗；产出 plan |
| `coder` | `react` + `safe` tool_executor | read_file、write_file、list_files、grep_files、ripgrep | 可写；`constraints.read_only=true` 可禁写 |
| `reviewer` | `react` + `safe` tool_executor | read_file、list_files、grep_files、ripgrep、search | 下游岗；只读 |
| `researcher` | `reflexion` + `safe` tool_executor | search、http_request、url_parse、query_param | 上游岗；迭代式取证 |

Archetypes 只是默认模板，不是硬编码的 team 语义。所有 seam 都可以通过 `overrides` 调整。

## LLM 默认走 mock

为了让 smoke run 可以在离线/CI 环境无条件通过，所有 archetype 的 `llm.provider` 默认是 `mock`。真实部署必须通过 `overrides.llm` 切换到 `anthropic` 或 `openai_compatible`（见 `LLMOptions` 校验规则；后者要求 `api_base`）。

## Seam 整合说明（0.3.x）

0.3.x seam-consolidation 之后，agent builder 生成的配置统一使用 `tool_executor: filesystem_aware` 而不是旧的 `execution_policy: filesystem`。所有生成的 `sdk_config` 均与 0.3.x 格式兼容，不需要手动迁移。

!!! warning
    如果你有缓存的旧版 agent builder 输出（0.2.x 格式），请重新运行 builder 或手动将 `execution_policy: filesystem` 替换为 `tool_executor: filesystem_aware`。详见 [migration-0.2-to-0.3.md](migration-0.2-to-0.3.md)。

## Host Adapters

这套能力统一收在 skill 目录里：

- `skills/openagent-agent-builder/`
  - SKILL.md、`references/architecture.md`、`references/examples.md`、`agents/openai.yaml`
- `skills/openagent-agent-builder/src/openagent_agent_builder/`
  - 可执行 core（`normalize → archetypes → render → smoke`）
- `openagent_agent_builder.entrypoint.run_openagent_skill(payload: dict) -> dict`
  - 给顶层 `skills` 组件或 app-owned main-agent tool 调用

Session 开始时，`skills.prepare_session()` 只预热 description；references 和 entrypoint 在需要时再渐进式加载。

## 已知限制

- **不处理多 agent 协作**：builder 只负责 single-agent 配置，不涉及 team scheduler、mailbox 或 approval UX。
- **smoke run 使用 mock LLM**：smoke run 用 `mock` provider，不会因 LLM 调用问题而失败。验证真实 LLM 行为需自行在目标环境运行。
- **`overrides.tools` 是全量替换**：当 `overrides.tools` 是列表时，它会完整替换 archetype 的默认工具列表，而不是追加合并。如果只想新增一个工具，请将 archetype 默认工具也一并写入。
- **不涉及跨 session 持久化**：builder 生成的 `sdk_config` 默认用 `jsonl_file` session，不保证跨 major 版本可读。

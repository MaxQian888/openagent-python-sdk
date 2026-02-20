# Config-as-Code Agent SDK 设计文档

日期：2026-02-20  
状态：已确认（设计阶段）

## 1. 目标与范围

目标是构建一个 **config-as-code** 的 Agent SDK，满足：

- 通过 `agent.json` 声明 Agent 及其插件（`memory` / `pattern` / `tool`）。
- 提供内置 builtin 插件开箱即用。
- 支持开发者自定义 `@memory`、`@pattern`、`tool` 插件并可插拔接入。
- `Runtime` 作为唯一运行入口，负责 session/eventbus 管理与并发调度。
- `memory` 与 `pattern` 交互充分、协议稳定、便于扩展。

不在本阶段处理：

- 分布式调度与跨进程一致性。
- 复杂工作流引擎（DAG/状态机）能力。

## 2. 核心设计决策（已确认）

1. 插件解析采用双轨：
   - `type`：builtin 插件短名。
   - `impl`：自定义 Python import path。
2. `type` 与 `impl` 采用严格互斥：
   - 同时出现 => 启动失败（配置错误）。
   - 都未出现 => 启动失败（配置错误）。
3. 并发语义：
   - 同 `session_id` 串行执行。
   - 不同 `session_id` 并发执行。
4. memory 注入策略：
   - 注入什么、注入多少、何时注入、何时跳过由 memory 插件自主决定。
5. memory 写回策略：
   - 是否写回、何时写回、怎么写回由 memory 插件自主决定。
6. memory 错误策略：
   - 可配置，默认 `continue`（不阻断主流程，记录事件/日志）。
7. 架构方案选择：
   - 采用能力契约驱动（capability-based）方案。

## 3. 为什么要 capability contract

`capability contract` 不是让模型“猜”插件能力，而是让 Runtime 在运行前可预测、可校验、可测试地编排插件。

价值：

- 启动阶段即可校验插件是否满足运行所需能力。
- Runtime 可按能力安全降级（有则调用、无则跳过）。
- 避免大量 `if isinstance(...)` 分支与运行时偶发错误。
- 便于第三方插件生态稳定演进。

开发者体验策略：

- 不要求用户在 `agent.json` 手写 capabilities。
- capability 由插件类声明（或框架探测）并在加载时统一注册。

## 4. 架构分层

### 4.1 Config 层

- 负责配置读取、默认值填充、严格校验（含 `type|impl` 互斥）。
- 仅声明“使用哪些插件”和参数，不承载运行逻辑。

### 4.2 Runtime 层（唯一入口）

- 负责生命周期编排：`session_start`、`before_step`、`after_step`、`session_end`。
- 负责 session 隔离、并发控制、eventbus 事件流。
- 通过 capability 调用插件，不依赖具体插件类型实现细节。
- 仅定义调用时机，不定义 memory 注入/写回的内部策略。

### 4.3 Plugin 层

- memory/pattern/tool 各自实现具体行为。
- 通过统一契约暴露能力给 Runtime。
- 支持 builtin 与第三方自定义插件。

## 5. 运行时序（高层）

1. `runtime.run(agent_id, session_id, input)` 进入。
2. 配置校验 + 插件实例化 + capability 校验。
3. 获取 session 执行锁（同 session 串行）。
4. 构建 `execution_context`。
5. 调用 memory `inject`（若支持）。
6. 进入 pattern 主循环 `react`。
7. pattern 触发 tool 调用时，Runtime 调 `tool.invoke` 并将结果回写 context。
8. pattern 返回 final 后，调用 memory `writeback`（若支持）。
9. 发布完成/错误事件并返回结果，释放 session 锁。

## 6. execution_context 设计原则

`execution_context` 是 pattern 可见的统一门面，至少提供：

- 当前输入、会话状态、步骤状态。
- 工具调用能力（统一入口）。
- memory 可读视图与可写回缓存。
- 事件发布能力（供观测与扩展）。

约束：

- pattern 不直接依赖具体 memory 类实现。
- memory 与 pattern 的耦合通过 context 协议完成，而非类级直接引用。
- memory 的注入策略由 memory 插件内部定义，Runtime 只在生命周期点触发。

## 7. agent.json 字段规范（V1）

示例（概念）：

```json
{
  "version": "1.0",
  "agents": [
    {
      "id": "assistant",
      "name": "demo-agent",
      "memory": { "type": "window_buffer", "config": {}, "on_error": "continue" },
      "pattern": { "type": "react", "config": {} },
      "tools": [
        { "id": "search", "type": "builtin_search", "enabled": true, "config": {} },
        { "id": "weather", "impl": "my_plugins.tools.weather.WeatherTool", "enabled": true, "config": {} }
      ],
      "runtime": {
        "max_steps": 16,
        "step_timeout_ms": 30000,
        "session_queue_size": 1000,
        "event_queue_size": 2000
      }
    }
  ]
}
```

校验要点：

- `type` 与 `impl` 必须二选一。
- `tools[].id` 在同一 agent 下唯一。
- `max_steps`、`step_timeout_ms` 为正整数。
- `on_error` 仅允许枚举值（`continue` / `fail`）。

## 8. 推荐目录结构（确认版）

```text
openagent-py-sdk/
  AGENTS.md
  README.md
  pyproject.toml

  openagents/
    __init__.py

    config/
      schema.py
      loader.py
      validator.py

    interfaces/
      plugin.py
      memory.py
      pattern.py
      tool.py
      capabilities.py
      events.py

    runtime/
      runtime.py
      session_manager.py
      event_bus.py
      execution_context.py
      dispatcher.py
      lifecycle.py

    plugins/
      loader.py
      registry.py
      builtin/
        memory/
          buffer.py
          window_buffer.py
        pattern/
          react.py
        tool/
          common.py

    errors/
      exceptions.py

  tests/
    unit/
    integration/

  examples/
    quickstart/
      agent.json
```

## 9. 扩展性结论

该设计可同时满足：

- 新手：直接使用 builtin（`type`）。
- 高级开发者：通过 `impl` 快速接入自定义插件。
- 平台稳定性：通过 capability + 严格校验维持可预测运行行为。

并且保留了“框架默认编排 + 必要时高度自定义”的扩展空间。

## 10. 后续实施建议（实现前）

1. 先实现配置校验与插件加载器（最小闭环）。
2. 再实现 Runtime + SessionManager + EventBus（并发闭环）。
3. 最后补 builtin memory/pattern/tool 与端到端测试。


# OpenAgents SDK 文档索引

这一套文档基于当前仓库代码整理，覆盖 runtime API、config schema、builtin plugins 和 examples 结构。

## 推荐阅读顺序

第一次接触这个项目，建议按下面顺序读：

1. [配置参考](configuration.md)
2. [开发指南](developer-guide.md)
3. [插件开发](plugin-development.md)
4. [API 参考](api-reference.md)
5. [示例说明](examples.md)

## 心智模型

一个 OpenAgents 应用有两层配置：

- App 级：`runtime`、`session`、`events`
- Agent 级：`memory`、`pattern`、`llm`、`skill`、`tools`、`tool_executor`、`execution_policy`、`context_assembler`、`runtime`

一次 `run` 的主流程是：

1. `Runtime.from_config()` 读取并校验 JSON。
2. 实例化全局 runtime、session manager、event bus。
3. 按 `agent_id` 找到目标 agent。
4. 创建或复用该 session 下的插件实例。
5. context assembler 组装 transcript / artifacts。
6. memory 把上下文注入到 `ExecutionContext.memory_view`。
7. skill / policy / tool executor 参与执行前后阶段。
8. pattern 执行，过程中可调用 tools 和 LLM。
9. memory 把本轮交互写回 session state。
10. event bus 记录完整生命周期事件。

## 各文档负责什么

- [配置参考](configuration.md)
  - JSON 结构、默认值、校验规则、builtin selector 和完整示例
- [开发指南](developer-guide.md)
  - runtime 执行流、hot reload、session 隔离、本地开发和排障
- [插件开发](plugin-development.md)
  - plugin loader 行为、capabilities 要求、自定义 Tool / Memory / Pattern / Runtime / Session / Event Bus 的写法
- [API 参考](api-reference.md)
  - 对外导出、类与 helper 签名、接口契约、事件名、异常类型
- [示例说明](examples.md)
  - 每个 example 目录的用途、入口文件和适用场景

## 快速跳转

- 根 README：[../README.md](../README.md)
- Quickstart config：[../examples/quickstart/agent.json](../examples/quickstart/agent.json)
- 自定义插件示例：[../examples/custom_impl/plugins.py](../examples/custom_impl/plugins.py)
- Runtime composition 示例：[../examples/runtime_composition/agent.json](../examples/runtime_composition/agent.json)
- Runtime 实现：[../openagents/runtime/runtime.py](../openagents/runtime/runtime.py)
- Builtin registry：[../openagents/plugins/registry.py](../openagents/plugins/registry.py)

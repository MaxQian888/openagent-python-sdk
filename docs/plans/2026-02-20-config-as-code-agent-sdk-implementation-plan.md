# Config-as-Code Agent SDK 实施计划

日期：2026-02-20
关联设计：`docs/plans/2026-02-20-config-as-code-agent-sdk-design.md`

## 1. 目标

按已确认设计实现一个可运行的 V1：

- `agent.json` 声明式插件配置（`type|impl` 严格互斥）。
- `runtime` 作为唯一入口。
- capability-based 插件编排。
- session 并发模型：同 session 串行、跨 session 并发。
- memory 注入与写回能力（注入和写回策略由 memory 插件决定）。

## 2. 实施原则

- 使用 `uv` 管理环境与依赖（遵循 `AGENTS.md`）。
- 先做最小闭环，再扩展内置插件与测试矩阵。
- 配置与契约优先，避免后期重构成本。

## 3. 里程碑

### M1: 项目骨架与配置系统

范围：

- 创建目录结构（`config/interfaces/runtime/plugins/errors/tests/examples`）。
- 实现 `agent.json` schema、loader、validator。
- 完成 `type|impl` 互斥校验与错误定义。

交付：

- 配置可被加载并返回结构化对象。
- 非法配置在启动前失败并给出可读错误。

验收标准：

- `type+impl`、两者都空、重复 tool id 等场景均有单测覆盖并通过。

### M2: 契约与插件加载器

范围：

- 定义 `plugin/memory/pattern/tool` 契约。
- 定义 capability 常量与校验规则。
- 实现 builtin registry + dynamic import loader。

交付：

- `type` 能加载内置插件。
- `impl` 能加载自定义插件（import path）。
- 启动时 capability 校验完成。

验收标准：

- 缺失 `pattern.react` 直接失败。
- 插件实例化、能力识别、错误路径均有单测。

### M3: Runtime 核心（并发 + 时序）

范围：

- 实现 `Runtime.run()` 主流程。
- 实现 `SessionManager`（session lock/queue）。
- 实现 `EventBus`（异步发布基础能力）。
- 实现 `ExecutionContext` 统一门面。

交付：

- 单次 run 可完整执行：inject -> react loop -> writeback -> return。
- 同 session 串行、跨 session 并发生效。
- Runtime 仅负责生命周期触发，不实现 memory 注入/写回内部策略。

验收标准：

- 并发测试可稳定复现串行/并行语义。
- 关键生命周期事件可观测。

### M4: Builtin 插件与示例

范围：

- builtin memory：`buffer`, `window_buffer`。
- builtin pattern：`react`（最小可用版本）。
- builtin tool：`common`（最小工具集合）。
- `examples/quickstart/agent.json` 与运行说明。

交付：

- 开箱即用的最小示例可运行。
- 自定义 `impl` 示例可加载。

验收标准：

- quickstart 集成测试通过。

### M5: 稳定性与回归测试

范围：

- 完整 unit + integration 覆盖核心路径。
- 错误策略（memory on_error=continue/fail）验证。
- 基础文档补齐（README 运行与扩展指南）。

交付：

- CI 级别基础测试可稳定通过。
- 具备对外发布 V1 的最小文档。

验收标准：

- 关键链路测试通过率 100%，无阻断级缺陷。

## 4. 任务拆分（按模块）

### config

- `schema.py`: agent/plugin/runtime 配置模型。
- `loader.py`: 文件加载、默认值填充、版本入口。
- `validator.py`: 互斥/唯一性/枚举值/正整数校验。

### interfaces

- `capabilities.py`: capability 命名与分组。
- `plugin.py`: 通用插件协议。
- `memory.py`: inject/writeback/close 协议（策略归属 memory 插件实现）。
- `pattern.py`: react 协议。
- `tool.py`: invoke 协议。
- `events.py`: 标准事件模型。

### plugins

- `registry.py`: builtin 名称映射。
- `loader.py`: `type|impl` 解析与实例化。
- `builtin/*`: V1 内置插件实现。

### runtime

- `runtime.py`: run 主入口与阶段编排。
- `session_manager.py`: session 锁与串行机制。
- `event_bus.py`: 异步事件发布。
- `execution_context.py`: pattern 统一调用门面。
- `dispatcher.py`/`lifecycle.py`: capability 调度与生命周期。

### errors

- `exceptions.py`: `ConfigError/PluginLoadError/CapabilityError/...`

### tests

- `tests/unit`: 配置、加载器、契约、并发语义。
- `tests/integration`: quickstart 端到端、错误分支端到端。

## 5. 测试策略

单元测试重点：

- 配置合法性与错误消息可读性。
- 插件加载成功与失败路径。
- capability 缺失时失败行为。
- session 锁行为（同 session 串行）。

集成测试重点：

- inject/react/writeback 全链路。
- `memory.on_error=continue` 不阻断主流程。
- `memory.on_error=fail` 按预期中断。

## 6. 风险与应对

- 风险：capability 命名漂移导致插件兼容问题。应对：冻结 capability 常量与文档，新增能力仅增不改。
- 风险：execution_context 边界不稳导致 pattern/memory 耦合。应对：context API 最小化，新增字段走版本化。
- 风险：将注入策略错误放入 Runtime，导致插件扩展受限。应对：在契约和代码评审中强约束“Runtime 只定义时机，策略归属 memory 插件”。
- 风险：并发实现不当引发 session 竞态。
  应对：先锁语义后优化吞吐，先保证 correctness。

## 7. 建议执行顺序

1. 先完成 M1 + M2（配置与契约闭环）。
2. 再完成 M3（runtime 并发闭环）。
3. 最后完成 M4 + M5（内置插件、测试和文档）。

## 8. 完成定义（DoD）

- quickstart 示例可跑通。
- 核心单测与集成测试通过。
- 配置错误与插件错误可定位。
- 并发语义符合约定。
- README 覆盖安装、运行、扩展（builtin 与 impl 两种接入）。

## 9. M1 可执行清单（开工顺序）

1. 建立目录骨架与空模块文件（仅结构，不填业务实现）。
2. 在 `config/schema.py` 定义：
   - Agent、PluginRef、ToolRef、RuntimeOptions 的模型。
3. 在 `config/validator.py` 落地硬规则：
   - `type|impl` 二选一。
   - tools id 唯一。
   - runtime 数值字段为正整数。
4. 在 `errors/exceptions.py` 定义最小错误集合：
   - `ConfigError`、`PluginLoadError`、`CapabilityError`。
5. 在 `config/loader.py` 实现读取与校验入口：
   - `load_config(path)` -> parse -> validate -> 返回结构化配置。
6. 编写 M1 单测：
   - 合法配置通过。
   - `type+impl` 冲突失败。
   - `type/impl` 都空失败。
   - 重复 tool id 失败。
7. 产出 quickstart 的最小 `agent.json` 示例（仅配置，不依赖 runtime 实现）。


# research_analyst

演示 2026-04-18 seam 整合后扩展模型的离线研究 Agent。

[English](README.md)

| 机制 | 实现 | 位置 |
|---|---|---|
| 自定义 `tool_executor`（多策略 + 重试） | `SandboxedResearchExecutor` — `evaluate_policy()` 通过 `CompositePolicy` 组合文件系统 + 网络白名单；`execute()` 委托给 `RetryToolExecutor(inner=SafeToolExecutor)` | `app/executor.py` |
| 模式子类的 follow-up 解析 | `FollowupFirstReActPattern` 覆写 `ReActPattern.resolve_followup()`，实现基于规则的正则 → 模板匹配 | `app/followup_pattern.py` + `app/followup_rules.json` |
| 会话持久化 | `jsonl_file` 内置实现 | `agent.json` + `./sessions` |
| 事件日志 | `file_logging` 内置实现 | `agent.json` + `./sessions/events.ndjson` |

## 快速上手（开发环境）

无需真实 API key 或网络访问——演示会在 `127.0.0.1` 上启动一个 `aiohttp` stub 服务器来提供所有 Web 内容。

```bash
# 1. 安装依赖
uv sync

# 2. 运行演示
uv run python examples/research_analyst/run_demo.py
```

## 测试

```bash
# 单元测试（stub 服务器 + follow-up 模式，无外部服务）
uv run pytest -q tests/unit/examples/research_analyst/

# 端到端集成测试（stub 服务器 + mock LLM）
uv run pytest -q tests/integration/test_research_analyst_example.py
```

## 与整合前版本的对比

2026-04-18 之前的版本使用：

- `execution_policy: composite`（嵌套 `filesystem` + `network_allowlist`）——现已合并进 `SandboxedResearchExecutor.evaluate_policy()`（自定义 `tool_executor`）。
- `followup_resolver: rule_based`——现改为在 `FollowupFirstReActPattern` 上覆写 `PatternPlugin.resolve_followup()`，由内置 `ReActPattern.execute()` 自动调用。
- `response_repair_policy: strict_json`——此处省略；对本示例而言内置默认值（abstain）已足够。需要修复行为的应用可在 pattern 子类上覆写 `PatternPlugin.repair_empty_response()`。

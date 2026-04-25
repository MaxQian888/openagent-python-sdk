# multi_agent_support

基于 `agent_router` seam 构建的客服分诊多 Agent 应用。这是 SDK 的多 Agent 旗舰示例——通过单一连贯的业务场景，覆盖 `agent-router` 规范的全部契约（三种 `session_isolation` 模式、深度保护、未知 Agent 错误路径、handoff metadata、子预算兜底）。

简短的 seam 级参考请看 [`examples/multi_agent/`](../multi_agent/)。

[English](README.md)

## 目录结构

```
examples/multi_agent_support/
├── agent_mock.json           # 离线 mock 配置（四个 Agent，无需 API key）
├── agent_real.json           # 真实 LLM 配置（Anthropic 兼容端点）
├── agent_mock_scenario3.json # 深度限制场景变体
├── agent_mock_scenario4.json # 未知 Agent 场景变体
├── .env.example              # 真实 demo 的凭证模板
├── scenarios.py              # demo 和测试共用的 4 个场景函数
├── run_demo_mock.py          # 离线端到端演示（CI 安全）
├── run_demo_real.py          # LLM 驱动的演示
└── app/
    ├── deps.py               # SupportDeps：CustomerStore + TicketStore + trace
    ├── plugins.py            # ToolPlugin 子类（查询、router 绑定、动作）
    └── protocol.py           # pydantic 信封 + 状态键
```

## Agent 拓扑

```
concierge ─┬─ delegate(isolated) ───▶ account_lookup
           │
           ├─ transfer ─▶ refund_specialist ─ delegate(shared) ▶ account_lookup
           │                                       │
           │                                       └─ issue_refund ticket
           │
           └─ transfer ─▶ tech_support ─ delegate(forked)   ▶ account_lookup
                                        └ delegate(isolated) ▶ account_lookup
                                        └─ open_ticket
```

## 快速上手（开发环境）

### 离线 mock 演示（无需 API key）

```bash
uv sync
uv run python examples/multi_agent_support/run_demo_mock.py
```

四个场景均在 < 1 s 内完成，无需网络访问。

### 真实 LLM 演示

```bash
cp examples/multi_agent_support/.env.example examples/multi_agent_support/.env
# 编辑 .env，填入 LLM_API_KEY / LLM_API_BASE / LLM_MODEL
uv run python examples/multi_agent_support/run_demo_real.py
```

仅运行场景 1 和 2（深度限制和未知 Agent 场景依赖真实 LLM 可能不会原样发出的直接工具调用）。使用 `rich_console` 事件总线，工具 / LLM / session 事件实时流式输出到 stderr。

## 场景说明

1. **退款流程** — concierge 将控制权交给 `refund_specialist`，后者以 `session_isolation="shared"` 委托 `account_lookup`，随后持久化退款工单。
2. **技术支持流程** — concierge 将控制权交给 `tech_support`，后者先进行一次 `session_isolation="forked"` 的诊断委托（主假设），再进行一次 `session_isolation="isolated"` 的备用查询，最后开技术工单。
3. **深度限制** — `SelfDelegateLookupTool` 在上下文中 `DELEGATION_DEPTH_KEY == max_delegation_depth` 时调用，在构建任何子 Agent 之前抛出 `DelegationDepthExceededError(depth=3, limit=3)`。
4. **未知 Agent** — `DelegateToMissingTool` 调用 `router.delegate("does_not_exist", ...)` → `AgentNotFoundError("does_not_exist")`。

## 测试

```bash
# 集成测试——全部四个场景 + plugins.py 静态分析（无需 API key）
uv run pytest -q tests/integration/test_multi_agent_support_example.py

# 单元测试——SupportDeps 存储行为
uv run pytest -q tests/unit/test_multi_agent_support_deps.py
```

预期运行时间：≤ 1 s。

## 多 Agent 配置块

```jsonc
"multi_agent": {
  "enabled": true,                        // 将 DefaultAgentRouter 注入 ctx.agent_router
  "default_session_isolation": "isolated",
  "max_delegation_depth": 3,              // 嵌套委托深度保护
  "default_child_budget": {               // 子 run 预算兜底
    "max_steps": 4,
    "max_cost_usd": 0.05
  }
}
```

## 使用到的 Router API

```python
# 在任意工具或 pattern 中：
router = ctx.agent_router  # DefaultAgentRouter，multi_agent.enabled=true 时注入

# 编排（等待专家子 Agent，然后继续）
result = await router.delegate(
    "account_lookup",
    "cust-001",
    ctx,
    session_isolation="shared",   # 或 "isolated" / "forked"
)

# 交接（将控制权永久移交，父 run 以子输出结束）
await router.transfer(
    "refund_specialist",
    "/tool process_refund cust-001",
    ctx,
    session_isolation="isolated",
)
# transfer() 抛出 HandoffSignal；DefaultRuntime 捕获后将
# parent.metadata["handoff_from"] 设置为 child.run_id。
```

## 环境变量（仅真实 LLM 演示需要）

| 名称 | 是否必填 | 说明 |
|------|----------|------|
| `LLM_API_KEY` | 是 | OpenAI 兼容的 API 密钥。 |
| `LLM_API_BASE` | 是 | 提供商 Base URL。 |
| `LLM_MODEL` | 是 | 模型名称。 |

## 延伸阅读

- [docs/multi-agent-support-example.md](../../docs/multi-agent-support-example.md) — 逐场景说明每个 `agent-router` 规范要求的完整演练。
- [openspec/specs/agent-router/spec.md](../../openspec/specs/agent-router/spec.md) — 本示例所演示的正式契约。

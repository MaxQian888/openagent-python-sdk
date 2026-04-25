# multi_agent 示例

> **想看完整的、贴近真实业务的多 Agent 应用？** 请看 [`examples/multi_agent_support/`](../multi_agent_support/) —— 那是 SDK 的多 Agent 旗舰示例，覆盖 `agent_router` 规范的全部契约（三种 session 隔离、深度保护、`AgentNotFoundError`、handoff metadata、`default_child_budget` 兜底等），带完整的集成测试和文档。
>
> 本目录是约 **200 行的 seam 级最小参考**，只演示 `delegate` / `transfer` 两个 API 的基本形状；不覆盖业务分层、deps 传递、错误路径等。第一次读多 Agent 可以先看本示例感受 API，真要落 app 请看 `multi_agent_support`。

[English](README.md)

演示 `agent_router` seam：两种多 Agent 协作模式，分别基于 `delegate`（编排）和 `transfer`（交接）。

## 目录结构

```
examples/multi_agent/
├── plugins.py           # 两个自定义工具：DelegateToSpecialistTool + TransferToBillingTool
├── agent_mock.json      # 使用 mock provider 的 4-agent 配置（无需 API key）
├── agent_real.json      # 使用真实 LLM 的 4-agent 配置（需要 API key）
├── run_demo_mock.py     # 离线演示
├── run_demo_real.py     # LLM 驱动的演示
└── .env.example         # 真实 demo 的环境变量模板
```

四个 Agent：
- `orchestrator` — 挂载 `delegate_to_specialist` 工具
- `specialist` — 子 Agent，接收 orchestrator 的子任务
- `triage` — 挂载 `transfer_to_billing` 工具
- `billing_agent` — 子 Agent，接收 triage 交接的账单请求

## 快速上手（开发环境）

### 离线 mock 演示（无需 API key）

```bash
uv sync
uv run python examples/multi_agent/run_demo_mock.py
```

展示三个场景：
1. **Delegate**：直接调用 `router.delegate("specialist", ...)`，展示 `RunResult` 返回与 `_run_depths` 记录。
2. **Transfer**：直接调用 `router.transfer("billing_agent", ...)` 并捕获 `HandoffSignal`。
3. **Tool-driven**：`runtime.run()` + `/tool delegate_to_specialist ...`，走完整 ReAct → tool → router 路径。

### 真实 LLM 演示

```bash
cp examples/multi_agent/.env.example examples/multi_agent/.env
# 编辑 .env，填入 LLM_API_KEY / LLM_API_BASE / LLM_MODEL
uv run python examples/multi_agent/run_demo_real.py
```

两个场景：
- `orchestrator` 收到事实查询问题，LLM 选择调用 `delegate_to_specialist`，综合返回最终答案。
- `triage` 收到退款请求，LLM 调用 `transfer_to_billing` 将控制权永久交给 `billing_agent`，父 run 以 billing 的输出结束。

## 测试

```bash
uv run pytest -q tests/integration/test_multi_agent.py
```

使用 mock provider，无需 API key。

## 关键 API

```python
# 在自定义工具 / pattern 中：
router = ctx.agent_router  # 由 DefaultRuntime 注入（仅在 multi_agent.enabled=true 时存在）

# Orchestrator（等待子结果，继续执行）
result = await router.delegate(
    "specialist", task, ctx,
    session_isolation="isolated",  # "shared" | "isolated" | "forked"
)

# Handoff（永久交接）
await router.transfer("billing_agent", task, ctx)  # 抛出 HandoffSignal
```

## 启用配置

```json
{
  "multi_agent": {
    "enabled": true,
    "default_session_isolation": "isolated",
    "max_delegation_depth": 3
  }
}
```

- `max_delegation_depth` — 控制嵌套层数，超过时抛 `DelegationDepthExceededError`；深度通过 `RunRequest.metadata["__openagents_delegation_depth__"]` 传递，不使用进程级状态。
- `default_child_budget` — 调用 `delegate(budget=None)` 时自动使用该预算。
- `session_isolation` 模式：
  - `shared` — 子 run 复用父 `session_id`（asyncio-task 可重入锁避免死锁）。
  - `isolated` — 全新 session（默认）。
  - `forked` — `SessionManagerPlugin.fork_session()` 复制父 session 的消息/artifacts 快照到新 `{parent}:fork:{run_id}`；之后父/子独立写。

## 环境变量（仅真实 LLM 演示需要）

| 名称 | 是否必填 | 说明 |
|------|----------|------|
| `LLM_API_KEY` | 是 | OpenAI 兼容的 API 密钥。 |
| `LLM_API_BASE` | 是 | 提供商 Base URL。 |
| `LLM_MODEL` | 是 | 模型名称。 |

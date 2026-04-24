# multi_agent_support 示例详解

`examples/multi_agent_support/` 是 SDK 的多 agent 旗舰示例 —— 它把 `agent_router` seam 的**每一条**契约在同一个客服分诊应用里一次性走通。读完这篇文档你会知道：

- 四个 agent 如何通过 `delegate` / `transfer` 协作
- 三种 `session_isolation`（`shared` / `isolated` / `forked`）分别适合什么场景
- `max_delegation_depth` 和 `AgentNotFoundError` 怎么保护主 run
- `deps` 如何承载跨 agent 的共享状态（`CustomerStore` / `TicketStore` / `trace`）而不污染 kernel
- 为什么这个示例需要把"consult + commit" 打包到单个工具里（ReAct pattern 在一次 run 里只会派发一次 tool）

## 拓扑

```
        user message
             │
             ▼
     ┌──────────────┐
     │  concierge   │
     └────┬───┬─────┘
          │   └─── delegate(isolated) ─────┐
          │                                 ▼
          │                       ┌─────────────────┐
          │                       │  account_lookup │
          │                       └─────────────────┘
          ▼
   ┌─ transfer ─────────────────────────────┐
   │                                        │
   ▼                                        ▼
┌──────────────────┐                ┌─────────────────┐
│ refund_specialist│                │   tech_support  │
└────────┬─────────┘                └────────┬────────┘
         │                                   │
         │ delegate(shared)                  │ delegate(forked) + delegate(isolated)
         ▼                                   ▼
┌─────────────────┐                ┌─────────────────┐
│ account_lookup  │                │ account_lookup  │
└─────────────────┘                └─────────────────┘
```

四个 agent 都挂在 `multi_agent.enabled: true` + `max_delegation_depth: 3` + `default_child_budget: {max_steps: 4, max_cost_usd: 0.05}` 的配置下。

## 分层

示例严格遵循 CLAUDE.md 规定的分层 —— 所有产品语义都放在 `app/`，不渗漏进 kernel：

| 层 | 文件 | 职责 |
|---|---|---|
| SDK seam（不动） | `openagents/plugins/builtin/agent_router/default.py` | 提供 `delegate` / `transfer` / 三种 isolation / depth 检查 |
| App-defined 协议 | `app/protocol.py` | `CustomerIntent`、`TicketDraft`、`DelegationTraceEntry` 三个 pydantic 信封 |
| App-defined 依赖 | `app/deps.py` | `SupportDeps` 包装 `CustomerStore` + `TicketStore` + `trace` |
| App-defined 工具 | `app/plugins.py` | 所有 `ToolPlugin` 子类（读表、写票、router-bound consult / route） |
| 场景编排 | `scenarios.py` | demo 和测试共享的四个场景函数 |

`SupportDeps` 通过 `RunRequest.deps` 附到顶层 run，路由器在构造 child run 时 `deps=None` 自动沿用父的 `ctx.deps`，所以整个调用树共享同一组 `customer_store` / `ticket_store` / `trace`。

## 四个场景

### 场景 1 — 退款流（transfer + shared delegate）

用户输入 `/tool route_to_refund cust-001` 到 concierge。

```
concierge                          refund_specialist                 account_lookup
   │                                      │                               │
   │ RouteToRefundTool.invoke()           │                               │
   │   │                                  │                               │
   │   └─ router.transfer("refund_       │                               │
   │        specialist", "/tool           │                               │
   │        process_refund cust-001")     │                               │
   │                                      │                               │
   │   raises HandoffSignal ←─────────────┤ ProcessRefundTool.invoke()    │
   │                                      │   ├─ router.delegate(          │
   │                                      │   │    "account_lookup",      │
   │                                      │   │    "cust-001",            │
   │                                      │   │    session_isolation=     │
   │                                      │   │      "shared")  ──────────▶
   │                                      │   │                           │ (returns echo)
   │                                      │   │ ◀──────────────────────── │
   │                                      │   └─ ticket_store.create(     │
   │                                      │        TicketDraft(refund))   │
   │                                      │                               │
   │ RunResult.metadata["handoff_from"]   │                               │
   │   = refund_specialist.run_id         │                               │
```

行使的 `agent-router` 契约：

- **Transfer ends the parent run with child output** — concierge 的 `RunResult.metadata["handoff_from"]` 等于 refund_specialist 的 `run_id`，`final_output` 是 refund_specialist 的输出。
- **`shared` session mode — reentrant lock** — refund_specialist 的 `shared` delegate 复用父 session_id，Python asyncio 级可重入锁保证不死锁。
- **Child run budget fallback** — refund_specialist 和 account_lookup 的 child run 都没显式传 `budget=`，走 `default_child_budget`。

断言（`assert_refund_outcome` / 集成测试）：

- `parent.stop_reason == StopReason.COMPLETED`
- `parent.metadata["handoff_from"]` 非空
- `SupportDeps.trace` 里有一条 `(delegate, refund_specialist → account_lookup, shared)`
- `SupportDeps.ticket_store` 里有且仅有一张 `kind="refund"` 的票，`customer_id="cust-001"`

### 场景 2 — 技术流（transfer + forked diagnostic + isolated fallback）

用户输入 `/tool route_to_tech cust-002` 到 concierge。

tech_support 的 `TroubleshootTechTool` 先用 `session_isolation="forked"` 派发"网络"诊断 —— 派生的 child session 是 `{tech_support.session_id}:fork:{tech_support.run_id}`，启动时完整拷贝父 session 的消息和 artifact；接着用 `session_isolation="isolated"` 派发"billing 缓存"回退检查；最后写一张 `tech` 票。

行使的 `agent-router` 契约：

- **`forked` session mode — real snapshot copy** — forked child 看到 fork 时父 session 的完整快照；fork 之后父/子的写互不渗漏。
- **`isolated` session mode** — 第二个诊断分支用全新 session，演示一个 tool 里混用 isolation。
- **Router injection when enabled** — `multi_agent.enabled: true` 保证 `ctx.agent_router` 是 `DefaultAgentRouter`。

*为什么只 fork 一次*：`DefaultAgentRouter._resolve_session` 把 forked child sid 固定为 `{parent_sid}:fork:{parent_run_id}`，同一个父 run 内多次 fork 会撞目标 sid。单次 fork 已经足以覆盖快照 + 隔离契约。

断言：

- `parent.stop_reason == StopReason.COMPLETED`
- `SupportDeps.trace` 至少有一条 `isolation="forked"` 的条目，且 `child_session_id` 匹配 `<parent_sid>:fork:<run_id>` 格式
- 调用 `session_manager.load_messages(forked_child_sid)` 不报错（child session 在 session manager 中真实存在）
- `SupportDeps.ticket_store` 有且仅有一张 `kind="tech"` 的票，`customer_id="cust-002"`

### 场景 3 — 深度保护（DelegationDepthExceededError）

`SelfDelegateLookupTool` 里 `router.delegate("account_lookup", "/tool self_delegate_lookup ...", isolated)` 会递归调用自己。`max_delegation_depth=3` 下第四级（parent depth=3）调用时，路由器在构造 child request 之前就 `raise DelegationDepthExceededError(depth=3, limit=3)`。

场景函数 `run_depth_scenario` 直接构造一个 `RunContext.run_request.metadata={DELEGATION_DEPTH_KEY: 3}` 的 ctx，调用 tool 触发异常 —— 这样原始异常类型可以被 caller 捕获，而不是被 `DefaultRuntime.run()` 的 `except Exception` 包装成 `PatternError`。

行使的 `agent-router` 契约：

- **Delegation depth is tracked via request metadata** — 深度保存在 `RunRequest.metadata["__openagents_delegation_depth__"]`，不使用任何进程级状态。
- **Depth limit enforced** — 深度 ≥ limit 时在 `_run_fn` 前就抛异常。

### 场景 4 — 目标 agent 不存在（AgentNotFoundError）

`DelegateToMissingTool.invoke` 调用 `router.delegate("does_not_exist", ...)`。路由器的 `_agent_exists` 回调（Runtime 注入）在启动 child run 之前返回 False，抛 `AgentNotFoundError("does_not_exist")`。

行使的 `agent-router` 契约：

- **Unknown agent_id raises AgentNotFoundError** — 非 `ConfigError` / 非通用 `Exception`，并且 `.agent_id` 等于传入的错误 id。

## 常见问题

**Q: 为什么要把 consult + commit 塞进同一个 tool？**

`ReActPattern` 在一次 run 里检测到 `_PENDING_TOOL_KEY`（scratch 中）后会把下一步短路成 `final` —— 也就是每个 agent run **最多** 派发一次 tool 调用。所以像 refund 场景里"先查客户再开票"这种两步逻辑，必须打包到一个 tool（`ProcessRefundTool`）里。这不是 example 的设计怪癖，是 builtin ReAct 的 shape。

**Q: 示例用 mock provider 怎么决定派什么 tool？**

`MockLLMClient` 的规则：只解析用户 prompt 的 `INPUT:` 行，如果以 `/tool <id> <query>` 开头就派发对应 tool。所以场景函数通过 `/tool ...` 前缀喂 concierge 的 `input_text`，再由 `RouteToRefundTool` 把 `/tool process_refund ...` 作为 child 的 `input_text` 传下去，一层层 prime 下游 agent。

**Q: `deps.trace` 为什么不放 `ctx.state`？**

`ctx.state` 是 per-run 的 —— 父 run 看不到子 run 的 state。但我们希望顶层测试能检查"整条调用树里一共 delegate / transfer 了几次"，所以 trace 放 deps，成为整棵调用树共享的对象。

**Q: 真实 LLM demo 不保证 tool 派发顺序，怎么办？**

`run_demo_real.py` 只跑场景 1 和场景 2，且不 assert 具体的 `final_output` 字符串；只在 stdout 打印 stop_reason / handoff_from / ticket 结果。CI 的回归锁在 mock 这一侧。

## 相关文档

- [agent-router 规范](../openspec/specs/agent-router/spec.md) —— 每一条契约的正式 WHEN/THEN
- [seam-and-extension-points](seams-and-extension-points.md) —— "这应该放哪层" 的决策树
- [production_coding_agent](examples.md#examplesproduction_coding_agent) —— 单 agent 的对照示例，同样的 app layering 风格

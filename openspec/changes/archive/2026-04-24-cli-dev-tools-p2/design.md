## Context

`enhance-builtin-cli` 建立了 scaffold → run → iterate 的基础循环，并制定了稳定的架构约定：每个子命令一个模块文件（`openagents/cli/commands/<name>.py`），`add_parser` + `run(args) -> int` 两个公开入口，共用 `_events.py` / `_rich.py` / `_exit.py` / `_fallback.py` 工具层，可选 extras 通过 `require_or_hint` 优雅降级。本 change 在此框架内追加功能，不改动架构契约。

本 change 解决的痛点：
1. **CI/自动化**：无法不花 LLM 费用验证配置；无批量执行能力。
2. **交互式开发体验**：`dev` 热重载后没有健康信号；`chat` 会话不可恢复；`/help` 是已知 bug。
3. **工具层诊断**：tool 和 MCP server 的连接/注册问题只能靠写 Python 脚本复现，缺乏直接的 CLI 入口。

## Goals / Non-Goals

**Goals:**
- 所有新功能不引入新的强制依赖；MCP ping 复用现有 `mcp` optional extra。
- `--batch` 的并发模型安全、可预测，对 LLM API rate limit 友好。
- `tools call` 和 `mcp ping/tools` 只能访问已注册/已配置的资源，不暴露任意代码执行面。
- 每个新 flag / 新命令的 exit code 服从现有约定（0/1/2/3）。
- 所有新命令可用 mock provider 头对头测试，不依赖真实网络。

**Non-Goals:**
- 不实现 `openagents bench`（N 次压测 + 统计），留到下一轮。
- 不实现 `openagents sessions list/show/delete`（依赖 session backend 枚举能力，当前 jsonl_file backend 不支持）。
- 不实现 `config diff` / `config env`（有价值但优先级低，留后续）。
- 不实现网络连通性探针或 SDK 版本更新检查（`doctor` 功能扩展，留后续）。
- `tools call` 不支持 async tool（第一版只支持同步/简单 async tool，通过 asyncio.run 调用）。

## Decisions

### 1. `run --dry-run`：实例化 plugin 但拦截 LLM 调用

**决定。** `--dry-run` 在 `load_config` 和 `Runtime.from_config` 成功后 **不** 调用 `runtime.run_detailed`。改为：
1. 调用 `load_config` 校验 JSON/schema；
2. 调用 `Runtime.from_config` 触发 plugin 实例化和能力检查（`loader.py` 的 `capability + required-method checks`）；
3. 打印"dry-run OK: N agents, M seams"到 stdout，exit 0。
任何 `ConfigError` 在步骤 1–2 都会被捕获 → exit 2。

**理由。** 这样做的 "dry-run" 语义是：所有可以在不发出网络请求的情况下检查的内容都被检查了。`Runtime.from_config` 已经做了 plugin 解析和能力校验，对 CI 来说就够了。

**替代方案。** 用 mock LLM provider override 跑一次真实 run — 更彻底但更慢、输出冗长；对 CI 来说超时不可预期。

---

### 2. `run --timeout SECONDS`：asyncio.wait_for 包裹

**决定。** 在 `_run_once` 的 `asyncio.run(...)` 调用外套一层 `asyncio.wait_for(coro, timeout=args.timeout)`，超时时捕获 `asyncio.TimeoutError` → 打印 `TimeoutError: run exceeded {N}s` → exit 3。

**理由。** 与现有 exit 3 语义一致（runtime 错误）。`asyncio.wait_for` 是标准库，无新依赖。

**注意。** `timeout=None`（默认）时保持当前行为。`--timeout` 仅在传入时生效，不作为全局 default。

---

### 3. `run --batch JSONL`：受控并发的 asyncio.gather

**决定。** 批量模式读入 JSONL 文件，每行为 `{"input_text": "...", "session_id": "...（可选）"}` 或纯字符串。
- 并发度由 `--concurrency N`（默认 1，串行）控制，避免默认并发炸 API rate limit。
- 每条记录用一个新的 `asyncio.Semaphore` 限流，通过 `asyncio.gather` 并发执行。
- 每条结果立即以 JSONL 行输出到 stdout：`{"index": N, "input": "...", "output": "...", "stop_reason": "...", "latency_ms": N, "error": null|"..."}`。
- 全部完成后，输出到 **stderr** 的摘要行：`Batch: 12 inputs, 11 OK, 1 error | p50=1.2s p95=4.8s`（避免污染 stdout JSONL 流）。
- 若任意一条失败，exit code 为 3；全部成功为 0。

**理由。** 默认串行（`--concurrency 1`）保护用户免受意外的 API 并发费用；显式 `--concurrency N` 让有需要的用户解锁。摘要到 stderr 让 stdout 保持纯净的 JSONL（可直接 pipe 进 `jq`）。

**替代方案。** 全并发 `asyncio.gather`——对小数据集快，但对 API rate limit 不友好；拒绝，默认安全优先。

---

### 4. `chat /help`：在 `_dispatch_slash` 中补充 `"help"` 分支

**决定。** 这是 bug fix：在 `chat.py:_dispatch_slash` 中 `/help` 当前 fall-through 到错误分支。补充 `if cmd == "/help": console_out.write(HELP_TEXT)`，其中 `HELP_TEXT` 是列出所有斜杠命令的静态字符串，与现有错误消息中列出的命令集保持一致。

---

### 5. `chat /history`：REPL 循环内维护轮次摘要列表

**决定。** `_chat_loop` 中新增 `turns: list[dict]` 列表，每轮 `result` 返回后 append `{"turn": N, "stop_reason": ..., "preview": final_output[:80]}`。`/history` 斜杠命令遍历此列表格式化输出。

**理由。** 数据全部已经在内存里（`last_result` 已有）；只需扩展为列表而非覆写。

---

### 6. `chat --history FILE`：从 `/save` 产生的 JSON 恢复上下文

**决定。** 加载时读取文件（与 `openagents replay` 相同的解析逻辑），从 `{"schema": 1, "session_id": "...", "events": [...]}` 中提取 `session_id` 并作为初始 `session_id` 传入 REPL 循环。**不** replay 历史 events 给 LLM（session backend 已经持久化了 transcript；如果 session backend 无持久化，告知用户历史上下文不会被 LLM 看到）。启动时打印 `"resuming session <id> from <file>"`。

**理由。** 简单可行。深度会话恢复（把历史消息重新注入 context）依赖 session backend 的具体实现，不在 CLI 层强制。

---

### 7. `dev --watch-also GLOB`：扩展 watchdog observer

**决定。** 在 `_watch_with_watchdog` 中，将 `--watch-also` 的每个 glob 展开为唯一的父目录列表，并为每个目录调用 `observer.schedule(_Handler(), dir, recursive=True)`。`_Handler.on_any_event` 检查 `event.src_path` 是否匹配 glob pattern（用 `fnmatch`），匹配则触发 debounce。轮询模式（polling fallback）中同样扩展 mtime 检查的文件集合（glob 展开到当前已存在的文件）。

**理由。** watchdog 的 observer 天然支持多目录监听；只需多次调用 `schedule`。

---

### 8. `dev --test-prompt TEXT`：reload 后异步 probe

**决定。** 每次 `_reload_with_log` 成功后，如果 `--test-prompt` 有值，调用 `asyncio.run(_run_probe(runtime, agent_id, test_prompt))`，捕获结果打印到 stderr：
- 成功：`✓ reload OK | probe {N}ms: {final_output[:60]}`
- 失败：`✗ probe failed: {exc}`

`_run_probe` 使用一个固定的 `session_id="dev-probe"` + `--test-prompt` 文本 + `--timeout 30`（硬限，防 probe 挂起）。

**风险。** probe 会调用真实 LLM，消耗 API 费用。文档中明确说明。

**替代方案。** 提供 `--probe-with-mock` 覆盖 provider → 在本 change 中 SKIP，过于复杂；用户可以在 dev 配置里换成 mock provider。

---

### 9. `tools list`：从 Runtime 读取 tool 注册信息

**决定。** `openagents tools list --config <path> [--agent ID] [--format text|json]`：
- `load_config(path)` → 找到 agent → 读取 `agent.tools` 列表（配置层信息）。
- 对每个 tool ref：读取 `type`、`id`，如果有 `impl`/`type` 对应已注册的 `ToolPlugin`，尝试实例化并调用 `tool.schema()` 或 `getattr(tool, 'description', '')` 获取额外元数据。
- 输出：`id | type | description | params`（text）或 JSON 数组。
- 实例化失败（missing dep、错误的 impl path）不中断——改为显示 `(schema unavailable: <err>)`。

**理由。** 不需要完整 Runtime（避免启动 session backend、event bus），只需 plugin loader 层。

---

### 10. `tools call`：通过 Runtime 执行单个 tool

**决定。** `openagents tools call --config <path> <tool_id> [JSON_ARGS] [--agent ID]`：
- 构造完整 `Runtime.from_config`（需要完整 runtime 保证 tool executor 可用）。
- 从 `runtime.config` 找到 tool ref，通过 `tool_executor` 执行 `ToolExecutionRequest(tool_id=..., params=json.loads(JSON_ARGS))`。
- 打印 result 为 JSON（`--format text` 用 `_render_value` pretty-print）。
- exit 0 成功，exit 3 tool 抛异常。

**安全考量。** `tool_id` 必须存在于 agent 配置的 tools 列表中；不允许调用未在配置中声明的 tool。JSON_ARGS 从 CLI 参数读取，不执行任何 Python eval。

---

### 11. `mcp list`：从配置中读取 MCP server 信息

**决定。** `openagents mcp list --config <path> [--agent ID]`：
- `load_config` → 遍历 agent 的 tools 列表，筛选 `type: mcp` 的 tool ref（或 tools 中存在 `mcp_url` / `mcp_server` 字段的条目）。
- 打印 server url、transport、名称。
- 纯配置读取，不建立网络连接，不需要 `mcp` extra。

---

### 12. `mcp ping` 和 `mcp tools`：连接 MCP server

**决定。** 两个命令都需要 `mcp` extra；缺失时用 `require_or_hint("mcp")` 提示安装并 exit 1。

`mcp ping --config <path> [--agent ID] [--server NAME]` 或 `mcp ping <URL>`：
- 连接 MCP server，调用 `list_tools()`，记录 latency，打印 `✓ <url> latency={N}ms tools={M}` 或 `✗ <err>`。

`mcp tools --config <path> [--agent ID] [--server NAME]` 或 `mcp tools <URL>`：
- 同上但打印完整 tool 列表（id + description + inputSchema）。

**两者的 URL 解析规则**：优先从 config 里匹配（按 server 名称或 index），也接受直接传入 URL 字符串（适合独立测试一个 MCP server）。

**理由。** 允许直接传 URL 使得调试一个尚未加入配置的 MCP server 成为可能。

---

### 13. 新命令注册

`"tools"` 和 `"mcp"` 追加到 `commands/__init__.py` 的 `COMMANDS` 列表。两者都使用 nested subparsers（`tools list`/`tools call`，`mcp list`/`mcp ping`/`mcp tools`），pattern 与现有 `config show` 一致。

## Risks / Trade-offs

- **`--batch` 并发费用风险** → 默认 `--concurrency 1`（串行）；文档强调并发是 opt-in。
- **`dev --test-prompt` 消耗 API 费用** → 文档明确告知；建议配合 mock provider 使用。
- **`tools call` 执行真实副作用**（如文件写入、HTTP 请求）→ 文档标注；`tools call` 不比直接 `openagents run` 更危险，因为 tool 必须在配置中声明。
- **`mcp ping` 依赖网络 + MCP server 在线** → 超时设 10s 硬限；exit 1 给出明确的连接错误信息；CI 不应依赖 `mcp ping`（用 `doctor` 代替）。
- **`chat --history FILE` 上下文不注入 LLM**：如果 session backend 无持久化（如 `in_memory`），恢复的 session_id 对 LLM 是"空的"。文档说明此限制；对有 jsonl_file backend 的用户透明。
- **`--watch-also` glob 展开**：如果 glob 匹配到大量文件（如 `**/*`），watchdog observer 可能注册过多 inotify 句柄。文档建议用精确 glob；在代码中限制最多 1000 个文件触发警告。

## Why

`enhance-builtin-cli` 完成了核心的 scaffold → run → iterate 开发循环，但覆盖的场景主要是"跑起来"——一旦开发者进入"调试/持续开发"阶段，当前 CLI 缺少三类关键能力：自动化/CI 场景下的批量执行与空跑、交互式开发中的上下文可见性与会话延续、以及工具层（tool / MCP）的直接诊断。这些缺口在对比 CrewAI、LangChain CLI、Mastra 和 Temporal 后清晰可见，且都有直接用户场景支撑，不是假设性需求。

## What Changes

- **`openagents run --dry-run`**：仅加载配置 + 解析所有 plugin，不发任何 LLM 请求，以 CI 友好的方式验证 `agent.json` 变更；exit 0 表示"一切可以运行"。
- **`openagents run --timeout SECONDS`**：为单次 run 设置最大挂钟时间；超时后以 exit 3 退出并打印 `TimeoutError`。
- **`openagents run --batch JSONL`**：批量执行模式——从 JSONL 文件读取多条 `{input_text, session_id?}` 记录，并发/串行执行，输出结果 JSONL（含 latency、stop_reason、final_output），结尾打印摘要行（N 条、成功/失败数、p50/p95 延迟）。
- **`openagents chat /help`**：修复已知 bug——`/help` 当前返回 "unknown slash command"，应列出所有可用斜杠命令及其用法。
- **`openagents chat /history`**：新斜杠命令，列出本 session 所有历史轮次摘要（turn N, stop_reason, output 前 80 字符）。
- **`openagents chat --history FILE`**：启动时从 `/save` 产生的 JSON 文件恢复上一次 session，使"上次聊到哪里，继续"成为可能。
- **`openagents dev --watch-also GLOB`**：除 `agent.json` 外，额外监听 glob 匹配的文件（典型用法：`"plugins/**/*.py"`）；任何一个文件变更都触发 `Runtime.reload()`。
- **`openagents dev --test-prompt TEXT`**：每次 reload 成功后自动发一个轻量 probe 请求，并在终端输出 `✓ reload 142ms | run 890ms` 或 `✗ run failed: <err>`，给开发者即时的"绿灯/红灯"反馈。
- **`openagents tools list`**：列出某个 agent 已注册的 tool（id、type、描述、参数 schema 摘要），替代 `chat /tools` 的只读入口，适合非交互场景。
- **`openagents tools call`**：不经过 LLM，直接调用一个 tool 并打印结果；用于验证工具注册是否正确、参数格式是否符合预期。
- **`openagents mcp list`**：列出 `agent.json` 中配置的 MCP server（url、transport、连接参数）。
- **`openagents mcp ping`**：测试 MCP server 连接可达性，返回延迟和 tool 数量。
- **`openagents mcp tools`**：连接 MCP server，列出其暴露的 tool id + 描述 + 输入 schema。

无 **BREAKING** 改动：所有现有命令的 flags 和输出格式不变；新功能均为加法。

## Capabilities

### New Capabilities
- `cli-run-advanced`: `openagents run` 的自动化扩展——`--dry-run`（零 LLM 调用的 CI 校验）、`--timeout`（超时保护）、`--batch`（批量执行 + 摘要统计）。
- `cli-interactive-depth`: 交互式开发体验深化——`chat` 的 `/help` bug 修复、`/history` 斜杠命令、`--history FILE` 会话恢复；`dev` 的 `--watch-also` 多文件监听和 `--test-prompt` 自动 probe。
- `cli-tools-subcommand`: 新顶级子命令 `openagents tools`，提供 `list`（工具注册检查）和 `call`（直接调用工具，不走 LLM），聚焦 tool 集成调试场景。
- `cli-mcp-subcommand`: 新顶级子命令 `openagents mcp`，提供 `list`（配置中的 MCP server）、`ping`（连通性探测）、`tools`（枚举 server 暴露的 tool），聚焦 MCP 集成调试场景。

### Modified Capabilities
<!-- 现有全局 specs/ 中无 builtin-cli 条目（该 spec 仍在 enhance-builtin-cli change 中），
     本 change 通过新建 specs 扩展 CLI 能力，不触发全局 spec 修改。 -->

## Impact

- **Code**: 新增 `openagents/cli/commands/tools.py` 和 `openagents/cli/commands/mcp.py`；扩展 `run.py`（`--dry-run`、`--timeout`、`--batch` 分支）、`chat.py`（`/help`、`/history`、`--history`）、`dev.py`（`--watch-also`、`--test-prompt`）。`COMMANDS` 注册表新增 `"tools"` 和 `"mcp"`。
- **Dependencies**: `--batch` 并发执行可选用标准库 `asyncio.gather`（无新依赖）；`--timeout` 用 `asyncio.wait_for`；MCP 连接复用现有 `mcp` optional extra；`dev --watch-also` 复用已有的 `watchdog` 依赖。不引入任何新的强制依赖。
- **APIs**: 不改动 kernel interfaces（`RunRequest`、`RunResult`、`Runtime`）。`--batch` 复用 `Runtime.run_detailed`，`tools call` 通过 `Runtime` 的 tool executor 路径执行。
- **Tests**: 每个新 flag / 新命令对应一个 `tests/unit/test_cli_<cmd>.py`（或在已有 test 文件中扩展）。`--dry-run` 和 `--batch` 增加 integration smoke test。覆盖率维持 90% 以上不新增豁免。
- **Docs**: `docs/cli.md` / `docs/cli.en.md` 新增各子命令的用法说明；子命令一览表追加 `tools` / `mcp` 行。

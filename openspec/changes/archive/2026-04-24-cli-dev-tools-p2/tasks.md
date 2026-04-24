## 1. `openagents run` 扩展（--dry-run / --timeout / --batch）

- [x] 1.1 在 `openagents/cli/commands/run.py::add_parser` 中新增三个参数：`--dry-run`（store_true）、`--timeout SECONDS`（type=float）、`--batch PATH`（dest="batch_file"）；`--batch` 与 `--input` / `--input-file` 互斥（`argparse.add_mutually_exclusive_group` 或手工检测 → exit 1）。
- [x] 1.2 在 `run.py::run` 函数顶部处理 `--dry-run` 分支：`load_config` → `Runtime.from_config` → 打印 `dry-run OK: {N} agent(s), {M} seams configured` → exit 0；干运行时跳过 `_resolve_input` 校验（prompt 可为空）。
- [x] 1.3 将现有 `asyncio.run(_run_once(...))` 包裹进 `asyncio.wait_for` 当 `args.timeout` 不为 None 时；捕获 `asyncio.TimeoutError` → stderr `TimeoutError: run exceeded {N}s` → exit 3。
- [x] 1.4 新增 `_run_batch(runtime, agent_id, batch_file, *, concurrency, timeout, fmt)` 协程：读取 JSONL、每行解析为 `{input_text, session_id?}`（兼容纯字符串行）、用 `asyncio.Semaphore(concurrency)` 限流、`asyncio.gather` 并发执行、每条记录完成后立即向 stdout emit 结果 JSONL 行；全部完成后向 stderr emit 摘要（计算 p50 / p95）。
- [x] 1.5 在 `run.py::run` 函数中检测 `args.batch_file`，若存在则调用 `asyncio.run(_run_batch(...))`；`--concurrency` 默认值为 1；批量模式下跳过 `_resolve_input` 的"no input"报错。
- [x] 1.6 新增 `tests/unit/test_cli_run.py` 中已有的 test 文件扩展（如无则新建）：
  - `test_dry_run_valid_config` — mock Runtime.from_config，断言 exit 0 + stdout 含 `dry-run OK`
  - `test_dry_run_bad_config` — load_config 抛 ConfigError，断言 exit 2
  - `test_dry_run_no_input_ok` — 无 --input 时 dry-run 依然 exit 0
  - `test_timeout_exceeded` — asyncio.wait_for side_effect TimeoutError，断言 exit 3 + stderr 含 `TimeoutError`
  - `test_timeout_within_limit` — 正常完成，exit 0
  - `test_batch_serial_3_inputs` — batch file with 3 lines, concurrency=1, 断言 3 JSONL 行 + stderr 摘要
  - `test_batch_partial_failure_exit3` — 第 2 条 mock 抛异常，exit 3，第 2 行 output error 非 null
  - `test_batch_mutual_exclusive_with_input` — --batch + --input 同时传 → exit 1
  - `test_batch_concurrency_2` — 验证 Semaphore(2) 下 6 条并发不超过 2

## 2. `openagents chat` 扩展（/help / /history / --history）

- [x] 2.1 在 `openagents/cli/commands/chat.py` 中定义 `_HELP_TEXT` 常量，列出所有斜杠命令及说明；在 `_dispatch_slash` 中补充 `if cmd == "/help": console_out.write(_HELP_TEXT)` 分支（bug fix）。
- [x] 2.2 修改 `_chat_loop` 签名，新增 `turns: list[dict]`（在调用方初始化为 `[]`）；每次成功 `result` 后 append `{"turn": len(turns)+1, "stop_reason": ..., "preview": str(result.final_output or "")[:80]}`。
- [x] 2.3 在 `_dispatch_slash` 中补充 `/history` 分支：遍历 `turns` 列表格式化输出，无轮次时打印 `(no turns yet)`；`/reset` 时同步清空 `turns`（传引用或通过返回新 session_id + 外层重置）。
- [x] 2.4 在 `add_parser` 中新增 `--history FILE` 参数（`dest="history_file"`）；在 `run` 函数中检测互斥（`--history` + `--session-id` 不能同时传 → exit 1）。
- [x] 2.5 实现 `_load_history_session(path: str) -> str`：读取 JSON 文件、提取 `session_id`，文件不存在或解析失败 → exit 1；返回 session_id。在 `run` 函数中使用返回值替换默认生成的 `session_id` 并打印 banner 到 stderr。
- [x] 2.6 扩展（或新建）`tests/unit/test_cli_chat.py`：
  - `test_help_slash_command` — 输入 `/help`，断言输出含所有命令名，不含 "unknown"
  - `test_history_empty` — `/history` before any turn → `(no turns yet)`
  - `test_history_two_turns` — 发两条消息后 `/history` → 2 行 `turn N`
  - `test_history_reset_clears` — turn → /reset → /history → `(no turns yet)`
  - `test_history_file_load_ok` — 临时 JSON 文件含 session_id，断言 session 使用该 id
  - `test_history_file_not_found` — exit 1 + stderr 含文件路径
  - `test_history_file_malformed` — exit 1 + 描述性错误
  - `test_history_and_session_id_conflict` — exit 1

## 3. `openagents dev` 扩展（--watch-also / --test-prompt）

- [x] 3.1 在 `openagents/cli/commands/dev.py::add_parser` 中新增 `--watch-also` (`action="append"`, `dest="watch_also"`, `default=[]`, `metavar="GLOB"`) 和 `--test-prompt` (`dest="test_prompt"`, `default=None`) 参数。
- [x] 3.2 修改 `_watch_with_watchdog`：接受额外的 `watch_globs: list[str]` 参数；展开每个 glob 的唯一父目录集合，调用 `observer.schedule(_Handler(), dir, recursive=True)`；`_Handler.on_any_event` 对 extra glob 文件也触发 debounce；展开文件数 > 1000 时向 stderr 写 warning。
- [x] 3.3 修改 `_watch_polling`：接受 `watch_globs`；在 `{path: mtime}` 字典中加入 glob 展开的文件；每次 poll 更新 mtime 对比。
- [x] 3.4 实现 `_probe(runtime, agent_id, test_prompt, *, timeout=30.0) -> tuple[bool, str]`：构建 RunRequest → asyncio.wait_for → 返回 (True, f"probe {N}ms: {output[:60]}") 或 (False, f"{ExcType}: {msg}")。
- [x] 3.5 修改 `_reload_with_log`：接受可选 `test_prompt: str | None` 和 `agent_id: str | None`；reload 成功后如果 `test_prompt` 非空，调用 `_probe` 并将结果拼入 stderr 行（`✓ reload OK | ...` 或 `✗ probe failed: ...`）。
- [x] 3.6 在 `dev.py::run` 中将 `args.watch_also` 和 `args.test_prompt` 传入监听函数。
- [x] 3.7 扩展（或新建）`tests/unit/test_cli_dev.py`：
  - `test_watch_also_parser` — `--watch-also` 收集多个 glob
  - `test_watch_also_triggers_reload` — mock watchdog observer，断言 extra glob 目录被 schedule
  - `test_watch_also_large_glob_warning` — glob 展开 >1000 文件时 stderr 有 warning
  - `test_test_prompt_success` — reload 成功 + probe 成功 → stderr 含 `✓ reload OK | probe`
  - `test_test_prompt_failure` — probe 抛异常 → stderr 含 `✗ probe failed:`
  - `test_test_prompt_timeout` — probe asyncio.TimeoutError → stderr 含 `TimeoutError`
  - `test_no_test_prompt_no_probe` — 不传 --test-prompt 时 _probe 未被调用

## 4. `openagents tools` 新命令

- [x] 4.1 创建 `openagents/cli/commands/tools.py`：顶层 `add_parser` 注册 `tools` + nested subparsers `list` / `call`；`run(args)` 根据 `args.tools_action` 分派；无 action → exit 1 + 用法提示。
- [x] 4.2 实现 `_list_tools(cfg, agent_id, fmt)` 函数：遍历 `agent.tools`，对每个 tool ref 尝试插件解析获取 description + params；插件解析失败捕获为 `"(schema unavailable: <err>)"`；text 格式对齐列打印，json 格式输出 JSON 数组；无 tool 时打印 `(no tools registered for agent <id>)`。
- [x] 4.3 实现 `_call_tool(cfg, path, agent_id, tool_id, json_args_str, fmt)`：验证 tool_id 在 agent.tools 中；`Runtime.from_config(path)` → 获取 tool_executor → 构建 `ToolExecutionRequest` → 执行；result 用 `_render_value`（text）或 `json.dumps`（json）输出；tool 抛异常 → exit 3；JSON parse 失败 → exit 1。
- [x] 4.4 在 `add_parser` 中为 `list` 注册 `--config`、`--agent`、`--format`；为 `call` 注册 `--config`、`--agent`、`<tool_id>`（positional）、`[JSON_ARGS]`（nargs="?"）、`--format`。
- [x] 4.5 将 `"tools"` 追加到 `openagents/cli/commands/__init__.py` 的 `COMMANDS` 列表。
- [x] 4.6 新建 `tests/unit/test_cli_tools.py`（最少 10 测试）：
  - `test_list_no_subaction_exit1`
  - `test_list_single_agent_text`
  - `test_list_json_parseable`
  - `test_list_tool_schema_unavailable` — impl 不可导入时仍 exit 0
  - `test_list_no_tools_message`
  - `test_list_multi_agent_requires_agent_flag`
  - `test_call_success_text`
  - `test_call_unknown_tool_exit1`
  - `test_call_tool_raises_exit3`
  - `test_call_bad_json_args_exit1`
  - `test_call_empty_json_args_defaults_to_empty_dict`
  - `test_call_json_format`

## 5. `openagents mcp` 新命令

- [x] - [x] 5.1 创建 `openagents/cli/commands/mcp.py`：顶层 `add_parser` 注册 `mcp` + nested subparsers `list` / `ping` / `tools`；`run(args)` 分派；无 action → exit 1。
- [x] - [x] 5.2 实现 `_mcp_list(cfg, agent_id, fmt)`：从 `agent.tools` 筛选 `type=="mcp"` 或含 `mcp_url`/`mcp_server` 字段的条目；text / json 格式输出；无 MCP server → 提示信息；纯配置读取，无网络调用。
- [x] - [x] 5.3 实现 `_resolve_mcp_url(cfg, agent_id, server_name) -> str | None`：从配置中按 server 名 / index 找 URL；返回 None 表示未找到。`ping` 和 `tools` 的 URL 可来自配置或直接命令行参数。
- [x] - [x] 5.4 实现 `async _mcp_connect_list_tools(url, timeout) -> list[dict]`：用 `mcp` 库连接 server、调 `list_tools()`，返回 tool 列表；连接失败/超时抛异常（调用方捕获）。
- [x] - [x] 5.5 实现 `_run_ping(url, timeout)`：调用 `_mcp_connect_list_tools`，计算 latency，格式化打印 `✓`/`✗` 行；exit 0/3。
- [x] - [x] 5.6 实现 `_run_tools(url, timeout, fmt)`：调用 `_mcp_connect_list_tools`，打印完整 tool 列表（text / json）；exit 0/3。
- [x] - [x] 5.7 在 `add_parser` 中为 `list` 注册 `--config`、`--agent`、`--format`；为 `ping` / `tools` 注册可选的 `--config + --agent + --server` 或直接 `[url]` positional + `--timeout`（default 10.0）+ `--format`（tools only）。
- [x] - [x] 5.8 将 `"mcp"` 追加到 `COMMANDS` 列表。
- [x] 5.9 新建 `tests/unit/test_cli_mcp.py`（最少 10 测试，全部 mock 网络）：
  - `test_mcp_no_subaction_exit1`
  - `test_list_shows_mcp_servers`
  - `test_list_no_mcp_servers_message`
  - `test_list_json_format`
  - `test_ping_success` — mock `_mcp_connect_list_tools` 返回 3 tools，断言 stdout 含 `✓` + `tools=3`
  - `test_ping_connection_refused_exit3`
  - `test_ping_timeout_exit3`
  - `test_ping_mcp_extra_missing_exit1`
  - `test_tools_success_text`
  - `test_tools_success_json_parseable`
  - `test_tools_empty_server`
  - `test_tools_connection_error_exit3`

## 6. 文档与集成

- [x] 6.1 在 `docs/cli.md` 的子命令一览表中追加 `tools list`、`tools call`、`mcp list`、`mcp ping`、`mcp tools` 行；在 `run` 行的备注中提及 `--dry-run` / `--timeout` / `--batch`。
- [x] 6.2 在 `docs/cli.md` 中新增"批量执行"用法章节，示例：`openagents run agent.json --batch inputs.jsonl --concurrency 3 | jq -c .`；注明 `--concurrency` 默认值为 1 以及 API rate limit 注意事项。
- [x] 6.3 在 `docs/cli.md` 的 chat 斜杠命令表中追加 `/help` 和 `/history` 行。
- [x] 6.4 在 `docs/cli.md` 的 dev 章节补充 `--watch-also` 和 `--test-prompt` 用法；注明 `--test-prompt` 会产生真实 LLM 调用。
- [x] 6.5 同步更新 `docs/cli.en.md` 与中文版内容保持一致。

## 7. 验证

- [x] 7.1 `uv run pytest -q` — 全套测试 0 失败（含所有新增测试）。
- [x] 7.2 `uv run coverage run -m pytest && uv run coverage report` — TOTAL ≥ 90%，无新豁免。
- [x] 7.3 手工烟雾测试：`openagents run examples/quickstart/agent.json --dry-run`（mock provider）→ exit 0；`openagents tools list --config examples/quickstart/agent.json` → 输出不报错；`openagents chat examples/quickstart/agent.json` → `/help` 正常打印。
- [x] 7.4 `openspec validate cli-dev-tools-p2 --strict` passes。

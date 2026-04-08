# 示例说明

这个仓库里的 `examples/` 不是一组重复 demo，而是几种不同的接入方式：

- 最小可运行路径
- 用 `impl` 直接加载自定义插件
- 接真实 `openai_compatible` Provider
- 带交互命令的研究型 agent
- 带持久化 memory 的实验沙盒
- 演示 agent 级 runtime seam 组合的示例

如果你只想先确认 SDK 能跑，先看 `quickstart`。如果你要改配置或接真实模型，再往后看其他目录。

## `examples/quickstart/`

用途：

- 最小可运行 agent
- 使用 builtin `window_buffer` memory、`react` pattern、`builtin_search` tool
- LLM provider 使用 `mock`

关键文件：

- `agent.json`
- `run_demo.py`

这个示例会在同一个 `session_id="demo"` 下连续跑两次：

- 第一次输入普通文本 `hello`
- 第二次输入 `/tool search memory injection`

运行命令：

```bash
uv run python examples/quickstart/run_demo.py
```

适合场景：

- 第一次跑仓库
- 验证 `Runtime.from_config()`、session 复用、memory 注入和 tool 调用链路

## `examples/custom_impl/`

用途：

- 演示 agent 级组件如何通过 `impl` 指向真实 Python symbol
- 不依赖装饰器注册表
- 适合理解 loader 如何实例化自定义 `Memory`、`Pattern`、`Tool`

关键文件：

- `agent.json`
- `plugins.py`
- `run_demo.py`

`agent.json` 里直接引用：

- `examples.custom_impl.plugins.CustomMemory`
- `examples.custom_impl.plugins.CustomPattern`
- `examples.custom_impl.plugins.CustomTool`

其中 `plugins.py` 里：

- `CustomMemory` 实现 `inject()` / `writeback()`
- `CustomPattern` 先生成 tool call，再直接执行 `custom_tool`
- `CustomTool` 返回一个带 `prefix` 和 `memory_items` 的结果

运行命令：

```bash
uv run python -m examples.custom_impl.run_demo
```

适合场景：

- 学习 `impl` 配置怎么写
- 调试 plugin loader 的导入与实例化行为
- 给自己的插件做最小骨架参考

## `examples/openai_compatible/`

用途：

- 演示如何接任意 OpenAI-compatible backend
- 展示 `.env` 与 JSON 配置组合使用的方式
- 保留一个最小的真实 LLM 调用路径

关键文件：

- `.env.example`
- `agent.json`
- `run_demo.py`

运行前提：

1. 准备 `examples/openai_compatible/.env`
2. 至少设置以下环境变量：
   - `OPENAI_MODEL`
   - `OPENAI_BASE_URL`
   - `OPENAI_API_KEY`

这个示例的 `run_demo.py` 不直接调用 `Runtime.from_config()`，而是：

- 先用 `openagents.utils.build.load_dotenv()` 读取 `.env`
- 再用 `openagents.utils.build.build_runtime()` 读入 `agent.json`
- 用环境变量覆盖 `llm.model` 和 `llm.api_base`
- 固定把 `llm.api_key_env` 设为 `OPENAI_API_KEY`

运行命令：

```bash
uv run python examples/openai_compatible/run_demo.py
```

适合场景：

- 接 OpenAI 官方接口
- 接兼容 OpenAI API 的自建网关或第三方 Provider
- 验证真实 LLM + builtin tool 的联动

## `examples/longcat/`

用途：

- 一个明确指向 LongCat 的 `openai_compatible` 示例
- 比 `openai_compatible/` 更接近“开箱即用”的 Provider 配置模板

关键文件：

- `agent.json`
- `run_demo.py`
- `test_full.py`

配置特点：

- agent id 是 `longcat-agent`
- `llm.provider` 是 `openai_compatible`
- `llm.api_base` 固定为 `https://api.longcat.chat/openai/v1`
- tools 同时启用了 `builtin_search` 和 `calc`

运行前提：

- 设置 `LONGCAT_API_KEY`

运行命令：

```bash
uv run python examples/longcat/run_demo.py
```

如果你要做更完整的手工验证，可以再读 `test_full.py`，里面覆盖了多轮对话、tool 调用、pattern 和 memory 相关测试脚本。

适合场景：

- 已经确定要接 LongCat
- 想看一个具体 Provider 的完整 JSON 写法

## `examples/runtime_composition/`

用途：

- 演示 agent 级 `tool_executor`、`execution_policy`、`context_assembler` 如何组合
- 展示 builtin `safe`、`filesystem`、`summarizing` 的最小可运行写法
- 保留一个确定性、无需真实 LLM 的 runtime 组合路径

关键文件：

- `agent.json`
- `plugins.py`
- `run_demo.py`
- `workspace/note.txt`

运行命令：

```bash
uv run python examples/runtime_composition/run_demo.py
```

适合场景：

- 想理解 agent 级 runtime seam 的配置方式
- 想看一个比 `quickstart` 更贴近真实 runtime 组合的示例
- 想验证 SDK kernel 的组合能力，而不引入 team/product 层

## `examples/research_agent/`

用途：

- 一个更接近真实使用的交互式 research agent
- 展示较大的 context window、较长 timeout 和多个 builtin tools 的组合
- 演示 event bus 订阅和交互式 session 管理

关键文件：

- `.env.example`
- `agent.json`
- `run_demo.py`

配置特点：

- memory 使用 `window_buffer`，窗口大小是 `30`
- pattern 使用 `react`，`max_steps=20`
- LLM 使用 LongCat 的 `openai_compatible` 配置
- tools 包括 `builtin_search`、`http_request`、`url_parse`

交互命令：

- `/help`
- `/new`
- `/session`
- `/sessions`
- `/quit` / `/exit`

运行前提：

- 设置 `LONGCAT_API_KEY`
- 或者先根据 `.env.example` 准备本地 `.env`

运行命令：

```bash
uv run python examples/research_agent/run_demo.py
```

适合场景：

- `quickstart` 太简单，想看一个更真实的交互式 agent
- 想观察 tool 事件和 step 事件
- 想参考多 tool research 配置

## `examples/persistent_qa/`

用途：

- 一个偏实验性质的持久化问答沙盒
- 展示 `chain` memory、较多 builtin tools 和自定义插件目录的组合
- 适合做回归验证或二次开发试验田

关键文件：

- `agent.json`
- `agent_test.json`
- `run_demo.py`
- `test_e2e.py`
- `TEST_REPORT.md`
- `plugins/`

配置特点：

- 主 agent id 是 `qa_assistant`
- memory 使用 `chain`，其中包含一个 `window_buffer`
- LLM 使用 LongCat 的 `openai_compatible` 配置
- tools 包括 `builtin_search`、`calc`、`current_time`、`date_parse`、`random_int`、`uuid`、`url_parse`、`json_parse`、`read_file`、`list_files`

运行时行为：

- `run_demo.py` 会读取 `examples/persistent_qa/.env`，或者直接使用环境变量里的 `LONGCAT_API_KEY`
- 支持 `/new`、`/history`、`/quit`
- 运行过程中会订阅 `llm.`、`tool.`、`qa.` 前缀事件
- 历史记录会以 JSON 形式写到 `.agent_memory/` 目录

运行命令：

```bash
uv run python examples/persistent_qa/run_demo.py
```

适合场景：

- 想看 memory 持久化的近似实现
- 想把 SDK 当成一个实验沙盒来验证复杂交互
- 想结合 `agent_test.json`、`test_e2e.py` 做更完整的本地测试

## 怎么选

- 先确认仓库能跑：`quickstart`
- 学 `impl` 形式的自定义插件：`custom_impl`
- 看 agent 级 runtime seam 组合：`runtime_composition`
- 验证 OpenAI-compatible 接入：`openai_compatible`
- 直接看 LongCat 配置模板：`longcat`
- 看交互式 research agent：`research_agent`
- 看持久化与实验性能力：`persistent_qa`

## 相关文档

- [配置参考](configuration.md)
- [开发指南](developer-guide.md)
- [插件开发](plugin-development.md)
- [API 参考](api-reference.md)

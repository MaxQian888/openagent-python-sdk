# quickstart

基于 Anthropic 兼容端点（默认使用 MiniMax）的单 Agent ReAct 演示。

[English](README.md)

## 快速上手（开发环境）

```bash
# 1. 安装依赖
uv sync

# 2. 配置凭证
cp examples/quickstart/.env.example examples/quickstart/.env
# 编辑 .env，填写 LLM_API_KEY、LLM_API_BASE、LLM_MODEL

# 3. 通过内置 CLI 运行
openagents run examples/quickstart/agent.json --input "hello"
```

其他输出格式：

```bash
# JSONL 事件流（适合流水线接入）
openagents run examples/quickstart/agent.json --input "hello" --format events

# 完整 RunResult JSON
openagents run examples/quickstart/agent.json --input "hello" --format json --no-stream

# 交互式多轮对话
openagents chat examples/quickstart/agent.json
```

## 遗留脚本

`run_demo.py` 作为历史参考保留，它是一个一次性包装器：加载 `.env`，构建 `Runtime`，并发起两个硬编码的 `run` 调用。新代码请优先使用 `openagents run` / `openagents chat`。

## 测试

quickstart agent 通过 CLI 冒烟测试和 `openagents run` 集成测试覆盖，均使用 mock provider，无需真实 API key：

```bash
uv run pytest -q tests/integration/test_cli_smoke.py
uv run pytest -q tests/unit/cli/commands/test_run.py
```

## 环境变量

| 名称 | 是否必填 | 说明 |
|------|----------|------|
| `LLM_API_KEY` | 是 | OpenAI 兼容的 API 密钥。 |
| `LLM_API_BASE` | 是 | 提供商 Base URL（如 `https://api.minimax.chat/anthropic`）。 |
| `LLM_MODEL` | 是 | 模型名称（如 `abab6.5-chat`）。 |

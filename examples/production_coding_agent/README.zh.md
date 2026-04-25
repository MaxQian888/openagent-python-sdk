# 生产级编码 Agent

基于 OpenAgents 内核构建的生产风格编码 Agent。

[English](README.md)

演示内容：

- 显式任务包组装
- 持久化编码记忆
- 带文件系统边界的安全工具执行
- 本地 follow-up 语义
- 结构化交付物
- 基准测试评估框架
- **持久化执行**：`run_demo.py` 传递 `durable=True`——若上游 LLM 在运行中途遭遇速率限制/连接错误，runtime 会自动加载最近的步骤检查点并恢复（受 `RunBudget.max_resume_attempts` 限制）。

## 目录结构

```text
production_coding_agent/
  agent.json
  run_demo.py
  run_benchmark.py
  app/
    protocols.py
    plugins.py
    benchmark.py
  benchmarks/
    tasks.json
  workspace/
    PRODUCT_BRIEF.md
    app/
    tests/
  outputs/
```

### 各文件职责

- `agent.json` — runtime 配置
- `run_demo.py` — 交互式演示入口
- `run_benchmark.py` — 本地基准测试入口
- `app/protocols.py` — 结构化协议对象
- `app/plugins.py` — 记忆、上下文组装器、follow-up、修复、pattern
- `app/benchmark.py` — 确定性基准测试执行器
- `benchmarks/tasks.json` — 基准测试任务集
- `workspace/` — 待检查的模拟仓库
- `outputs/` — 生成的交付物

## 快速上手（开发环境）

```bash
# 1. 安装依赖
uv sync

# 2. 配置凭证
cp examples/production_coding_agent/.env.example examples/production_coding_agent/.env
# 编辑 .env，填写 LLM_API_KEY、LLM_API_BASE、LLM_MODEL

# 3. 通过内置 CLI 运行（推荐）
openagents run examples/production_coding_agent/agent.json \
    --input "implement TicketService.close_ticket and add tests"

# 交互式多轮对话
openagents chat examples/production_coding_agent/agent.json

# 遗留演示脚本（等价，保留作说明）
uv run python examples/production_coding_agent/run_demo.py
```

## 基准测试

```bash
uv run python examples/production_coding_agent/run_benchmark.py
```

## 测试

```bash
# 集成测试——确定性 mock LLM，无需真实 API key
uv run pytest -q tests/integration/test_production_coding_agent_example.py
```

## 环境变量

| 名称 | 是否必填 | 说明 |
|------|----------|------|
| `LLM_API_KEY` | 是 | OpenAI 兼容的 API 密钥。 |
| `LLM_API_BASE` | 是 | 提供商 Base URL。 |
| `LLM_MODEL` | 是 | 模型名称。 |

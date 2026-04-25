# pptx-agent

基于 openagents SDK 构建的交互式 CLI，驱动 7 阶段 PPT 生成流水线。

[English](README.md)

```bash
uv add "io-openagent-sdk[pptx]"
pptx-agent new --topic "你的演示文稿主题"
```

## 功能介绍

1. **意图分析（Intent）** — LLM 将你的自由文本描述转换为结构化 `IntentReport`，逐字段确认或编辑。
2. **环境检查（Environment）** — 检测 Python / Node / npm / markitdown / API 密钥，缺失项目可交互修复。
3. **资料调研（Research）** — 调用 Tavily（优先 MCP，回退 REST），多选保留的信息来源。
4. **大纲规划（Outline）** — 逐张生成幻灯片大纲，支持 `accept / add slide / remove slide / reorder / edit slide / regenerate all / abort` 操作。
5. **主题选择（Theme）** — Agent 并排返回 3–5 个主题候选，选一个或打开自定义编辑器。
6. **幻灯片生成（Slide generation）** — 每张幻灯片作为独立 Agent 调用并发执行，含 slot-schema 校验、最多 2 次重试，以及自由格式兜底。
7. **编译与质检（Compile + QA）** — 写出 PptxGenJS JS 文件，执行 `node compile.js`，通过 `markitdown` 回读 PPTX 做内容验证。

## 快速上手（开发环境）

### 1. 配置环境变量

复制模板并填入你的密钥：

```bash
cp examples/pptx_generator/.env.example examples/pptx_generator/.env
# 编辑 .env，至少填写 LLM_API_KEY、LLM_API_BASE 和 LLM_MODEL
```

也可以写入用户级配置（所有项目共享）：

```bash
mkdir -p ~/.config/pptx-agent
cp examples/pptx_generator/.env.example ~/.config/pptx-agent/.env
```

### 2. 安装依赖

```bash
uv sync
# 需要 Node 18+（用于 PptxGenJS 编译阶段）
node --version
```

### 3. 从 repo 根目录运行

```bash
# 新建演示文稿
uv run python -m examples.pptx_generator.cli new --topic "AI Agent 工作原理"

# 恢复中断的项目（slug 由上一步输出）
uv run python -m examples.pptx_generator.cli resume <slug>

# 查看跨会话偏好记忆
uv run python -m examples.pptx_generator.cli memory list
```

## 命令参考

```bash
pptx-agent new --topic "..."             # 新建演示文稿
pptx-agent resume <slug>                 # 恢复中断的项目
pptx-agent memory list [--section ...]   # 列出已保存的偏好
pptx-agent memory forget <entry_id>      # 删除某条偏好记录
```

## 测试

所有测试从 repo 根目录运行，**无需真实 API key**——外部服务全部通过 `monkeypatch` / mock 隔离。

### 运行全部 pptx 相关测试

```bash
# 单元测试（快，不依赖外部服务）
uv run pytest -q tests/unit/test_pptx_cli.py \
                 tests/unit/test_pptx_state.py \
                 tests/unit/test_pptx_persistence.py \
                 tests/unit/test_pptx_agent_config.py \
                 tests/unit/test_pptx_templates.py \
                 tests/unit/test_pptx_wizard_layout.py \
                 tests/unit/test_pptx_wizard_editors.py \
                 tests/unit/test_pptx_qa_scan.py \
                 tests/unit/test_pptx_slide_runner.py

# 端到端集成测试（全 7 步 wizard，外部服务 mock）
uv run pytest -q tests/integration/test_pptx_generator_example.py

# scaffold 冒烟测试（openagents init + run 验证脚手架可执行）
uv run pytest -q tests/unit/cli/commands/test_init_pptx_wizard_runs.py
```

### 单跑一个测试用例

```bash
uv run pytest -q tests/integration/test_pptx_generator_example.py::test_end_to_end_all_stages_mocked
```

### 测试中如何 mock LLM 和外部服务

集成测试（`test_pptx_generator_example.py`）展示了完整模式：

```python
# 1. 注入假 runtime，按 agent_id 分派返回值
async def fake_runtime_run(*, agent_id, session_id, input_text, deps=None):
    if agent_id == "intent-analyst":
        return SimpleNamespace(parsed=IntentReport(...), state={...})
    ...
fake_runtime = SimpleNamespace(run=fake_runtime_run)

# 2. 注入假 shell（跳过 node compile.js）
fake_shell = SimpleNamespace(invoke=AsyncMock(return_value={"exit_code": 0, ...}))

# 3. 传给 run_wizard——绕过 agent.json，不需要真实 API key
rc = await run_wizard(project, runtime=fake_runtime, shell_tool=fake_shell)
```

`run_wizard` 的 `runtime=` 和 `shell_tool=` 参数专为测试注入设计。正常运行时留空即可，函数内部会自动从 `agent.json` 构建。

## 回放历史运行

每次 `pptx-agent new` / `resume` 运行，都会通过内置 `FileLoggingEventBus` 将完整事件流追加写入 `outputs/<slug>/events.jsonl`。文件为追加式 NDJSON，每行格式为 `{"name", "payload", "ts"}`，可直接被 `openagents replay` 消费：

```bash
openagents replay outputs/<slug>/events.jsonl
```

写入时会自动脱敏 `api_key` / `authorization` / `token` / `secret` / `password` 等字段，可安全分享给协作者。若需为单次运行重定向日志路径，在调用前设置 `PPTX_EVENTS_LOG`。

## 中断恢复

项目状态以原子写入方式持久化到 `outputs/<slug>/project.json`，并维护滚动备份 `project.json.bak`。任意阶段按 Ctrl+C 都会刷新状态（退出码 130），之后用 `pptx-agent resume <slug>` 从中断处继续。若 `project.json` 损坏，CLI 会提示从备份恢复、重新开始或中止。

## 偏好记忆

跨会话偏好存储在 `~/.config/pptx-agent/memory/` 下，以人类可读的 Markdown 文件保存（`user_goals.md`、`user_feedback.md`、`decisions.md`、`references.md`，附带 `MEMORY.md` 索引）。第 1 / 3 / 5 / 6 阶段各提供一个可选的"存为偏好"提示，后续运行会将已存偏好注入 Agent 上下文。

## 文档

- CLI 使用指南：[`docs/pptx-agent-cli.md`](../../docs/pptx-agent-cli.md) · [EN](../../docs/pptx-agent-cli.en.md)
- 原始设计文档：[`docs/superpowers/specs/2026-04-18-pptx-agent-design.md`](../../docs/superpowers/specs/2026-04-18-pptx-agent-design.md)
- OpenSpec 变更：[`openspec/changes/pptx-example-full-interactions/`](../../openspec/changes/pptx-example-full-interactions/)

## 环境变量

| 名称 | 是否必填 | 说明 |
|------|----------|------|
| `LLM_API_KEY` | 是 | OpenAI 兼容的 API 密钥（MiniMax、Anthropic 兼容端点、OpenAI 等）。 |
| `LLM_API_BASE` | 是 | 提供商 Base URL。 |
| `LLM_MODEL` | 是 | 模型名称。 |
| `TAVILY_API_KEY` | 否 | 启用调研阶段的网页搜索。 |
| `PPTX_AGENT_OUTPUTS` | 否 | 覆盖项目输出根目录（默认：`examples/pptx_generator/outputs`）。 |
| `PPTX_EVENTS_LOG` | 否 | 覆盖单项目事件日志路径（默认：`outputs/<slug>/events.jsonl`）。 |

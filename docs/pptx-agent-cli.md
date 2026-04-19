# pptx-agent CLI 使用指南

## 安装

```bash
uv add "io-openagent-sdk[pptx]"
```

还需要系统级依赖：Python ≥3.10、Node.js ≥18、npm、`markitdown`（Python 包）。首次运行时，CLI 会检测并引导你安装缺项。

## 命令

- `pptx-agent new [--topic "..."] [--slug ...]` — 开始新 deck
- `pptx-agent resume <slug>` — 恢复一个被中断的 deck
- `pptx-agent memory list [--section ...]` — 列出已保存的用户偏好
- `pptx-agent memory forget <entry_id>` — 删除某条偏好
- `pptx-agent memory --section ...` — 旧写法，等同 `memory list --section ...`

## 7 阶段流程与交互

1. **Intent Analysis** — LLM 把你的自然语言描述转成结构化 `IntentReport`；CLI 展示所有字段，允许你在 `confirm / edit field / regenerate / abort` 间选择。选 `edit field` 后可修改 `topic / audience / purpose / tone / slide_count_hint / language / required_sections / visuals_hint / research_queries`，列表字段支持 `add / remove / reorder / edit-item`。确认后可选 "save as preference" 把偏好写入 `user_goals`。
2. **Environment Check** — 检查 Python / Node / npm / markitdown / API keys，缺项交互修复（密钥用 password 输入，写入用户级 `.env`）。
3. **Research** — 用 Tavily MCP（或 REST fallback）联网搜索；结果按 source 展示，可多选保留。确认后可选 "save as preference" 写入 `references`。
4. **Outline** — 生成 slide-by-slide 大纲，菜单：`accept / add slide / remove slide / reorder slides / edit slide / regenerate all / abort`。编辑后索引会自动压实。`regenerate all` 前会确认丢弃本地改动。
5. **Theme** — agent 产出 3–5 个候选主题，Rich `Columns` 并列展示（5 色色块 + 字体对 + style + badge）。菜单 `pick 1..N / regenerate / custom editor / abort`；`custom editor` 会逐字段引导 hex + 字体 + style + badge，hex 输入会自动去掉前缀 `#`。选定后可选 "save as preference" 写入 `decisions`。
6. **Slide Generation** — 每张 slide 独立的 agent run，按 `concurrency=3` 并行生成。返回的 `SlideIR` 会按 slide 类型的 slot schema 严格校验；失败后最多重试 2 次，仍失败则 fallback 成 `freeform` + 基础脚本。Live 表格实时展示每张 slide 的状态（`queued / running / retry-N / ok / fallback / failed`）。完成后给出 `N ok / M fallback / K failed` 汇总，允许对任一失败索引手动 `rerun`。
7. **Compile + QA** — 写入 JS 模板 → `npm install`（`node_modules` 已存在则跳过）→ `node compile.js` → `markitdown` 回读校验。

## Resume

所有项目状态持久化在 `outputs/<slug>/project.json`（atomic write，每次写入前备份成 `project.json.bak`）。任何阶段 Ctrl+C 退出后，都可以 `pptx-agent resume <slug>` 从该阶段恢复，退出码 `130`。

如果 `project.json` 损坏或通不过 pydantic 校验，CLI 会打印错误并弹出交互菜单：
1. 从 `project.json.bak` 恢复
2. 删除当前 `project.json` 重新来过
3. Abort

## Keys & `.env`

- 必需：`LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL`
- 可选：`TAVILY_API_KEY`（启用联网研究）
- 用户级 `.env`：`~/.config/pptx-agent/.env`（跨项目共享）
- 项目级 `.env`：`outputs/<slug>/.env`（覆盖用户级）

## Memory

跨会话记忆基于 `MarkdownMemory`，文件落在 `~/.config/pptx-agent/memory/`：

```
MEMORY.md          索引
user_goals.md      意图阶段确认的偏好
user_feedback.md   其他反馈规则（兜底分类）
decisions.md       主题 / 切片阶段确认的决策
references.md      研究阶段保留的引用
```

下一次运行同一 agent 时，这些条目会通过 `memory_view` 注入到上下文里，让 LLM 按你之前的偏好输出。`pptx-agent memory forget <id>` 可以随时撤销某条偏好。

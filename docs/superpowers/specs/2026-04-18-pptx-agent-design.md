# PPTX Agent — 生产级 PPT 生成 CLI · Design

**Date:** 2026-04-18

## Goal

在本 SDK 之上打造一个生产级、交互式的 PPT 生成 CLI（`pptx-agent`），演示并推动 SDK 成熟：

1. **7 阶段 pipeline**（意图→环境→研究→大纲→主题→切片→编译QA），每阶段一次 `Runtime.run()`，边界强制用户确认。
2. **TUI 质感**：Rich 布局（status bar / sidebar / main / log tail）+ questionary 方向键菜单，对齐 `uv` / `gh` / `poetry` 的观感。
3. **联网研究**：默认通过 MCP 调用 Tavily；MCP 不可用时退化到原生 `tavily_search` 工具。
4. **环境 / Key 引导**：主动交互式修复 Python / Node / markitdown / 必需 key / 可选 key 的缺项；两级 `.env`（用户级默认，项目级覆盖）。
5. **跨会话长期记忆**：引入新的内建 `markdown_memory`，用 Markdown 文件（`MEMORY.md` 索引 + sectioned files）持久化用户目标 / 反馈 / 决策 / 引用；本产品 7 阶段每步注入已学偏好，并支持一键"下次都这样"。
6. **PPT 渲染复用现有 skill**：Python CLI 编排 + Node/PptxGenJS 渲染，原样集成 `D:/Project/skills-test/pptx-generator` 的 design-system / slide-types / editing / pitfalls / pptxgenjs 参考。

## Non-Goals

- 多 agent 多 session 并发编排（本工具单用户单项目）
- 云端协同 / 多人评审
- 浏览器预览 / 实时 WYSIWYG
- 非 PPTX 格式（Keynote / Google Slides）
- 定制 LLM provider 之外的新 LLM 协议
- 替换/重写 SDK 现有任何 seam 协议

## Architecture

三层分工，严守 SDK 的 kernel / seam / app 边界：

```
┌─────────────────────────────────────────────────────────────┐
│  app 层： examples/pptx_generator/                           │
│  ├─ cli.py             Rich + questionary 向导主入口          │
│  ├─ wizard/            7 个 WizardStep（每阶段一个 UI 面板）    │
│  ├─ state.py           DeckProject + 7 个 pydantic 数据模型     │
│  ├─ app/plugins.py     每个 agent 的 pattern / context_assembler │
│  ├─ templates/         5 种 slide type 的 JS 模板 (PptxGenJS)   │
│  ├─ agent.json         7 个 agent 条目一起声明                 │
│  ├─ skills/            原样复制 pptx-generator skill 作为参考   │
│  ├─ outputs/<slug>/    项目产物目录（.env / project.json / pptx）│
│  └─ README.md                                                 │
├─────────────────────────────────────────────────────────────┤
│  seam 层：不改协议；使用既有 pattern / tool_executor / …        │
├─────────────────────────────────────────────────────────────┤
│  SDK 内建新增：                                                 │
│  ├─ openagents/plugins/builtin/tool/shell_exec.py             │
│  ├─ openagents/plugins/builtin/tool/tavily_search.py           │
│  ├─ openagents/plugins/builtin/memory/markdown_memory.py       │
│  ├─ openagents/plugins/builtin/tool/memory_tools.py           │
│  │     （含 remember_preference）                              │
│  ├─ openagents/utils/env_doctor.py                             │
│  └─ openagents/cli/wizard.py                                    │
└─────────────────────────────────────────────────────────────┘
```

## New SDK Builtins

### 1. `shell_exec` 工具

`openagents/plugins/builtin/tool/shell_exec.py`

```python
class ShellExecTool(TypedConfigPluginMixin, ToolPlugin):
    class Config(BaseModel):
        cwd: str | None = None
        env_passthrough: list[str] = []                # 白名单环境变量名
        command_allowlist: list[str] | None = None     # None=放开；否则仅允许 argv[0] 在列表内
        default_timeout_ms: int = 60_000
        capture_bytes: int = 1_048_576                 # stdout/stderr 各自上限
```

- **invoke args**：`{"command": str | list[str], "cwd"?: str, "timeout_ms"?: int, "env"?: dict[str, str]}`
- **returns**：`{"exit_code": int, "stdout": str, "stderr": str, "timed_out": bool, "truncated": bool}`
- 实现：`asyncio.create_subprocess_exec`；`env` merge 规则为 `os.environ` ∩ `env_passthrough` ∪ `invoke.env`
- `command_allowlist` 在工具层硬断言；`tool_executor` 的 `safe` / `filesystem_aware` 不绕过
- 注册到 `plugins/registry.py` 的 tool 段，`type: "shell_exec"`

### 2. `tavily_search` 工具

`openagents/plugins/builtin/tool/tavily_search.py`

```python
class TavilySearchTool(TypedConfigPluginMixin, ToolPlugin):
    class Config(BaseModel):
        api_key_env: str = "TAVILY_API_KEY"
        default_max_results: int = 5
        default_search_depth: Literal["basic", "advanced"] = "basic"
        timeout_ms: int = 15_000
```

- **invoke args**：`{"query": str, "max_results"?: int, "search_depth"?: str, "include_domains"?: list[str], "exclude_domains"?: list[str]}`
- **returns**：`{"results": [{"url", "title", "content", "score"}], "query": str, "search_depth": str}`
- 实现：用 `httpx.AsyncClient` POST `https://api.tavily.com/search`；`api_key` 从 env 读取，缺失抛 `ToolInvocationError`
- 作为 MCP 降级路径，`research-agent` 默认走 MCP，若 MCP 连接失败，`execution_policy` 可在 app 层切换工具（后续 PR）；本期先同时注册两者，由 agent 系统提示引导优先级

### 3. `markdown_memory` 内建 memory

`openagents/plugins/builtin/memory/markdown_memory.py`

**设计契约：**

```
memory_dir/
├─ MEMORY.md             索引（<200 行）
├─ user_goals.md         用户长期目标 / 角色 / 任务偏好
├─ user_feedback.md      反馈规则（追加型，每条 timestamp + Why + 规则）
├─ decisions.md          已确认的关键决策
└─ references.md         外部资源指向
```

```python
class MarkdownMemory(TypedConfigPluginMixin, MemoryPlugin):
    class Config(BaseModel):
        memory_dir: str = "~/.config/openagents/memory"
        max_chars_per_section: int = 2000
        sections: list[str] = ["user_goals", "user_feedback", "decisions", "references"]
        enable_remember_tool: bool = True
```

- **`inject(context)`**：读 `MEMORY.md` 解析出 section→文件映射；按 `sections` 顺序读取每个子文件（超过 `max_chars_per_section` 时保留最后 N 条 entry），put 到 `context.memory_view[section_name]` 为 `list[MemoryEntry]`
- **`writeback(context)`**：从 `context.state["_pending_memory_writes"]` 读取本轮条目 → append 到对应子文件；如新建 section 则更新 `MEMORY.md`
- **`retrieve(query, context) -> list[dict]`**：关键字/substring 匹配（case-insensitive），返回最多 20 条；后续可替换为 embedding 而不破协议
- **公共 API（供 app 层直接调用）**：
  - `capture(category: str, rule: str, reason: str) -> str`（返回 entry_id）
  - `forget(entry_id: str) -> bool`
  - `list_entries(section: str) -> list[MemoryEntry]`
- **MemoryEntry 格式**（子文件内）：

  ```markdown
  ### <entry_id> · 2026-04-18T12:34:56Z
  **Rule:** 中文标题 + Arial 英文正文
  **Why:** 用户在 intent 阶段明确说"英文正文用 Arial，中文用微软雅黑"
  **Applies to:** theme-selector, slide-generator
  ```
- 与 `chain` / `window_buffer` 可正常嵌套；内部仅操作本 section 键，不污染全局 `memory_view`

### 4. `remember_preference` 工具

`openagents/plugins/builtin/tool/memory_tools.py`

- **schema**：`{"category": str, "rule": str, "reason": str}`（`category` 必须属于 `markdown_memory.sections`，否则落到 `user_feedback`）
- **行为**：往 `context.state["_pending_memory_writes"]` 压一条；`markdown_memory.writeback` 负责持久化
- 和 `markdown_memory.enable_remember_tool=True` 联动（loader 在注册 `markdown_memory` 时自动一并注册该 tool）

### 5. `env_doctor` 工具库

`openagents/utils/env_doctor.py`

```python
class CheckStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"
    ERROR = "error"

class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    detail: str
    fix_hint: str | None = None
    get_url: str | None = None

class EnvironmentCheck(Protocol):
    name: str
    required: bool
    async def check(self) -> CheckResult: ...
    async def auto_fix(self, console: Console) -> bool: ...   # 可选；default False

class EnvironmentReport(BaseModel):
    checks: list[CheckResult]
    missing_required: list[str]
    missing_optional: list[str]
    auto_fixable: list[str]

class EnvironmentDoctor:
    def __init__(self, checks: list[EnvironmentCheck],
                 dotenv_paths: list[Path]): ...
    async def run(self) -> EnvironmentReport
    async def interactive_fix(self, report, console) -> EnvironmentReport
    def persist_env(self, key: str, value: str, level: Literal["user", "project"]) -> Path
```

**内建 checks（同一模块）：**

- `PythonVersionCheck(min_version="3.10")`
- `NodeVersionCheck(min_version="18")`（`node --version`）
- `NpmCheck()`
- `CliBinaryCheck(name: str, install_hint: str, get_url: str | None)`（用于 `markitdown`）
- `EnvVarCheck(name, required: bool, get_url: str | None, description: str)`

### 6. `wizard` 组件库

`openagents/cli/wizard.py`

```python
@dataclass
class StepResult:
    status: Literal["completed", "skipped", "aborted", "retry"]
    data: Any = None

class WizardStep(Protocol):
    title: str
    description: str
    async def render(self, console: Console, project: Any) -> StepResult: ...

class Wizard:
    def __init__(self, steps: list[WizardStep],
                 project: Any,
                 layout: Literal["sidebar", "linear"] = "sidebar",
                 console: Console | None = None): ...
    async def run(self) -> Literal["completed", "aborted"]
    async def resume(self, from_step: str) -> Literal["completed", "aborted"]

# 静态便捷组件（封装 Rich + questionary）：
Wizard.panel(title, body)
Wizard.confirm(prompt, default=True)
Wizard.select(prompt, choices, default=None)
Wizard.multi_select(prompt, choices, min_selected=0)
Wizard.password(prompt)
Wizard.text(prompt, default=None, validator=None)
Wizard.progress(task_name) -> AsyncContextManager
Wizard.live_log(title) -> AsyncContextManager
```

- `layout="sidebar"` 渲染 Rich `Layout`：顶 status bar / 左 sidebar（7 步 tree）/ 中 main / 底 log tail
- `resume()` 从 `project.stage` 读起点；每完成一步，`console.clear()` 后切下一步

## Data Models

`examples/pptx_generator/state.py`（pydantic v2）：

```python
class IntentReport(BaseModel):
    topic: str
    audience: str
    purpose: Literal["pitch", "report", "teaching", "announcement", "other"]
    tone: Literal["formal", "casual", "energetic", "minimalist"]
    slide_count_hint: int  # 3..20
    required_sections: list[str]
    visuals_hint: list[str]
    research_queries: list[str]
    language: Literal["zh", "en", "bilingual"]

class Source(BaseModel):
    url: str
    title: str
    snippet: str
    published_at: str | None = None
    score: float | None = None

class ResearchFindings(BaseModel):
    queries_executed: list[str]
    sources: list[Source]
    key_facts: list[str]
    caveats: list[str]

class SlideSpec(BaseModel):
    index: int
    type: Literal["cover", "agenda", "content", "transition", "closing", "freeform"]
    title: str
    key_points: list[str]
    sources_cited: list[int]      # 指向 ResearchFindings.sources 下标

class SlideOutline(BaseModel):
    slides: list[SlideSpec]

class Palette(BaseModel):
    primary: str   # 6 位 hex，不带 #
    secondary: str
    accent: str
    light: str
    bg: str

class FontPairing(BaseModel):
    heading: str
    body: str
    cjk: str

class ThemeSelection(BaseModel):
    palette: Palette
    fonts: FontPairing
    style: Literal["sharp", "soft", "rounded", "pill"]
    page_badge_style: Literal["circle", "pill"]

class SlideIR(BaseModel):
    index: int
    type: Literal["cover", "agenda", "content", "transition", "closing", "freeform"]
    slots: dict[str, Any]        # 按 type 验证的子 schema（下方模板章节约定）
    freeform_js: str | None = None
    generated_at: datetime

class DeckProject(BaseModel):
    slug: str
    created_at: datetime
    stage: Literal["intent", "env", "research", "outline",
                   "theme", "slides", "compile", "done"]
    intent: IntentReport | None = None
    research: ResearchFindings | None = None
    outline: SlideOutline | None = None
    theme: ThemeSelection | None = None
    slides: list[SlideIR] = []
    env_report: EnvironmentReport | None = None    # 从 openagents.utils.env_doctor import
    last_error: str | None = None
```

**持久化**：`outputs/<slug>/project.json`，每阶段完成后 atomic 写（写临时文件 → `os.replace`）；写入前先把旧文件复制为 `project.json.bak`。

**字段跨模块引用**：`EnvironmentReport` 在 `openagents/utils/env_doctor.py` 定义，`state.py` 从那里 import；其他字段全部本地定义。

## Slide Template Slot Schemas

5 个 JS 模板位于 `examples/pptx_generator/templates/`，对应 skill 的 5 种 slide types。每个模板导出 `createSlide(pres, theme, slots)` 同步函数。

| Type | `slots` 必填字段 |
|---|---|
| `cover` | `{title, subtitle?, author?, date?}` |
| `agenda` | `{title, items[]}`（每 item 为 `{label, sub?}`） |
| `content` | `{title, body_blocks[]}`（block 可为 `{kind:"bullets", items[]}` / `{kind:"two_column", left_items[], right_items[]}` / `{kind:"callout", text, icon?}`） |
| `transition` | `{section_number, section_title, subtitle?}` |
| `closing` | `{title, call_to_action?, contact?}` |
| `freeform` | `freeform_js` 字符串替代 slots；CLI 直接写入 slide 文件 |

每个 slot schema 用独立的 pydantic 子模型在 `state.py` 声明并在 slide-generator 阶段校验；校验失败重跑最多 2 次，仍失败则 fallback 到 `freeform`。

## 7-Stage Pipeline

阶段分两类：

- **LLM-driven 阶段**（1, 3, 4, 5, 6）：通过 `runtime.run(agent_id=..., session_id=<slug>, input_text=<structured>)` 驱动；stage 6 内部对 N 片 slide 并行多次 `runtime.run`（concurrency 默认 3）
- **CLI-local 阶段**（2, 7）：不调用 LLM，CLI 直接调用 SDK 工具（`EnvironmentDoctor` / `ShellExecTool`）

每阶段开始前读 `project.json`，完成后 atomic 写；任何阶段可 Ctrl+C 退出后 `pptx-agent resume <slug>` 恢复。

| # | Agent ID | Tools | UI 动作 | 输入 | 产出 | 确认点 |
|---|---|---|---|---|---|---|
| 1 | `intent-analyst` | `remember_preference` | Rich Panel 展示 LLM 理解 → questionary 逐字段修正 | 用户 raw prompt + memory.user_goals + memory.user_feedback | `IntentReport` | 意图确认 + "是否保存这些偏好？" |
| 2 | `env-doctor`（非 agent；CLI 直调 `EnvironmentDoctor`） | — | 表格展示 checks；缺项交互式修复 | `IntentReport`（含 language 等影响 checks 的信息） | `EnvironmentReport` + 副作用 | 每个缺项单独 confirm；可选 key 先问 "是否启用该功能" |
| 3 | `research-agent` | Tavily MCP（默认）+ `tavily_search`（fallback）+ `http_request`（builtin `HttpRequestTool`）+ `remember_preference` | 并发跑 `research_queries` → Rich Tree 展示 sources → multi-select 选保留项 | `IntentReport` | `ResearchFindings` | "保留 N 条；继续？"；若 `research_queries` 为空或用户禁用 Tavily，跳过本阶段（写入空 `ResearchFindings`） |
| 4 | `outliner` | —（仅 LLM） | Rich Tree/Table 按 slide_count_hint 预排 → 每片可编辑/增删/重排 | `IntentReport` + `ResearchFindings` | `SlideOutline` | 每次修改走 questionary |
| 5 | `theme-selector` | （内部 palette/font 库查询工具；读 skill 的 design-system.md） | Rich Columns 并列展示 3-5 个候选 theme（色块 + 字体示例） → arrow-key 选择 | `IntentReport` + memory.decisions | `ThemeSelection` | "选此主题 / 查看更多 / 自定义 hex" |
| 6 | `slide-generator` | `remember_preference` | 每片一次 `runtime.run`；`asyncio.gather` 并行（默认 concurrency=3，可配）；Rich Live 展示每片状态；schema 校验失败重跑 ≤2 次，仍失败 fallback freeform | `SlideOutline` + `ResearchFindings` + `ThemeSelection` | `list[SlideIR]` | 聚合后展示 "成功 N / fallback M / 失败 K" ，失败允许手工重选 |
| 7 | `compile-qa`（非 agent；CLI 调 `ShellExecTool`） | `shell_exec` | 4 步 Rich Live：① SlideIR → JS 文件写盘（在 `outputs/<slug>/slides/`） ② `npm install pptxgenjs`（首次） ③ `node compile.js` ④ `markitdown presentation.pptx -o presentation.md` ⑤ `rg -i "xxxx\|lorem\|placeholder\|this page"` 扫描 | `list[SlideIR]` + `ThemeSelection` | `.pptx` + QA 报告 | 发现问题 → "回阶段 X 修 / 手工编辑 / 接受并完成" |

**阶段间并发约束**：阶段本身串行（一次一个）；stage 6 内部并行（slide-level）。

## UI Layout

Rich `Layout` 四段式：

```
┌─ pptx-agent · deck-slug-abc123 · stage 4/7 · 02:15 ───────────┐
│                                    Status Bar (固定，实时更新)  │
├────────────────┬───────────────────────────────────────────────┤
│ Sidebar        │ Main                                          │
│ ✓ 1 意图分析    │                                               │
│ ✓ 2 环境检查    │    <当前步骤面板>                              │
│ ✓ 3 联网研究    │                                               │
│ ▶ 4 大纲       │                                               │
│ ○ 5 主题       │                                               │
│ ○ 6 切片       │                                               │
│ ○ 7 编译QA     │                                               │
├────────────────┴───────────────────────────────────────────────┤
│ Logs (最后 5 行，可 `l` 展开)                                    │
└────────────────────────────────────────────────────────────────┘
```

- 每次阶段切换：`console.clear()` 重绘 Layout
- questionary prompt 在 main 区域渲染
- 长任务用 `Progress` 或 `Live` 嵌入 main

## Memory Integration

- **共享 memory** 声明在 `agent.json` 顶层（跨阶段共享）：`chain = window_buffer(12) + markdown_memory(~/.config/pptx-agent/memory)`
- stage 1 / 3 / 5 / 6 的 agent context 通过 `memory_view["user_goals"]` / `["user_feedback"]` / `["decisions"]` 注入
- 每阶段可写 memory 的来源：
  - agent 主动调用 `remember_preference`（需 `enable_remember_tool=True`）
  - CLI 向导在用户勾选 "下次都这样" 时直接调用 `MarkdownMemory.capture`
- `writeback` 在每次 `runtime.run` 后自动触发；CLI 直接调用 `capture` 走同样的 IO 路径

## Error Handling & Resume

| 失败点 | 策略 |
|---|---|
| LLM 响应被 `response_repair_policy` 无法修复 | 向用户展示原始响应 → 允许 "重跑 / 手工编辑 / 回上一步" |
| schema 校验失败（intent / outline / slide / theme） | 重跑该 agent 最多 2 次；仍失败：intent/outline/theme 弹到用户手工编辑；slide 自动 fallback freeform |
| `shell_exec` 超时 / 非零退出 | 保留完整 stdout/stderr 到 `outputs/<slug>/logs/<stage>-<ts>.log`；UI 展示首 40 行；让用户选 "重跑 / 跳过 / 回退阶段" |
| Tavily 查询错误（key 缺失 / 配额） | fallback `http_request`（搜索引擎开源端点），或用户确认 "跳过研究" |
| Ctrl+C | 捕获 `KeyboardInterrupt`；刷一次 `project.json`；打印 "已保存至 X；`pptx-agent resume <slug>` 恢复" |
| `project.json` 损坏 | 启动时 pydantic 校验；失败 → 展示错误 + 允许 "从最近备份恢复 / 删除并新建"（每次写入前先复制旧文件到 `project.json.bak`） |

## Testing Strategy

遵循仓库铁律（AGENTS.md）：源码改动必须同改测试；coverage floor 92%；新增 builtin 不进 `coverage.omit`。

| 新文件 | 测试文件 | 覆盖要点 |
|---|---|---|
| `shell_exec.py` | `tests/unit/test_shell_exec_tool.py` | 成功 / 超时 / 退出码非零 / stdout 截断 / allowlist 拒绝 / env merge；`asyncio.create_subprocess_exec` 用 `unittest.mock.AsyncMock` |
| `tavily_search.py` | `tests/unit/test_tavily_search_tool.py` | httpx 用 `respx` mock；key 缺失错误；默认参数；include/exclude domains |
| `markdown_memory.py` | `tests/unit/test_markdown_memory.py` | tmp_path；读/写/索引更新/裁剪/retrieve；与 `chain` 组合；`capture` / `forget` / `list_entries`；损坏文件 graceful fallback |
| `memory_tools.py` | `tests/unit/test_remember_preference_tool.py` | 推入 `_pending_memory_writes`；非法 category fallback；多次调用累积 |
| `utils/env_doctor.py` | `tests/unit/test_env_doctor.py` | 各 check 的 ok/missing/outdated；auto_fix 路径；dotenv 合并；interactive_fix 用 mock console |
| `cli/wizard.py` | `tests/unit/test_cli_wizard.py` | step 完成 / 跳过 / abort / retry；mock console；sidebar 布局渲染 snapshot |
| 7 个 example plugin | `tests/integration/test_pptx_generator_example.py` | mock LLM（本地 stub provider）+ mock Tavily + mock shell_exec；end-to-end 跑完 7 阶段产出 `project.json`；**不**产出真实 `.pptx`（compile 阶段只校验命令构造） |

`coverage.omit` 只保留需要 optional extra 才能跑的文件：
```
mem0_memory.py, mcp_tool.py, sqlite_backed.py, otel_bridge.py
```

## Packaging

`pyproject.toml`：

```toml
[project.optional-dependencies]
pptx = [
  "io-openagent-sdk[rich,mcp]",
  "questionary>=2.0.1",
  "python-dotenv>=1.0",
  "httpx>=0.27.0",           # tavily_search
]

[project.scripts]
openagents = "openagents.cli.main:main"
pptx-agent = "examples.pptx_generator.cli:main"
```

安装：`uv add "io-openagent-sdk[pptx]"` → 执行 `pptx-agent`。

**Node / npm / markitdown / PptxGenJS** 不通过 pip 管理，全部由 `env_doctor` 运行时引导安装。

## Skill Integration

- 原样拷贝 `D:/Project/skills-test/pptx-generator/` → `examples/pptx_generator/skills/pptx-generator/`（含 SKILL.md、references/、agents/）
- references/ 在本产品中作为**模板作者 & 开发者文档**，**不**每次注入 LLM；LLM 只看 slot schema + 风格摘要
- 产品 README 标注：本工具是 skill 的"自动化实现路径"，手动/自由路径仍以 skill 为准
- `templates/` 下 5 个 JS 文件从 skill 的 slide-types.md 契约直接派生；每模板独立可测（`node slides/cover-preview.js` 输出单页预览）

## Version & Changelog

- 版本：0.3.0 → **0.4.0**（新增 builtin seams 实现 + 新 example + 新 CLI 入口，minor 级）
- `CHANGELOG.md` 新增 0.4.0 条目，分 Added / Changed / Docs 小节

## Docs Updates

- `docs/examples.md`：追加 pptx_generator 一节
- `docs/seams-and-extension-points.md`：memory builtin 表格增行 `markdown_memory`
- 新增 `docs/pptx-agent-cli.md`：用户向，覆盖 7 阶段 / 环境 / Key / resume
- `docs/builtin-tools.md`：追加 `shell_exec` / `tavily_search` / `remember_preference`
- 所有新文档同步英文镜像（`*.en.md`）

## Risks & Open Questions

1. **Tavily MCP 的 stdio server 真的存在且可靠吗？** 需要在实现阶段第一时间验证；若社区 server 质量不佳，回到 `tavily_search` 原生工具作为主路径，把 MCP 降级为 optional。
2. **PptxGenJS 在 Windows 路径的转义。** 模板文件路径通过 `os.path` 构造，统一用正斜杠；`cwd` 传 `outputs/<slug>/`，子进程内相对路径就行。
3. **LLM 输出幻觉字段** — slot schema 严格但 LLM 可能写成 string-of-json；在 `response_repair_policy` 里统一 decode + repair 一轮。
4. **memory 跨 session 的隐私** — 所有 memory 都落本地用户家目录；新增 `pptx-agent memory list / forget <id>` 子命令（0.4.1 增量，本期可先做 `list` 只读）。
5. **测试 questionary 交互** — 用 `questionary` 的 `Question.unsafe_ask` 在 pytest 下通过 `mocker.patch("questionary.select").return_value.ask.return_value = "choice"` mock。

## Implementation Order (供后续 plan 参考)

1. SDK 新 builtin：`shell_exec` → `tavily_search` → `markdown_memory` + `remember_preference` → `env_doctor` → `cli/wizard`（每项含测试）
2. 数据模型 + `project.json` 持久化
3. 7 个 agent 的 plugins + agent.json
4. cli 主入口 + 7 个 WizardStep
5. templates/ 下 5 个 JS 模板
6. skill 原样复制
7. 集成测试 + 文档 + 打包

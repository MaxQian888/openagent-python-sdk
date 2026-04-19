# PPTX Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a production-grade interactive CLI (`pptx-agent`) that drives a 7-stage pipeline (intent → env → research → outline → theme → slides → compile/QA) on top of the SDK, introducing 5 new SDK builtins along the way.

**Architecture:** Three-layer split. (1) SDK-level additions: `shell_exec` tool, `tavily_search` tool, `markdown_memory` memory + `remember_preference` tool, `env_doctor` utility, `cli/wizard` component. (2) App at `examples/pptx_generator/` with 7 agents in a single `agent.json`, pydantic state models, JSON persistence, and 7 Rich+questionary wizard steps. (3) Node/PptxGenJS renderer driven by `shell_exec`; PPT skill copied verbatim into `examples/pptx_generator/skills/`.

**Tech Stack:** Python 3.10+, pydantic v2, httpx, Rich, questionary, python-dotenv, PptxGenJS (Node), MarkItDown, Tavily (MCP + REST fallback), pytest + respx.

Spec reference: `docs/superpowers/specs/2026-04-18-pptx-agent-design.md`.

---

## Phase A — SDK Builtins

### Task 1: `shell_exec` builtin tool

**Files:**
- Create: `openagents/plugins/builtin/tool/shell_exec.py`
- Create: `tests/unit/test_shell_exec_tool.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_shell_exec_tool.py
from __future__ import annotations

import asyncio
import sys

import pytest

from openagents.plugins.builtin.tool.shell_exec import ShellExecTool


@pytest.mark.asyncio
async def test_runs_command_and_captures_output():
    tool = ShellExecTool(config={})
    result = await tool.invoke(
        {"command": [sys.executable, "-c", "print('hello')"]},
        context=None,
    )
    assert result["exit_code"] == 0
    assert result["stdout"].strip() == "hello"
    assert result["timed_out"] is False
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_times_out():
    tool = ShellExecTool(config={"default_timeout_ms": 200})
    result = await tool.invoke(
        {"command": [sys.executable, "-c", "import time; time.sleep(2)"]},
        context=None,
    )
    assert result["timed_out"] is True
    assert result["exit_code"] != 0


@pytest.mark.asyncio
async def test_allowlist_rejects_unlisted_command():
    tool = ShellExecTool(config={"command_allowlist": ["node"]})
    with pytest.raises(ValueError, match="not in allowlist"):
        await tool.invoke({"command": [sys.executable, "-c", "pass"]}, context=None)


@pytest.mark.asyncio
async def test_string_command_split():
    tool = ShellExecTool(config={})
    result = await tool.invoke(
        {"command": f"{sys.executable} -c \"print('ok')\""},
        context=None,
    )
    assert result["exit_code"] == 0
    assert "ok" in result["stdout"]


@pytest.mark.asyncio
async def test_truncates_large_output():
    tool = ShellExecTool(config={"capture_bytes": 10})
    result = await tool.invoke(
        {"command": [sys.executable, "-c", "print('x' * 1000)"]},
        context=None,
    )
    assert result["truncated"] is True
    assert len(result["stdout"]) <= 10


@pytest.mark.asyncio
async def test_env_passthrough_and_merge(monkeypatch):
    monkeypatch.setenv("FOO_PASS", "value_from_parent")
    monkeypatch.setenv("BAR_BLOCKED", "should_not_leak")
    tool = ShellExecTool(config={"env_passthrough": ["FOO_PASS"]})
    result = await tool.invoke(
        {
            "command": [
                sys.executable, "-c",
                "import os; print(os.environ.get('FOO_PASS','')); "
                "print(os.environ.get('BAR_BLOCKED',''))",
            ],
            "env": {"EXTRA": "via_invoke"},
        },
        context=None,
    )
    assert "value_from_parent" in result["stdout"]
    assert "should_not_leak" not in result["stdout"]
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_shell_exec_tool.py -v
```

Expected: `ModuleNotFoundError: No module named 'openagents.plugins.builtin.tool.shell_exec'`.

- [ ] **Step 3: Implement tool**

```python
# openagents/plugins/builtin/tool/shell_exec.py
from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any

from pydantic import BaseModel

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin
from openagents.interfaces.typed_config import TypedConfigPluginMixin


class ShellExecTool(TypedConfigPluginMixin, ToolPlugin):
    """Execute a process using explicit argv (no shell). Allowlist-aware.

    What:
        Async subprocess execution via ``asyncio.create_subprocess_exec`` (no
        shell). Captures stdout/stderr with configurable byte caps, timeout,
        and an argv[0] allowlist. Does not inherit full environment.
    Usage:
        ``{"id": "shell", "type": "shell_exec", "config": {
            "command_allowlist": ["node", "npx", "npm", "markitdown"],
            "env_passthrough": ["PATH", "HOME"],
            "default_timeout_ms": 120000}}``
    Depends on:
        asyncio stdlib only. Pair with a strict ``tool_executor``.
    """

    class Config(BaseModel):
        cwd: str | None = None
        env_passthrough: list[str] = []
        command_allowlist: list[str] | None = None
        default_timeout_ms: int = 60_000
        capture_bytes: int = 1_048_576

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})
        self._init_typed_config()

    def _resolve_argv(self, command: str | list[str]) -> list[str]:
        if isinstance(command, list):
            argv = [str(c) for c in command]
        else:
            argv = shlex.split(str(command))
        if not argv:
            raise ValueError("'command' resolved to empty argv")
        allow = self.cfg.command_allowlist
        if allow is not None and os.path.basename(argv[0]) not in allow and argv[0] not in allow:
            raise ValueError(f"command {argv[0]!r} not in allowlist {allow!r}")
        return argv

    def _resolve_env(self, extra: dict[str, str] | None) -> dict[str, str]:
        env: dict[str, str] = {}
        for key in self.cfg.env_passthrough:
            if key in os.environ:
                env[key] = os.environ[key]
        if extra:
            env.update({str(k): str(v) for k, v in extra.items()})
        return env

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        argv = self._resolve_argv(params.get("command", ""))
        cwd = params.get("cwd") or self.cfg.cwd
        timeout_ms = int(params.get("timeout_ms") or self.cfg.default_timeout_ms)
        env = self._resolve_env(params.get("env"))
        cap = int(self.cfg.capture_bytes)

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env or None,
        )
        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_ms / 1000.0
            )
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            stdout, stderr = await proc.communicate()

        truncated = len(stdout) > cap or len(stderr) > cap
        return {
            "exit_code": proc.returncode,
            "stdout": stdout[:cap].decode("utf-8", errors="replace"),
            "stderr": stderr[:cap].decode("utf-8", errors="replace"),
            "timed_out": timed_out,
            "truncated": truncated,
        }
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_shell_exec_tool.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/plugins/builtin/tool/shell_exec.py tests/unit/test_shell_exec_tool.py
rtk git commit -m "feat: add shell_exec builtin tool (allowlist-aware subprocess)"
```

---

### Task 2: `tavily_search` builtin tool

**Files:**
- Create: `openagents/plugins/builtin/tool/tavily_search.py`
- Create: `tests/unit/test_tavily_search_tool.py`
- Modify: `pyproject.toml` (dev group: add `respx`)

- [ ] **Step 1: Add respx to dev deps**

Edit `pyproject.toml` `dev` optional-dependencies:

```toml
dev = [
    "coverage[toml]>=7.6.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "respx>=0.21.1",
    "io-openagent-sdk[rich]",
]
```

Then:

```bash
uv sync
```

- [ ] **Step 2: Write failing tests**

```python
# tests/unit/test_tavily_search_tool.py
from __future__ import annotations

import pytest
import respx
from httpx import Response

from openagents.plugins.builtin.tool.tavily_search import TavilySearchTool


@pytest.mark.asyncio
@respx.mock
async def test_basic_search(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "secret")
    route = respx.post("https://api.tavily.com/search").mock(
        return_value=Response(
            200,
            json={
                "query": "openagents",
                "results": [
                    {"url": "https://x.example", "title": "X", "content": "snippet", "score": 0.9},
                ],
            },
        )
    )
    tool = TavilySearchTool(config={})
    result = await tool.invoke({"query": "openagents"}, context=None)
    assert route.called
    body = route.calls.last.request.content.decode()
    assert "openagents" in body
    assert "secret" in body
    assert result["query"] == "openagents"
    assert result["results"][0]["url"] == "https://x.example"


@pytest.mark.asyncio
async def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    tool = TavilySearchTool(config={})
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        await tool.invoke({"query": "x"}, context=None)


@pytest.mark.asyncio
@respx.mock
async def test_domain_filters_forwarded(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    route = respx.post("https://api.tavily.com/search").mock(
        return_value=Response(200, json={"query": "q", "results": []})
    )
    tool = TavilySearchTool(config={})
    await tool.invoke(
        {
            "query": "q",
            "include_domains": ["example.com"],
            "exclude_domains": ["bad.com"],
            "max_results": 7,
            "search_depth": "advanced",
        },
        context=None,
    )
    payload = route.calls.last.request.content.decode()
    assert "example.com" in payload
    assert "bad.com" in payload
    assert '"max_results":7' in payload.replace(" ", "")
    assert "advanced" in payload
```

- [ ] **Step 3: Run, expect fail**

```bash
uv run pytest tests/unit/test_tavily_search_tool.py -v
```

Expected: `ModuleNotFoundError: ... tavily_search`.

- [ ] **Step 4: Implement**

```python
# openagents/plugins/builtin/tool/tavily_search.py
from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin
from openagents.interfaces.typed_config import TypedConfigPluginMixin

_API_URL = "https://api.tavily.com/search"


class TavilySearchTool(TypedConfigPluginMixin, ToolPlugin):
    """REST-based Tavily search tool (MCP fallback).

    What:
        POSTs to Tavily's REST ``/search`` endpoint with the configured API
        key. Used when the Tavily MCP server is unavailable.
    Usage:
        ``{"id": "tavily", "type": "tavily_search"}``; invoke with
        ``{"query": "...", "max_results": 5}``.
    Depends on:
        ``httpx.AsyncClient``; key read from ``TAVILY_API_KEY`` env.
    """

    class Config(BaseModel):
        api_key_env: str = "TAVILY_API_KEY"
        default_max_results: int = 5
        default_search_depth: Literal["basic", "advanced"] = "basic"
        timeout_ms: int = 15_000

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})
        self._init_typed_config()

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        query = str(params.get("query") or "").strip()
        if not query:
            raise ValueError("'query' is required")

        api_key = os.environ.get(self.cfg.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"{self.cfg.api_key_env} is not set; cannot call Tavily"
            )

        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": int(params.get("max_results") or self.cfg.default_max_results),
            "search_depth": params.get("search_depth") or self.cfg.default_search_depth,
        }
        include = params.get("include_domains")
        exclude = params.get("exclude_domains")
        if include:
            payload["include_domains"] = list(include)
        if exclude:
            payload["exclude_domains"] = list(exclude)

        timeout = httpx.Timeout(self.cfg.timeout_ms / 1000.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return {
            "query": data.get("query", query),
            "results": data.get("results", []),
            "search_depth": payload["search_depth"],
        }
```

- [ ] **Step 5: Run, expect pass**

```bash
uv run pytest tests/unit/test_tavily_search_tool.py -v
```

- [ ] **Step 6: Commit**

```bash
rtk git add openagents/plugins/builtin/tool/tavily_search.py tests/unit/test_tavily_search_tool.py pyproject.toml uv.lock
rtk git commit -m "feat: add tavily_search builtin tool (MCP fallback)"
```

---

### Task 3: `markdown_memory` builtin + `remember_preference` tool

**Files:**
- Create: `openagents/plugins/builtin/memory/markdown_memory.py`
- Create: `openagents/plugins/builtin/tool/memory_tools.py`
- Create: `tests/unit/test_markdown_memory.py`
- Create: `tests/unit/test_remember_preference_tool.py`

- [ ] **Step 1: Write failing tests for memory**

```python
# tests/unit/test_markdown_memory.py
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from openagents.plugins.builtin.memory.markdown_memory import MarkdownMemory


def _ctx():
    return SimpleNamespace(
        state={},
        memory_view={},
        input_text="",
        tool_results=[],
    )


@pytest.mark.asyncio
async def test_inject_with_empty_dir(tmp_path):
    mem = MarkdownMemory(config={"memory_dir": str(tmp_path)})
    ctx = _ctx()
    await mem.inject(ctx)
    assert ctx.memory_view["user_goals"] == []
    assert ctx.memory_view["user_feedback"] == []


@pytest.mark.asyncio
async def test_capture_then_inject_roundtrip(tmp_path):
    mem = MarkdownMemory(config={"memory_dir": str(tmp_path)})
    mem.capture("user_feedback", "用 Arial 做英文正文", "用户 2026-04 明确要求")
    # capture writes immediately (no run needed)
    ctx = _ctx()
    await mem.inject(ctx)
    entries = ctx.memory_view["user_feedback"]
    assert len(entries) == 1
    assert "Arial" in entries[0]["rule"]
    assert (tmp_path / "MEMORY.md").exists()
    assert (tmp_path / "user_feedback.md").exists()


@pytest.mark.asyncio
async def test_writeback_drains_pending(tmp_path):
    mem = MarkdownMemory(config={"memory_dir": str(tmp_path)})
    ctx = _ctx()
    ctx.state["_pending_memory_writes"] = [
        {"category": "decisions", "rule": "palette=ocean", "reason": "user chose at stage 5"},
    ]
    await mem.writeback(ctx)
    assert ctx.state["_pending_memory_writes"] == []
    text = (tmp_path / "decisions.md").read_text(encoding="utf-8")
    assert "palette=ocean" in text


@pytest.mark.asyncio
async def test_unknown_category_falls_back_to_feedback(tmp_path):
    mem = MarkdownMemory(config={"memory_dir": str(tmp_path)})
    mem.capture("bogus_category", "rule X", "why")
    ctx = _ctx()
    await mem.inject(ctx)
    assert any("rule X" in e["rule"] for e in ctx.memory_view["user_feedback"])


@pytest.mark.asyncio
async def test_section_char_truncation(tmp_path):
    mem = MarkdownMemory(
        config={"memory_dir": str(tmp_path), "max_chars_per_section": 200},
    )
    for i in range(20):
        mem.capture("user_feedback", f"rule {i}" + "x" * 50, "why")
    ctx = _ctx()
    await mem.inject(ctx)
    entries = ctx.memory_view["user_feedback"]
    # Most recent entries kept; total chars ≤ 200
    total = sum(len(e["rule"]) + len(e["reason"]) for e in entries)
    assert total <= 220  # small slack for format
    assert any("rule 19" in e["rule"] for e in entries)


@pytest.mark.asyncio
async def test_retrieve_keyword(tmp_path):
    mem = MarkdownMemory(config={"memory_dir": str(tmp_path)})
    mem.capture("user_goals", "make short pitch decks", "")
    mem.capture("user_goals", "prefer English title case", "")
    hits = await mem.retrieve("pitch", _ctx())
    assert len(hits) == 1
    assert "pitch" in hits[0]["rule"]


@pytest.mark.asyncio
async def test_forget(tmp_path):
    mem = MarkdownMemory(config={"memory_dir": str(tmp_path)})
    entry_id = mem.capture("user_feedback", "rule A", "why")
    assert mem.forget(entry_id) is True
    ctx = _ctx()
    await mem.inject(ctx)
    assert ctx.memory_view["user_feedback"] == []
```

- [ ] **Step 2: Write failing tests for tool**

```python
# tests/unit/test_remember_preference_tool.py
from __future__ import annotations

from types import SimpleNamespace

import pytest

from openagents.plugins.builtin.tool.memory_tools import RememberPreferenceTool


def _ctx():
    return SimpleNamespace(state={})


@pytest.mark.asyncio
async def test_appends_to_pending():
    tool = RememberPreferenceTool(config={})
    ctx = _ctx()
    result = await tool.invoke(
        {"category": "user_feedback", "rule": "use Arial", "reason": "user said so"},
        ctx,
    )
    assert result["queued"] is True
    pending = ctx.state["_pending_memory_writes"]
    assert len(pending) == 1
    assert pending[0]["rule"] == "use Arial"


@pytest.mark.asyncio
async def test_multiple_calls_accumulate():
    tool = RememberPreferenceTool(config={})
    ctx = _ctx()
    await tool.invoke({"category": "user_goals", "rule": "R1", "reason": ""}, ctx)
    await tool.invoke({"category": "decisions", "rule": "R2", "reason": "x"}, ctx)
    assert len(ctx.state["_pending_memory_writes"]) == 2
```

- [ ] **Step 3: Run, expect fail**

```bash
uv run pytest tests/unit/test_markdown_memory.py tests/unit/test_remember_preference_tool.py -v
```

Expected: `ModuleNotFoundError` on both modules.

- [ ] **Step 4: Implement `markdown_memory.py`**

```python
# openagents/plugins/builtin/memory/markdown_memory.py
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from openagents.interfaces.capabilities import (
    MEMORY_INJECT,
    MEMORY_RETRIEVE,
    MEMORY_WRITEBACK,
)
from openagents.interfaces.memory import MemoryPlugin
from openagents.interfaces.typed_config import TypedConfigPluginMixin

_ENTRY_RE = re.compile(
    r"^### (?P<id>[\w-]+) · (?P<ts>[\dTZ:+\-.]+)\s*\n"
    r"\*\*Rule:\*\* (?P<rule>.*?)\n"
    r"\*\*Why:\*\* (?P<why>.*?)\n",
    re.MULTILINE | re.DOTALL,
)


class MarkdownMemory(TypedConfigPluginMixin, MemoryPlugin):
    """Human-readable, file-backed long-term memory.

    What:
        Persists user goals, feedback, decisions, references as markdown
        files under ``memory_dir``. Injects each section as a list of entries
        into ``context.memory_view``. Writeback reads
        ``context.state['_pending_memory_writes']`` and appends entries.
    Usage:
        ``{"type": "markdown_memory", "config": {
            "memory_dir": "~/.config/openagents/memory"}}``.
    Depends on:
        Plain filesystem IO; no network. Sections default to
        ``["user_goals", "user_feedback", "decisions", "references"]``.
    """

    class Config(BaseModel):
        memory_dir: str = "~/.config/openagents/memory"
        max_chars_per_section: int = 2000
        sections: list[str] = Field(
            default_factory=lambda: [
                "user_goals",
                "user_feedback",
                "decisions",
                "references",
            ]
        )
        enable_remember_tool: bool = True

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={MEMORY_INJECT, MEMORY_WRITEBACK, MEMORY_RETRIEVE},
        )
        self._init_typed_config()
        self._dir = Path(self.cfg.memory_dir).expanduser()
        self._dir.mkdir(parents=True, exist_ok=True)

    # ---- public API (app-side) -------------------------------------
    def capture(self, category: str, rule: str, reason: str) -> str:
        section = category if category in self.cfg.sections else "user_feedback"
        entry_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now(timezone.utc).isoformat()
        block = (
            f"### {entry_id} · {timestamp}\n"
            f"**Rule:** {rule}\n"
            f"**Why:** {reason or '(no reason given)'}\n\n"
        )
        path = self._dir / f"{section}.md"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(block)
        self._refresh_index()
        return entry_id

    def forget(self, entry_id: str) -> bool:
        for section in self.cfg.sections:
            path = self._dir / f"{section}.md"
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            new_content, count = re.subn(
                rf"### {re.escape(entry_id)} · .*?(?=\n### |\Z)",
                "",
                content,
                flags=re.DOTALL,
            )
            if count:
                path.write_text(new_content.lstrip(), encoding="utf-8")
                self._refresh_index()
                return True
        return False

    def list_entries(self, section: str) -> list[dict[str, Any]]:
        return self._parse(section)

    # ---- plugin lifecycle ------------------------------------------
    async def inject(self, context: Any) -> None:
        for section in self.cfg.sections:
            context.memory_view[section] = self._parse(
                section, max_chars=self.cfg.max_chars_per_section
            )

    async def writeback(self, context: Any) -> None:
        pending = context.state.get("_pending_memory_writes") or []
        if not pending:
            return
        for entry in pending:
            self.capture(
                category=entry.get("category", "user_feedback"),
                rule=str(entry.get("rule", "")),
                reason=str(entry.get("reason", "")),
            )
        context.state["_pending_memory_writes"] = []

    async def retrieve(self, query: str, context: Any) -> list[dict[str, Any]]:
        q = query.lower()
        out: list[dict[str, Any]] = []
        for section in self.cfg.sections:
            for entry in self._parse(section):
                if q in entry["rule"].lower() or q in entry["reason"].lower():
                    entry_copy = dict(entry)
                    entry_copy["section"] = section
                    out.append(entry_copy)
        return out[:20]

    # ---- helpers ----------------------------------------------------
    def _parse(self, section: str, *, max_chars: int | None = None) -> list[dict[str, Any]]:
        path = self._dir / f"{section}.md"
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        entries = [
            {"id": m.group("id"), "timestamp": m.group("ts"),
             "rule": m.group("rule").strip(),
             "reason": m.group("why").strip()}
            for m in _ENTRY_RE.finditer(content)
        ]
        if max_chars is None:
            return entries
        # keep most-recent entries within char budget
        kept: list[dict[str, Any]] = []
        total = 0
        for entry in reversed(entries):
            size = len(entry["rule"]) + len(entry["reason"])
            if total + size > max_chars and kept:
                break
            kept.append(entry)
            total += size
        kept.reverse()
        return kept

    def _refresh_index(self) -> None:
        lines = ["# Memory Index\n"]
        for section in self.cfg.sections:
            path = self._dir / f"{section}.md"
            count = len(self._parse(section)) if path.exists() else 0
            lines.append(f"- [{section}]({section}.md) — {count} entries")
        (self._dir / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 5: Add `MEMORY_RETRIEVE` capability if missing**

```bash
rtk grep "MEMORY_RETRIEVE" openagents/interfaces/capabilities.py
```

If not present, edit `openagents/interfaces/capabilities.py` and add:

```python
MEMORY_RETRIEVE = "memory.retrieve"
```

(The retrieve capability is already documented in `interfaces/memory.py` docstring; wiring the constant keeps capability sets complete.)

- [ ] **Step 6: Implement `remember_preference` tool**

```python
# openagents/plugins/builtin/tool/memory_tools.py
from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin


class RememberPreferenceTool(ToolPlugin):
    """Queue a preference for the paired MarkdownMemory to persist on writeback.

    What:
        Pushes ``{category, rule, reason}`` onto
        ``context.state['_pending_memory_writes']``. The companion
        ``MarkdownMemory`` plugin drains this list during writeback and
        appends each entry to the appropriate section file.
    Usage:
        ``{"id": "remember", "type": "remember_preference"}``; invoke with
        ``{"category": "user_feedback", "rule": "...", "reason": "..."}``.
    Depends on:
        Must be paired with ``markdown_memory`` in the agent's memory chain.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        category = str(params.get("category") or "user_feedback")
        rule = str(params.get("rule") or "").strip()
        reason = str(params.get("reason") or "").strip()
        if not rule:
            raise ValueError("'rule' is required")
        pending = context.state.setdefault("_pending_memory_writes", [])
        pending.append({"category": category, "rule": rule, "reason": reason})
        return {"queued": True, "count": len(pending)}
```

- [ ] **Step 7: Run, expect pass**

```bash
uv run pytest tests/unit/test_markdown_memory.py tests/unit/test_remember_preference_tool.py -v
```

- [ ] **Step 8: Commit**

```bash
rtk git add openagents/plugins/builtin/memory/markdown_memory.py openagents/plugins/builtin/tool/memory_tools.py openagents/interfaces/capabilities.py tests/unit/test_markdown_memory.py tests/unit/test_remember_preference_tool.py
rtk git commit -m "feat: add markdown_memory builtin + remember_preference tool"
```

---

### Task 4: `env_doctor` utility

**Files:**
- Create: `openagents/utils/env_doctor.py`
- Create: `tests/unit/test_env_doctor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_env_doctor.py
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from openagents.utils.env_doctor import (
    CheckStatus,
    CliBinaryCheck,
    EnvVarCheck,
    EnvironmentDoctor,
    NodeVersionCheck,
    PythonVersionCheck,
)


@pytest.mark.asyncio
async def test_python_version_ok():
    check = PythonVersionCheck(min_version="3.8")
    result = await check.check()
    assert result.status == CheckStatus.OK


@pytest.mark.asyncio
async def test_python_version_outdated():
    check = PythonVersionCheck(min_version="99.0")
    result = await check.check()
    assert result.status == CheckStatus.OUTDATED
    assert "3." in result.detail


@pytest.mark.asyncio
async def test_env_var_check_missing(monkeypatch):
    monkeypatch.delenv("FOO_X1", raising=False)
    check = EnvVarCheck(
        name="FOO_X1", required=True,
        description="my var", get_url="https://get.example",
    )
    result = await check.check()
    assert result.status == CheckStatus.MISSING
    assert result.get_url == "https://get.example"


@pytest.mark.asyncio
async def test_env_var_check_present(monkeypatch):
    monkeypatch.setenv("FOO_X2", "v")
    check = EnvVarCheck(name="FOO_X2", required=True, description="", get_url=None)
    result = await check.check()
    assert result.status == CheckStatus.OK


@pytest.mark.asyncio
async def test_cli_binary_check_missing(monkeypatch):
    # Fake binary that never resolves on PATH
    check = CliBinaryCheck(
        name="definitely-not-real-binary-xyz",
        install_hint="pip install xyz",
        get_url=None,
    )
    result = await check.check()
    assert result.status == CheckStatus.MISSING


@pytest.mark.asyncio
async def test_doctor_aggregates(monkeypatch):
    monkeypatch.setenv("Y1", "v")
    monkeypatch.delenv("Y2", raising=False)
    doctor = EnvironmentDoctor(
        checks=[
            EnvVarCheck(name="Y1", required=True, description="", get_url=None),
            EnvVarCheck(name="Y2", required=True, description="", get_url=None),
            EnvVarCheck(name="Y3", required=False, description="", get_url=None),
        ],
        dotenv_paths=[],
    )
    report = await doctor.run()
    assert "Y2" in report.missing_required
    assert "Y3" in report.missing_optional
    assert "Y1" not in report.missing_required


def test_persist_env_writes_dotenv(tmp_path):
    doctor = EnvironmentDoctor(checks=[], dotenv_paths=[tmp_path / ".env"])
    path = doctor.persist_env("TEST_KEY", "value with = and space", level="project")
    assert path == tmp_path / ".env"
    text = path.read_text(encoding="utf-8")
    assert "TEST_KEY=" in text
    assert "value with = and space" in text


def test_persist_env_overwrites_existing_key(tmp_path):
    p = tmp_path / ".env"
    p.write_text("TEST_KEY=old\nOTHER=keep\n", encoding="utf-8")
    doctor = EnvironmentDoctor(checks=[], dotenv_paths=[p])
    doctor.persist_env("TEST_KEY", "new", level="project")
    lines = p.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("TEST_KEY=new") for line in lines)
    assert any(line.startswith("OTHER=keep") for line in lines)
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_env_doctor.py -v
```

Expected: module not found.

- [ ] **Step 3: Implement utility**

```python
# openagents/utils/env_doctor.py
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel


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


class EnvironmentReport(BaseModel):
    checks: list[CheckResult]
    missing_required: list[str]
    missing_optional: list[str]
    auto_fixable: list[str]


class EnvironmentCheck(Protocol):
    name: str
    required: bool

    async def check(self) -> CheckResult: ...


@dataclass
class PythonVersionCheck:
    min_version: str = "3.10"
    name: str = "python"
    required: bool = True

    async def check(self) -> CheckResult:
        actual = f"{sys.version_info.major}.{sys.version_info.minor}"
        need = tuple(int(x) for x in self.min_version.split("."))
        have = (sys.version_info.major, sys.version_info.minor)
        if have >= need:
            return CheckResult(name=self.name, status=CheckStatus.OK, detail=actual)
        return CheckResult(
            name=self.name,
            status=CheckStatus.OUTDATED,
            detail=f"have {actual}, need ≥ {self.min_version}",
            fix_hint="Upgrade Python via your package manager or pyenv.",
        )


@dataclass
class NodeVersionCheck:
    min_version: str = "18"
    name: str = "node"
    required: bool = True

    async def check(self) -> CheckResult:
        try:
            out = subprocess.check_output(["node", "--version"], text=True, timeout=5).strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return CheckResult(
                name=self.name,
                status=CheckStatus.MISSING,
                detail="node not on PATH",
                fix_hint="Install Node.js ≥ 18",
                get_url="https://nodejs.org/",
            )
        m = re.match(r"v(\d+)", out)
        have = int(m.group(1)) if m else 0
        need = int(self.min_version)
        if have >= need:
            return CheckResult(name=self.name, status=CheckStatus.OK, detail=out)
        return CheckResult(
            name=self.name,
            status=CheckStatus.OUTDATED,
            detail=f"have {out}, need ≥ {self.min_version}",
            fix_hint="Upgrade Node.js",
            get_url="https://nodejs.org/",
        )


@dataclass
class NpmCheck:
    name: str = "npm"
    required: bool = True

    async def check(self) -> CheckResult:
        path = shutil.which("npm")
        if path:
            return CheckResult(name=self.name, status=CheckStatus.OK, detail=path)
        return CheckResult(
            name=self.name,
            status=CheckStatus.MISSING,
            detail="npm not on PATH",
            fix_hint="Install Node.js (ships with npm)",
            get_url="https://nodejs.org/",
        )


@dataclass
class CliBinaryCheck:
    name: str
    install_hint: str
    get_url: str | None = None
    required: bool = True

    async def check(self) -> CheckResult:
        path = shutil.which(self.name)
        if path:
            return CheckResult(name=self.name, status=CheckStatus.OK, detail=path)
        return CheckResult(
            name=self.name,
            status=CheckStatus.MISSING,
            detail=f"{self.name} not on PATH",
            fix_hint=self.install_hint,
            get_url=self.get_url,
        )


@dataclass
class EnvVarCheck:
    name: str
    required: bool
    description: str
    get_url: str | None

    async def check(self) -> CheckResult:
        if os.environ.get(self.name):
            return CheckResult(name=self.name, status=CheckStatus.OK, detail="set")
        return CheckResult(
            name=self.name,
            status=CheckStatus.MISSING,
            detail=self.description or "not set",
            fix_hint=f"export {self.name}=...",
            get_url=self.get_url,
        )


class EnvironmentDoctor:
    """Aggregates environment checks and guides interactive fixes."""

    def __init__(
        self,
        checks: list[EnvironmentCheck],
        dotenv_paths: list[Path],
    ) -> None:
        self._checks = checks
        self._dotenv_paths = [Path(p) for p in dotenv_paths]

    async def run(self) -> EnvironmentReport:
        results: list[CheckResult] = []
        missing_required: list[str] = []
        missing_optional: list[str] = []
        for check in self._checks:
            result = await check.check()
            results.append(result)
            if result.status in (CheckStatus.MISSING, CheckStatus.OUTDATED):
                if getattr(check, "required", True):
                    missing_required.append(check.name)
                else:
                    missing_optional.append(check.name)
        return EnvironmentReport(
            checks=results,
            missing_required=missing_required,
            missing_optional=missing_optional,
            auto_fixable=[],
        )

    def persist_env(
        self,
        key: str,
        value: str,
        level: Literal["user", "project"] = "project",
    ) -> Path:
        if not self._dotenv_paths:
            raise RuntimeError("no dotenv_paths configured")
        path = self._dotenv_paths[0] if level == "project" else self._dotenv_paths[-1]
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ[key] = value
        return path

    async def interactive_fix(self, report: EnvironmentReport, console: Any) -> EnvironmentReport:
        """App-side UI glue; deliberately left minimal here so Wizard can own the UI."""
        return report
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_env_doctor.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/utils/env_doctor.py tests/unit/test_env_doctor.py
rtk git commit -m "feat: add env_doctor utility with built-in checks"
```

---

### Task 5: `cli/wizard` Rich+questionary component

**Files:**
- Create: `openagents/cli/wizard.py`
- Create: `tests/unit/test_cli_wizard.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_cli_wizard.py
from __future__ import annotations

from types import SimpleNamespace

import pytest

from openagents.cli.wizard import StepResult, Wizard


class _DummyStep:
    def __init__(self, title: str, result_status: str):
        self.title = title
        self.description = ""
        self._status = result_status
        self.called = False

    async def render(self, console, project):
        self.called = True
        return StepResult(status=self._status, data={"title": self.title})


@pytest.mark.asyncio
async def test_wizard_runs_all_steps_on_happy_path():
    steps = [_DummyStep("a", "completed"), _DummyStep("b", "completed")]
    project = SimpleNamespace(stage="a")
    wizard = Wizard(steps=steps, project=project)
    outcome = await wizard.run()
    assert outcome == "completed"
    assert all(s.called for s in steps)


@pytest.mark.asyncio
async def test_wizard_stops_on_abort():
    steps = [_DummyStep("a", "aborted"), _DummyStep("b", "completed")]
    project = SimpleNamespace(stage="a")
    wizard = Wizard(steps=steps, project=project)
    outcome = await wizard.run()
    assert outcome == "aborted"
    assert steps[0].called is True
    assert steps[1].called is False


@pytest.mark.asyncio
async def test_wizard_resume_skips_earlier_steps():
    steps = [_DummyStep("a", "completed"), _DummyStep("b", "completed")]
    project = SimpleNamespace(stage="b")
    wizard = Wizard(steps=steps, project=project)
    outcome = await wizard.resume(from_step="b")
    assert outcome == "completed"
    assert steps[0].called is False
    assert steps[1].called is True


@pytest.mark.asyncio
async def test_wizard_retry_reruns_current_step():
    class _RetryThenOk:
        def __init__(self):
            self.title = "x"
            self.description = ""
            self.calls = 0

        async def render(self, console, project):
            self.calls += 1
            return StepResult(status="retry" if self.calls == 1 else "completed")

    step = _RetryThenOk()
    project = SimpleNamespace(stage="x")
    wizard = Wizard(steps=[step], project=project)
    outcome = await wizard.run()
    assert outcome == "completed"
    assert step.calls == 2
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_cli_wizard.py -v
```

- [ ] **Step 3: Implement**

```python
# openagents/cli/wizard.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:  # pragma: no cover
    Console = object  # type: ignore[assignment,misc]
    Panel = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]

try:
    import questionary
except ImportError:  # pragma: no cover
    questionary = None  # type: ignore[assignment]


@dataclass
class StepResult:
    status: Literal["completed", "skipped", "aborted", "retry"]
    data: Any = None


class WizardStep(Protocol):
    title: str
    description: str

    async def render(self, console: Any, project: Any) -> StepResult: ...


class Wizard:
    """Drive a sequence of WizardSteps with Rich layout and optional questionary prompts.

    What:
        Iterates ``steps`` in order, calling ``render(console, project)`` on
        each and branching on the returned :class:`StepResult`. ``resume``
        starts from a named step. UI helpers (``panel``, ``confirm``,
        ``select``, ``multi_select``, ``password``, ``text``,
        ``progress``, ``live_log``) wrap Rich and questionary so steps
        don't import them directly.
    """

    def __init__(
        self,
        steps: list[WizardStep],
        project: Any,
        layout: Literal["sidebar", "linear"] = "sidebar",
        console: Any = None,
    ):
        self._steps = list(steps)
        self._project = project
        self._layout = layout
        self._console = console or (Console() if Console is not object else None)

    async def run(self) -> Literal["completed", "aborted"]:
        i = 0
        while i < len(self._steps):
            step = self._steps[i]
            result = await step.render(self._console, self._project)
            if result.status == "aborted":
                return "aborted"
            if result.status == "retry":
                continue
            i += 1
        return "completed"

    async def resume(self, from_step: str) -> Literal["completed", "aborted"]:
        skipped = [s for s in self._steps if getattr(s, "title", None) != from_step]
        # advance until title matches
        start = 0
        for i, step in enumerate(self._steps):
            if getattr(step, "title", None) == from_step:
                start = i
                break
        self._steps = self._steps[start:]
        _ = skipped  # placate linters
        return await self.run()

    # ---- UI helpers (thin; easy to mock in tests) -------------------
    @staticmethod
    def panel(title: str, body: str) -> Any:
        return Panel(body, title=title) if Panel is not None else None

    @staticmethod
    async def confirm(prompt: str, default: bool = True) -> bool:
        if questionary is None:
            return default
        return bool(await questionary.confirm(prompt, default=default).ask_async())

    @staticmethod
    async def select(prompt: str, choices: list[str], default: str | None = None) -> str:
        if questionary is None:
            return default or choices[0]
        return str(await questionary.select(prompt, choices=choices, default=default).ask_async())

    @staticmethod
    async def multi_select(prompt: str, choices: list[str], min_selected: int = 0) -> list[str]:
        if questionary is None:
            return list(choices) if min_selected else []
        picked = await questionary.checkbox(prompt, choices=choices).ask_async()
        return list(picked or [])

    @staticmethod
    async def password(prompt: str) -> str:
        if questionary is None:
            return ""
        return str(await questionary.password(prompt).ask_async() or "")

    @staticmethod
    async def text(prompt: str, default: str | None = None) -> str:
        if questionary is None:
            return default or ""
        return str(await questionary.text(prompt, default=default or "").ask_async() or "")
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_cli_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/cli/wizard.py tests/unit/test_cli_wizard.py
rtk git commit -m "feat: add reusable Wizard component for Rich+questionary CLIs"
```

---

### Task 6: Register new builtins + update pyproject

**Files:**
- Modify: `openagents/plugins/registry.py`
- Modify: `openagents/plugins/builtin/tool/__init__.py` (if exports matter)
- Modify: `pyproject.toml` (add `pptx` optional-deps + bump version)
- Modify: `CHANGELOG.md` (add 0.4.0 stub; final updates come in Task 27)

- [ ] **Step 1: Register builtins in `registry.py`**

Find the imports block and add:

```python
from openagents.plugins.builtin.memory.markdown_memory import MarkdownMemory
from openagents.plugins.builtin.tool.memory_tools import RememberPreferenceTool
from openagents.plugins.builtin.tool.shell_exec import ShellExecTool
from openagents.plugins.builtin.tool.tavily_search import TavilySearchTool
```

Find the builtin registration table (look for where e.g. `"buffer": BufferMemory` and `"http_request": HttpRequestTool` get mapped) and add:

- memory: `"markdown_memory": MarkdownMemory`
- tool: `"shell_exec": ShellExecTool`, `"tavily_search": TavilySearchTool`, `"remember_preference": RememberPreferenceTool`

- [ ] **Step 2: Write a registry smoke test**

```python
# tests/unit/test_registry_new_builtins.py
import pytest

from openagents.plugins.loader import resolve_plugin


@pytest.mark.parametrize("kind,type_name", [
    ("memory", "markdown_memory"),
    ("tool", "shell_exec"),
    ("tool", "tavily_search"),
    ("tool", "remember_preference"),
])
def test_registered(kind, type_name, tmp_path):
    cfg = {"type": type_name, "config": {}}
    if type_name == "markdown_memory":
        cfg["config"] = {"memory_dir": str(tmp_path)}
    plugin = resolve_plugin(kind=kind, ref=cfg)
    assert plugin is not None
```

(If `resolve_plugin` is named differently, check `openagents/plugins/loader.py` and adjust.)

- [ ] **Step 3: Update pyproject.toml**

Add new optional-dependencies group and bump version:

```toml
[project]
name = "io-openagent-sdk"
version = "0.4.0"
# ... unchanged ...

[project.optional-dependencies]
# ... existing groups ...
pptx = [
  "io-openagent-sdk[rich,mcp]",
  "questionary>=2.0.1",
  "python-dotenv>=1.0",
  "httpx>=0.27.0",
]

[project.scripts]
openagents = "openagents.cli.main:main"
pptx-agent = "examples.pptx_generator.cli:main"
```

Also append `"io-openagent-sdk[pptx]"` to the `all` group.

- [ ] **Step 4: Sync + run full suite**

```bash
uv sync
uv run pytest -q
```

All tests must pass; coverage ≥ 92%.

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/plugins/registry.py pyproject.toml uv.lock tests/unit/test_registry_new_builtins.py
rtk git commit -m "chore: register new builtins and add pptx optional-deps (0.4.0)"
```

---

## Phase B — App Scaffolding

### Task 7: `examples/pptx_generator/` scaffold and state models

**Files:**
- Create: `examples/pptx_generator/__init__.py` (empty)
- Create: `examples/pptx_generator/app/__init__.py` (empty)
- Create: `examples/pptx_generator/state.py`
- Create: `examples/pptx_generator/README.md`
- Create: `tests/unit/test_pptx_state.py`

- [ ] **Step 1: Write failing tests for state models**

```python
# tests/unit/test_pptx_state.py
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from examples.pptx_generator.state import (
    DeckProject,
    IntentReport,
    Palette,
    SlideIR,
    SlideOutline,
    SlideSpec,
    ThemeSelection,
)


def test_intent_report_validates_purpose():
    with pytest.raises(ValidationError):
        IntentReport(
            topic="t", audience="a", purpose="bogus", tone="formal",
            slide_count_hint=5, required_sections=[], visuals_hint=[],
            research_queries=[], language="zh",
        )


def test_slide_count_bounds():
    with pytest.raises(ValidationError):
        IntentReport(
            topic="t", audience="a", purpose="pitch", tone="formal",
            slide_count_hint=25, required_sections=[], visuals_hint=[],
            research_queries=[], language="zh",
        )


def test_palette_hex_no_hash():
    with pytest.raises(ValidationError):
        Palette(primary="#123456", secondary="aabbcc",
                accent="aabbcc", light="aabbcc", bg="aabbcc")


def test_deck_project_minimum():
    p = DeckProject(slug="x", created_at=datetime.now(timezone.utc), stage="intent")
    assert p.slides == []
    assert p.intent is None


def test_slide_ir_freeform_requires_js():
    with pytest.raises(ValidationError):
        SlideIR(index=1, type="freeform", slots={}, freeform_js=None,
                generated_at=datetime.now(timezone.utc))


def test_slide_outline_indexes_unique():
    outline = SlideOutline(slides=[
        SlideSpec(index=1, type="cover", title="T", key_points=[], sources_cited=[]),
        SlideSpec(index=2, type="content", title="T", key_points=[], sources_cited=[]),
    ])
    assert [s.index for s in outline.slides] == [1, 2]
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_pptx_state.py -v
```

- [ ] **Step 3: Implement state models**

```python
# examples/pptx_generator/state.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from openagents.utils.env_doctor import EnvironmentReport

HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


class IntentReport(BaseModel):
    topic: str
    audience: str
    purpose: Literal["pitch", "report", "teaching", "announcement", "other"]
    tone: Literal["formal", "casual", "energetic", "minimalist"]
    slide_count_hint: int = Field(ge=3, le=20)
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
    queries_executed: list[str] = []
    sources: list[Source] = []
    key_facts: list[str] = []
    caveats: list[str] = []


class SlideSpec(BaseModel):
    index: int = Field(ge=1)
    type: Literal["cover", "agenda", "content", "transition", "closing", "freeform"]
    title: str
    key_points: list[str] = []
    sources_cited: list[int] = []


class SlideOutline(BaseModel):
    slides: list[SlideSpec]


class Palette(BaseModel):
    primary: str
    secondary: str
    accent: str
    light: str
    bg: str

    @field_validator("primary", "secondary", "accent", "light", "bg")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("palette colors must be 6-digit hex without '#'")
        return v


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
    slots: dict[str, Any]
    freeform_js: str | None = None
    generated_at: datetime

    @model_validator(mode="after")
    def _freeform_requires_js(self) -> "SlideIR":
        if self.type == "freeform" and not self.freeform_js:
            raise ValueError("freeform SlideIR requires freeform_js")
        return self


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
    env_report: EnvironmentReport | None = None
    last_error: str | None = None
```

- [ ] **Step 4: Write minimal README stub**

```markdown
<!-- examples/pptx_generator/README.md -->
# pptx-agent

Interactive CLI that drives a 7-stage PPT generation pipeline on the openagents SDK.

See the design spec: `docs/superpowers/specs/2026-04-18-pptx-agent-design.md`.
See the user CLI guide (wip): `docs/pptx-agent-cli.md`.
```

- [ ] **Step 5: Run, expect pass**

```bash
uv run pytest tests/unit/test_pptx_state.py -v
```

- [ ] **Step 6: Commit**

```bash
rtk git add examples/pptx_generator/ tests/unit/test_pptx_state.py
rtk git commit -m "feat(pptx): scaffold example app and state models"
```

---

### Task 8: `DeckProject` persistence with atomic write + backup

**Files:**
- Create: `examples/pptx_generator/persistence.py`
- Create: `tests/unit/test_pptx_persistence.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_pptx_persistence.py
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from examples.pptx_generator.persistence import (
    load_project,
    save_project,
    project_path,
    backup_path,
)
from examples.pptx_generator.state import DeckProject


def _mk(slug: str) -> DeckProject:
    return DeckProject(slug=slug, created_at=datetime.now(timezone.utc), stage="intent")


def test_save_and_load_roundtrip(tmp_path):
    p = _mk("demo")
    save_project(p, root=tmp_path)
    loaded = load_project("demo", root=tmp_path)
    assert loaded.slug == "demo"
    assert loaded.stage == "intent"


def test_save_creates_backup(tmp_path):
    p = _mk("demo")
    save_project(p, root=tmp_path)
    p.stage = "env"
    save_project(p, root=tmp_path)
    assert backup_path("demo", root=tmp_path).exists()


def test_corrupt_load_raises(tmp_path):
    path = project_path("demo", root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_project("demo", root=tmp_path)


def test_atomic_write_on_crash(tmp_path, monkeypatch):
    # simulate os.replace failure mid-write by patching os.replace
    import os
    original_replace = os.replace
    calls = {"n": 0}
    def fake_replace(src, dst):
        calls["n"] += 1
        raise OSError("boom")
    monkeypatch.setattr(os, "replace", fake_replace)
    p = _mk("demo")
    with pytest.raises(OSError):
        save_project(p, root=tmp_path)
    monkeypatch.setattr(os, "replace", original_replace)
    assert not project_path("demo", root=tmp_path).exists()
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_pptx_persistence.py -v
```

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/persistence.py
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .state import DeckProject


def project_path(slug: str, *, root: Path) -> Path:
    return Path(root) / slug / "project.json"


def backup_path(slug: str, *, root: Path) -> Path:
    return Path(root) / slug / "project.json.bak"


def load_project(slug: str, *, root: Path) -> DeckProject:
    path = project_path(slug, root=root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"project.json at {path} is corrupt: {exc}") from exc
    return DeckProject.model_validate(data)


def save_project(project: DeckProject, *, root: Path) -> Path:
    path = project_path(project.slug, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, backup_path(project.slug, root=root))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_pptx_persistence.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/persistence.py tests/unit/test_pptx_persistence.py
rtk git commit -m "feat(pptx): atomic project.json persistence with backup"
```

---

### Task 9: Copy pptx-generator skill + register 5 JS templates

**Files:**
- Create: `examples/pptx_generator/skills/pptx-generator/` (via filesystem copy from `D:/Project/skills-test/pptx-generator`)
- Create: `examples/pptx_generator/templates/cover.js`
- Create: `examples/pptx_generator/templates/agenda.js`
- Create: `examples/pptx_generator/templates/content.js`
- Create: `examples/pptx_generator/templates/transition.js`
- Create: `examples/pptx_generator/templates/closing.js`
- Create: `tests/unit/test_pptx_templates.py`

- [ ] **Step 1: Copy skill**

```bash
mkdir -p examples/pptx_generator/skills
cp -r "D:/Project/skills-test/pptx-generator" examples/pptx_generator/skills/pptx-generator
# remove vendored node_modules and lockfiles to keep the repo clean
rm -rf examples/pptx_generator/skills/pptx-generator/nova-code-2-launch/node_modules
rm -rf examples/pptx_generator/skills/pptx-generator/smoke-test/node_modules
```

Verify:

```bash
rtk ls examples/pptx_generator/skills/pptx-generator
```

Expected to see: `SKILL.md`, `references/`, `agents/`, and the two demo sub-projects without `node_modules/`.

- [ ] **Step 2: Write failing template-smoke test**

```python
# tests/unit/test_pptx_templates.py
from pathlib import Path

TEMPLATE_DIR = Path("examples/pptx_generator/templates")
TEMPLATE_NAMES = ["cover", "agenda", "content", "transition", "closing"]


def test_templates_exist():
    for name in TEMPLATE_NAMES:
        assert (TEMPLATE_DIR / f"{name}.js").exists(), f"missing {name}.js"


def test_templates_export_createSlide():
    for name in TEMPLATE_NAMES:
        text = (TEMPLATE_DIR / f"{name}.js").read_text(encoding="utf-8")
        assert "createSlide" in text
        assert "module.exports" in text


def test_cover_consumes_title_slot():
    text = (TEMPLATE_DIR / "cover.js").read_text(encoding="utf-8")
    assert "slots.title" in text


def test_content_supports_block_kinds():
    text = (TEMPLATE_DIR / "content.js").read_text(encoding="utf-8")
    for kind in ("bullets", "two_column", "callout"):
        assert kind in text
```

- [ ] **Step 3: Run, expect fail**

- [ ] **Step 4: Implement `cover.js`**

```javascript
// examples/pptx_generator/templates/cover.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  slide.addText(slots.title, {
    x: 0.5, y: 2, w: 9, h: 1.2,
    fontSize: 48, fontFace: "Arial",
    color: theme.primary, bold: true, align: "center",
  });

  if (slots.subtitle) {
    slide.addText(slots.subtitle, {
      x: 0.5, y: 3.2, w: 9, h: 0.6,
      fontSize: 20, fontFace: "Arial",
      color: theme.secondary, align: "center",
    });
  }

  if (slots.author || slots.date) {
    slide.addText(`${slots.author || ""}  ${slots.date || ""}`.trim(), {
      x: 0.5, y: 4.8, w: 9, h: 0.35,
      fontSize: 12, fontFace: "Arial",
      color: theme.accent, align: "center",
    });
  }

  return slide;
}

module.exports = { createSlide };
```

- [ ] **Step 5: Implement `agenda.js`**

```javascript
// examples/pptx_generator/templates/agenda.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  slide.addText(slots.title, {
    x: 0.5, y: 0.4, w: 9, h: 0.7,
    fontSize: 32, fontFace: "Arial",
    color: theme.primary, bold: true,
  });

  const items = slots.items || [];
  items.forEach((it, i) => {
    slide.addShape(pres.shapes.OVAL, {
      x: 0.6, y: 1.3 + i * 0.6, w: 0.35, h: 0.35,
      fill: { color: theme.accent },
    });
    slide.addText(String(i + 1), {
      x: 0.6, y: 1.3 + i * 0.6, w: 0.35, h: 0.35,
      fontSize: 12, fontFace: "Arial", color: "FFFFFF",
      bold: true, align: "center", valign: "middle",
    });
    slide.addText(it.label, {
      x: 1.1, y: 1.3 + i * 0.6, w: 7.5, h: 0.35,
      fontSize: 18, fontFace: "Arial", color: theme.primary,
      valign: "middle",
    });
    if (it.sub) {
      slide.addText(it.sub, {
        x: 1.1, y: 1.6 + i * 0.6, w: 7.5, h: 0.25,
        fontSize: 12, fontFace: "Arial", color: theme.secondary,
      });
    }
  });

  return slide;
}

module.exports = { createSlide };
```

- [ ] **Step 6: Implement `content.js`**

```javascript
// examples/pptx_generator/templates/content.js
function renderBlock(slide, theme, block, y) {
  if (block.kind === "bullets") {
    slide.addText(block.items.map((t) => ({ text: t, options: { bullet: true } })), {
      x: 0.6, y, w: 8.8, h: 3,
      fontSize: 16, fontFace: "Arial", color: theme.primary,
    });
    return y + 3.2;
  }
  if (block.kind === "two_column") {
    const col = (items, x) =>
      slide.addText(items.map((t) => ({ text: t, options: { bullet: true } })), {
        x, y, w: 4.2, h: 3,
        fontSize: 14, fontFace: "Arial", color: theme.primary,
      });
    col(block.left_items, 0.6);
    col(block.right_items, 5.2);
    return y + 3.2;
  }
  if (block.kind === "callout") {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.6, y, w: 8.8, h: 1.0,
      fill: { color: theme.accent }, rectRadius: 0.15,
    });
    slide.addText(block.text, {
      x: 0.8, y, w: 8.4, h: 1.0,
      fontSize: 16, fontFace: "Arial", color: "FFFFFF",
      valign: "middle",
    });
    return y + 1.2;
  }
  return y;
}

function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };
  slide.addText(slots.title, {
    x: 0.5, y: 0.4, w: 9, h: 0.7,
    fontSize: 28, fontFace: "Arial",
    color: theme.primary, bold: true,
  });
  let y = 1.3;
  (slots.body_blocks || []).forEach((b) => {
    y = renderBlock(slide, theme, b, y);
  });
  return slide;
}

module.exports = { createSlide };
```

- [ ] **Step 7: Implement `transition.js`**

```javascript
// examples/pptx_generator/templates/transition.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.primary };

  slide.addText(String(slots.section_number), {
    x: 0.5, y: 1.6, w: 9, h: 1.5,
    fontSize: 96, fontFace: "Arial",
    color: theme.light, bold: true, align: "center",
  });
  slide.addText(slots.section_title, {
    x: 0.5, y: 3.2, w: 9, h: 1.0,
    fontSize: 36, fontFace: "Arial",
    color: theme.bg, bold: true, align: "center",
  });
  if (slots.subtitle) {
    slide.addText(slots.subtitle, {
      x: 0.5, y: 4.3, w: 9, h: 0.5,
      fontSize: 16, fontFace: "Arial",
      color: theme.light, align: "center",
    });
  }
  return slide;
}

module.exports = { createSlide };
```

- [ ] **Step 8: Implement `closing.js`**

```javascript
// examples/pptx_generator/templates/closing.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  slide.addText(slots.title, {
    x: 0.5, y: 2.0, w: 9, h: 1.0,
    fontSize: 44, fontFace: "Arial",
    color: theme.primary, bold: true, align: "center",
  });
  if (slots.call_to_action) {
    slide.addText(slots.call_to_action, {
      x: 0.5, y: 3.2, w: 9, h: 0.7,
      fontSize: 22, fontFace: "Arial",
      color: theme.accent, align: "center",
    });
  }
  if (slots.contact) {
    slide.addText(slots.contact, {
      x: 0.5, y: 4.2, w: 9, h: 0.5,
      fontSize: 14, fontFace: "Arial",
      color: theme.secondary, align: "center",
    });
  }
  return slide;
}

module.exports = { createSlide };
```

- [ ] **Step 9: Run, expect pass**

```bash
uv run pytest tests/unit/test_pptx_templates.py -v
```

- [ ] **Step 10: Commit**

```bash
rtk git add examples/pptx_generator/skills examples/pptx_generator/templates tests/unit/test_pptx_templates.py
rtk git commit -m "feat(pptx): vendor skill references and 5 JS slide templates"
```

---

### Task 10: `agent.json` with 7 agents + shared memory chain

**Files:**
- Create: `examples/pptx_generator/agent.json`
- Create: `tests/unit/test_pptx_agent_config.py`

- [ ] **Step 1: Write failing config smoke test**

```python
# tests/unit/test_pptx_agent_config.py
from pathlib import Path

from openagents.config.loader import load_config


def test_agent_json_loads():
    cfg = load_config(Path("examples/pptx_generator/agent.json"))
    agent_ids = {a.id for a in cfg.agents}
    assert agent_ids == {
        "intent-analyst", "research-agent", "outliner",
        "theme-selector", "slide-generator",
    }


def test_shared_memory_is_chain_with_markdown():
    cfg = load_config(Path("examples/pptx_generator/agent.json"))
    for agent in cfg.agents:
        mem = agent.memory
        assert mem.type == "chain"
        mems = mem.config["memories"]
        assert any(m["type"] == "markdown_memory" for m in mems)
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_pptx_agent_config.py -v
```

- [ ] **Step 3: Implement config**

Only LLM-driven stages get agents (5 of the 7). Env-doctor and compile-qa are CLI-local.

```json
{
  "version": "1.0",
  "logging": {
    "auto_configure": true,
    "pretty": true,
    "level": "INFO",
    "include_prefixes": ["openagents", "examples.pptx_generator"],
    "redact_keys": ["api_key", "authorization", "token", "secret", "password"]
  },
  "events": {
    "type": "rich_console",
    "config": { "inner": { "type": "async" }, "show_payload": false, "stream": "stderr" }
  },
  "runtime": {
    "type": "default",
    "config": { "tool_executor": { "type": "safe", "config": { "default_timeout_ms": 30000 } } }
  },
  "shared_memory": {
    "type": "chain",
    "config": {
      "memories": [
        { "type": "window_buffer", "config": { "window_size": 12 } },
        {
          "type": "markdown_memory",
          "config": { "memory_dir": "~/.config/pptx-agent/memory" }
        }
      ]
    }
  },
  "agents": [
    {
      "id": "intent-analyst",
      "name": "Intent Analyst",
      "memory": { "$ref": "#/shared_memory" },
      "pattern": {
        "impl": "examples.pptx_generator.app.plugins.IntentAnalystPattern",
        "config": { "max_steps": 3 }
      },
      "context_assembler": { "type": "truncating", "config": { "max_messages": 8 } },
      "llm": {
        "provider": "anthropic",
        "api_base": "${LLM_API_BASE}",
        "api_key_env": "LLM_API_KEY",
        "model": "${LLM_MODEL}",
        "temperature": 0.3,
        "max_tokens": 1500,
        "timeout_ms": 60000
      },
      "tools": [
        { "id": "remember", "type": "remember_preference" }
      ]
    },
    {
      "id": "research-agent",
      "name": "Research Agent",
      "memory": { "$ref": "#/shared_memory" },
      "pattern": {
        "impl": "examples.pptx_generator.app.plugins.ResearchPattern",
        "config": { "max_steps": 6 }
      },
      "context_assembler": { "type": "truncating", "config": { "max_messages": 12 } },
      "llm": {
        "provider": "anthropic",
        "api_base": "${LLM_API_BASE}",
        "api_key_env": "LLM_API_KEY",
        "model": "${LLM_MODEL}",
        "temperature": 0.2,
        "max_tokens": 2000,
        "timeout_ms": 60000
      },
      "tools": [
        { "id": "tavily_mcp", "type": "mcp", "config": {
            "command": "npx", "args": ["-y", "tavily-mcp@latest"],
            "env": { "TAVILY_API_KEY": "${TAVILY_API_KEY}" }
        }},
        { "id": "tavily_fallback", "type": "tavily_search" },
        { "id": "http", "type": "http_request" },
        { "id": "remember", "type": "remember_preference" }
      ]
    },
    {
      "id": "outliner",
      "name": "Outliner",
      "memory": { "$ref": "#/shared_memory" },
      "pattern": {
        "impl": "examples.pptx_generator.app.plugins.OutlinePattern",
        "config": { "max_steps": 3 }
      },
      "context_assembler": { "type": "truncating", "config": { "max_messages": 8 } },
      "llm": {
        "provider": "anthropic",
        "api_base": "${LLM_API_BASE}",
        "api_key_env": "LLM_API_KEY",
        "model": "${LLM_MODEL}",
        "temperature": 0.4,
        "max_tokens": 2500,
        "timeout_ms": 60000
      },
      "tools": []
    },
    {
      "id": "theme-selector",
      "name": "Theme Selector",
      "memory": { "$ref": "#/shared_memory" },
      "pattern": {
        "impl": "examples.pptx_generator.app.plugins.ThemePattern",
        "config": { "max_steps": 2 }
      },
      "context_assembler": { "type": "truncating", "config": { "max_messages": 6 } },
      "llm": {
        "provider": "anthropic",
        "api_base": "${LLM_API_BASE}",
        "api_key_env": "LLM_API_KEY",
        "model": "${LLM_MODEL}",
        "temperature": 0.2,
        "max_tokens": 1000,
        "timeout_ms": 60000
      },
      "tools": []
    },
    {
      "id": "slide-generator",
      "name": "Slide Generator",
      "memory": { "$ref": "#/shared_memory" },
      "pattern": {
        "impl": "examples.pptx_generator.app.plugins.SlideGenPattern",
        "config": { "max_steps": 2, "max_retries": 2 }
      },
      "context_assembler": { "type": "truncating", "config": { "max_messages": 6 } },
      "llm": {
        "provider": "anthropic",
        "api_base": "${LLM_API_BASE}",
        "api_key_env": "LLM_API_KEY",
        "model": "${LLM_MODEL}",
        "temperature": 0.3,
        "max_tokens": 2000,
        "timeout_ms": 60000
      },
      "tools": [
        { "id": "remember", "type": "remember_preference" }
      ]
    }
  ]
}
```

- [ ] **Step 4: Verify config loader resolves `$ref` OR replace with literal copies**

Run:

```bash
uv run pytest tests/unit/test_pptx_agent_config.py -v
```

If the config loader does NOT support `$ref`, inline the `shared_memory` block into each agent's `memory` field. Inspect `openagents/config/loader.py` and `config/schema.py` briefly:

```bash
rtk grep -n "ref" openagents/config/
```

If `$ref` is not supported, replace each `{"$ref": "#/shared_memory"}` with the literal chain config; add a top-level comment in README noting the duplication is required until the SDK supports refs (tracked as follow-up).

- [ ] **Step 5: Run, expect pass**

- [ ] **Step 6: Commit**

```bash
rtk git add examples/pptx_generator/agent.json tests/unit/test_pptx_agent_config.py
rtk git commit -m "feat(pptx): agent.json declaring 5 LLM-driven agents"
```

---

## Phase C — Agent Plugins

### Task 11: `IntentAnalystPattern` + context_assembler wiring

**Files:**
- Create: `examples/pptx_generator/app/plugins.py` (this task starts it)
- Create: `examples/pptx_generator/app/protocols.py` (shared types if needed)
- Create: `tests/unit/test_intent_analyst.py`

- [ ] **Step 1: Write failing pattern test**

```python
# tests/unit/test_intent_analyst.py
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.app.plugins import IntentAnalystPattern
from examples.pptx_generator.state import IntentReport


class _FakeLLM:
    def __init__(self, response: str):
        self._response = response
        self.complete = AsyncMock(return_value=SimpleNamespace(content=response, tool_calls=[]))


def _ctx_with(llm_response: str):
    context = SimpleNamespace(
        input_text="Make me a 6-slide pitch for our new AI backup tool to VC investors.",
        memory_view={"user_goals": [], "user_feedback": []},
        tool_results=[],
        state={},
        assembly_metadata={},
        llm=_FakeLLM(llm_response),
    )
    return context


@pytest.mark.asyncio
async def test_intent_produces_valid_report():
    payload = json.dumps({
        "topic": "AI backup tool",
        "audience": "VC investors",
        "purpose": "pitch",
        "tone": "energetic",
        "slide_count_hint": 6,
        "required_sections": ["problem", "solution", "market", "ask"],
        "visuals_hint": ["architecture diagram"],
        "research_queries": ["enterprise backup market 2026"],
        "language": "en",
    })
    pattern = IntentAnalystPattern(config={})
    context = _ctx_with(payload)
    result = await pattern.execute(context)
    assert isinstance(result.parsed, IntentReport)
    assert result.parsed.purpose == "pitch"
    assert result.parsed.slide_count_hint == 6


@pytest.mark.asyncio
async def test_intent_invalid_json_retries_once():
    pattern = IntentAnalystPattern(config={"max_steps": 2})
    call_log = []

    async def complete(*args, **kwargs):
        call_log.append(1)
        if len(call_log) == 1:
            return SimpleNamespace(content="not json", tool_calls=[])
        return SimpleNamespace(content=json.dumps({
            "topic": "t", "audience": "a", "purpose": "pitch",
            "tone": "formal", "slide_count_hint": 5,
            "required_sections": [], "visuals_hint": [],
            "research_queries": [], "language": "zh",
        }), tool_calls=[])

    llm = SimpleNamespace(complete=complete)
    context = SimpleNamespace(
        input_text="draft deck", memory_view={}, tool_results=[],
        state={}, assembly_metadata={}, llm=llm,
    )
    result = await pattern.execute(context)
    assert isinstance(result.parsed, IntentReport)
    assert len(call_log) == 2
```

- [ ] **Step 2: Run, expect fail**

```bash
uv run pytest tests/unit/test_intent_analyst.py -v
```

- [ ] **Step 3: Implement pattern (and start plugins.py)**

```python
# examples/pptx_generator/app/plugins.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from openagents.interfaces.capabilities import PATTERN_EXECUTE
from openagents.interfaces.pattern import PatternPlugin

from ..state import IntentReport


_INTENT_SYSTEM = """You are a presentation planning assistant.
Extract an IntentReport as JSON only. Required fields:
topic, audience, purpose(one of pitch|report|teaching|announcement|other),
tone(one of formal|casual|energetic|minimalist),
slide_count_hint(int 3..20), required_sections(list), visuals_hint(list),
research_queries(list of up to 5 concrete search queries),
language(zh|en|bilingual).
Output ONLY JSON without markdown fencing.
"""


@dataclass
class PatternOutcome:
    parsed: Any
    raw: str
    steps_used: int


class IntentAnalystPattern(PatternPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE})
        self.max_steps = int(self.config.get("max_steps", 3))

    async def execute(self, context: Any) -> PatternOutcome:
        goals = context.memory_view.get("user_goals", []) if hasattr(context, "memory_view") else []
        feedback = context.memory_view.get("user_feedback", []) if hasattr(context, "memory_view") else []
        user_prompt = context.input_text
        priors = "\n".join(f"- {e['rule']}" for e in (goals + feedback))
        prompt = f"{_INTENT_SYSTEM}\nKnown user preferences:\n{priors or '(none)'}\n\nUser request:\n{user_prompt}"

        last_raw = ""
        for step in range(1, self.max_steps + 1):
            resp = await context.llm.complete(system=_INTENT_SYSTEM, prompt=prompt)
            last_raw = getattr(resp, "content", "")
            parsed = _try_parse_intent(last_raw)
            if parsed is not None:
                context.state["_runtime_last_output"] = last_raw
                return PatternOutcome(parsed=parsed, raw=last_raw, steps_used=step)
            prompt = prompt + f"\n\nPrevious output was not valid JSON:\n{last_raw}\nTry again."
        raise RuntimeError(f"intent pattern exhausted retries; last raw: {last_raw[:200]}")


def _try_parse_intent(raw: str) -> IntentReport | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    try:
        return IntentReport.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError):
        return None
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_intent_analyst.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/app/ tests/unit/test_intent_analyst.py
rtk git commit -m "feat(pptx): IntentAnalystPattern with JSON-schema retry loop"
```

---

### Task 12: `ResearchPattern` — Tavily MCP/fallback plus synthesis

**Files:**
- Modify: `examples/pptx_generator/app/plugins.py` (append)
- Create: `tests/unit/test_research_agent.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_research_agent.py
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.app.plugins import ResearchPattern
from examples.pptx_generator.state import ResearchFindings


@pytest.mark.asyncio
async def test_research_happy_path():
    tool_response = {
        "query": "q1",
        "results": [
            {"url": "https://a", "title": "A", "content": "fact A", "score": 0.9},
        ],
    }
    llm_summary = json.dumps({
        "queries_executed": ["q1"],
        "sources": [{"url": "https://a", "title": "A", "snippet": "fact A"}],
        "key_facts": ["A says fact A"],
        "caveats": [],
    })

    async def run_tool(name, params, context=None):
        return SimpleNamespace(success=True, data=tool_response)

    llm = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content=llm_summary, tool_calls=[])))
    context = SimpleNamespace(
        state={"intent": {"research_queries": ["q1"]}},
        memory_view={},
        tool_results=[],
        assembly_metadata={},
        input_text="",
        llm=llm,
        run_tool=run_tool,
    )
    pattern = ResearchPattern(config={})
    outcome = await pattern.execute(context)
    assert isinstance(outcome.parsed, ResearchFindings)
    assert outcome.parsed.key_facts == ["A says fact A"]


@pytest.mark.asyncio
async def test_research_empty_queries_returns_empty_findings():
    llm = SimpleNamespace(complete=AsyncMock())
    context = SimpleNamespace(
        state={"intent": {"research_queries": []}},
        memory_view={},
        tool_results=[],
        assembly_metadata={},
        input_text="",
        llm=llm,
        run_tool=AsyncMock(),
    )
    outcome = await ResearchPattern(config={}).execute(context)
    assert outcome.parsed.sources == []
    assert llm.complete.await_count == 0
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement pattern (append to plugins.py)**

```python
# append to examples/pptx_generator/app/plugins.py
from ..state import ResearchFindings, Source


_RESEARCH_SYSTEM = """Given a set of search results per query, output a JSON
ResearchFindings with: queries_executed, sources (url/title/snippet),
key_facts (3..8 bullet-style facts), caveats. JSON only, no markdown fencing.
"""


class ResearchPattern(PatternPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE})
        self.max_steps = int(self.config.get("max_steps", 6))

    async def execute(self, context: Any) -> PatternOutcome:
        intent = context.state.get("intent") or {}
        queries = list((intent.get("research_queries") or []))[:5]
        if not queries:
            return PatternOutcome(parsed=ResearchFindings(), raw="", steps_used=0)

        search_blocks: list[dict[str, Any]] = []
        for q in queries:
            try:
                tool_result = await context.run_tool("tavily_mcp", {"query": q})
                data = getattr(tool_result, "data", tool_result)
            except Exception:
                tool_result = await context.run_tool("tavily_fallback", {"query": q})
                data = getattr(tool_result, "data", tool_result)
            search_blocks.append({"query": q, "results": data.get("results", [])})

        prompt = json.dumps({"queries": search_blocks}, ensure_ascii=False)
        last_raw = ""
        for step in range(1, self.max_steps + 1):
            resp = await context.llm.complete(system=_RESEARCH_SYSTEM, prompt=prompt)
            last_raw = getattr(resp, "content", "")
            parsed = _try_parse(last_raw, ResearchFindings)
            if parsed is not None:
                context.state["research"] = parsed.model_dump(mode="json")
                return PatternOutcome(parsed=parsed, raw=last_raw, steps_used=step)
            prompt = prompt + f"\n\nPrevious output invalid: {last_raw}\nTry again."
        raise RuntimeError("research pattern failed to produce valid JSON")


def _try_parse(raw: str, model):
    from pydantic import ValidationError as _VE
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    try:
        return model.model_validate(json.loads(text))
    except (json.JSONDecodeError, _VE):
        return None
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_research_agent.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/app/plugins.py tests/unit/test_research_agent.py
rtk git commit -m "feat(pptx): ResearchPattern with MCP-first Tavily, REST fallback"
```

---

### Task 13: `OutlinePattern`

**Files:**
- Modify: `examples/pptx_generator/app/plugins.py`
- Create: `tests/unit/test_outliner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_outliner.py
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.app.plugins import OutlinePattern
from examples.pptx_generator.state import SlideOutline


@pytest.mark.asyncio
async def test_outline_generates_valid_slides():
    llm_response = json.dumps({
        "slides": [
            {"index": 1, "type": "cover", "title": "T", "key_points": [], "sources_cited": []},
            {"index": 2, "type": "content", "title": "Why", "key_points": ["p1"], "sources_cited": []},
            {"index": 3, "type": "closing", "title": "Thanks", "key_points": [], "sources_cited": []},
        ]
    })
    llm = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content=llm_response, tool_calls=[])))
    context = SimpleNamespace(
        input_text="", state={"intent": {"slide_count_hint": 3}, "research": {}},
        memory_view={}, tool_results=[], assembly_metadata={}, llm=llm,
    )
    outcome = await OutlinePattern(config={}).execute(context)
    assert isinstance(outcome.parsed, SlideOutline)
    assert len(outcome.parsed.slides) == 3
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement (append to plugins.py)**

```python
# append to examples/pptx_generator/app/plugins.py
from ..state import SlideOutline


_OUTLINE_SYSTEM = """Produce a SlideOutline JSON matching the SlideOutline pydantic schema.
Each slide must have index (1..N), type (cover|agenda|content|transition|closing|freeform),
title, key_points (may be empty), sources_cited (indexes into research.sources).
Output ONLY JSON; no markdown fencing.
"""


class OutlinePattern(PatternPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE})
        self.max_steps = int(self.config.get("max_steps", 3))

    async def execute(self, context: Any) -> PatternOutcome:
        intent = context.state.get("intent") or {}
        research = context.state.get("research") or {}
        prompt = json.dumps({"intent": intent, "research": research}, ensure_ascii=False)
        last_raw = ""
        for step in range(1, self.max_steps + 1):
            resp = await context.llm.complete(system=_OUTLINE_SYSTEM, prompt=prompt)
            last_raw = getattr(resp, "content", "")
            parsed = _try_parse(last_raw, SlideOutline)
            if parsed is not None:
                context.state["outline"] = parsed.model_dump(mode="json")
                return PatternOutcome(parsed=parsed, raw=last_raw, steps_used=step)
            prompt = prompt + f"\n\nPrevious output invalid: {last_raw}\nTry again."
        raise RuntimeError("outline pattern failed to produce valid JSON")
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_outliner.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/app/plugins.py tests/unit/test_outliner.py
rtk git commit -m "feat(pptx): OutlinePattern producing SlideOutline JSON"
```

---

### Task 14: `ThemePattern` + built-in palette/font catalog

**Files:**
- Create: `examples/pptx_generator/app/catalog.py`
- Modify: `examples/pptx_generator/app/plugins.py`
- Create: `tests/unit/test_theme_pattern.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_theme_pattern.py
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.app.catalog import PALETTES, FONT_PAIRINGS
from examples.pptx_generator.app.plugins import ThemePattern
from examples.pptx_generator.state import ThemeSelection


def test_catalog_has_at_least_five_palettes():
    assert len(PALETTES) >= 5
    for p in PALETTES:
        assert set(p).issuperset({"name", "palette", "mood"})


def test_font_pairings_cover_zh_en():
    assert any(fp["cjk"] for fp in FONT_PAIRINGS)


@pytest.mark.asyncio
async def test_theme_pattern_selects_valid_theme():
    llm_response = json.dumps({
        "palette_name": PALETTES[0]["name"],
        "font_pairing_name": FONT_PAIRINGS[0]["name"],
        "style": "sharp",
        "page_badge_style": "circle",
    })
    llm = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content=llm_response, tool_calls=[])))
    context = SimpleNamespace(
        input_text="", state={"intent": {"tone": "formal", "language": "zh"}},
        memory_view={"decisions": []}, tool_results=[], assembly_metadata={}, llm=llm,
    )
    outcome = await ThemePattern(config={}).execute(context)
    assert isinstance(outcome.parsed, ThemeSelection)
    assert outcome.parsed.palette.primary == PALETTES[0]["palette"]["primary"]
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement catalog**

```python
# examples/pptx_generator/app/catalog.py
from __future__ import annotations

PALETTES = [
    {
        "name": "midnight",
        "mood": "formal, technical",
        "palette": {
            "primary": "22223B", "secondary": "4A4E69",
            "accent": "9A8C98", "light": "C9ADA7", "bg": "F2E9E4",
        },
    },
    {
        "name": "ocean",
        "mood": "energetic, trustworthy",
        "palette": {
            "primary": "0D3B66", "secondary": "1B6CA8",
            "accent": "F4D35E", "light": "FAF0CA", "bg": "EE964B",
        },
    },
    {
        "name": "forest",
        "mood": "grounded, warm",
        "palette": {
            "primary": "264653", "secondary": "2A9D8F",
            "accent": "E9C46A", "light": "F4A261", "bg": "E76F51",
        },
    },
    {
        "name": "minimal-mono",
        "mood": "minimalist",
        "palette": {
            "primary": "111111", "secondary": "444444",
            "accent": "888888", "light": "DDDDDD", "bg": "FFFFFF",
        },
    },
    {
        "name": "candy",
        "mood": "casual, friendly",
        "palette": {
            "primary": "FF6B6B", "secondary": "FFD93D",
            "accent": "6BCB77", "light": "4D96FF", "bg": "FFF6F0",
        },
    },
]

FONT_PAIRINGS = [
    {
        "name": "arial-yahei",
        "heading": "Arial", "body": "Arial", "cjk": "Microsoft YaHei",
    },
    {
        "name": "helvetica-songti",
        "heading": "Helvetica Neue", "body": "Helvetica Neue", "cjk": "Songti SC",
    },
    {
        "name": "georgia-yahei",
        "heading": "Georgia", "body": "Georgia", "cjk": "Microsoft YaHei",
    },
]
```

- [ ] **Step 4: Implement pattern (append to plugins.py)**

```python
# append to examples/pptx_generator/app/plugins.py
from .catalog import FONT_PAIRINGS, PALETTES
from ..state import FontPairing, Palette, ThemeSelection


_THEME_SYSTEM = """Given an IntentReport and the catalogs of PALETTES and FONT_PAIRINGS
(each has a unique 'name'), select exactly one palette_name and one font_pairing_name
that best fit the tone/language. Also pick style (sharp|soft|rounded|pill) and
page_badge_style (circle|pill). Output JSON with keys: palette_name, font_pairing_name,
style, page_badge_style. Output JSON only.
"""


class ThemePattern(PatternPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE})
        self.max_steps = int(self.config.get("max_steps", 2))

    async def execute(self, context: Any) -> PatternOutcome:
        intent = context.state.get("intent") or {}
        decisions = context.memory_view.get("decisions", [])
        prompt = json.dumps({
            "intent": intent,
            "palette_catalog": PALETTES,
            "font_catalog": FONT_PAIRINGS,
            "prior_decisions": [e.get("rule") for e in decisions],
        }, ensure_ascii=False)

        for _ in range(self.max_steps):
            resp = await context.llm.complete(system=_THEME_SYSTEM, prompt=prompt)
            raw = getattr(resp, "content", "")
            choice = _try_parse_json(raw)
            if not choice:
                continue
            pal = next((p for p in PALETTES if p["name"] == choice.get("palette_name")), None)
            font = next((f for f in FONT_PAIRINGS if f["name"] == choice.get("font_pairing_name")), None)
            if not pal or not font:
                continue
            theme = ThemeSelection(
                palette=Palette(**pal["palette"]),
                fonts=FontPairing(heading=font["heading"], body=font["body"], cjk=font["cjk"]),
                style=choice.get("style", "soft"),
                page_badge_style=choice.get("page_badge_style", "circle"),
            )
            context.state["theme"] = theme.model_dump(mode="json")
            return PatternOutcome(parsed=theme, raw=raw, steps_used=1)
        raise RuntimeError("theme pattern failed to pick a valid combination")


def _try_parse_json(raw: str):
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
```

- [ ] **Step 5: Run, expect pass**

```bash
uv run pytest tests/unit/test_theme_pattern.py -v
```

- [ ] **Step 6: Commit**

```bash
rtk git add examples/pptx_generator/app/catalog.py examples/pptx_generator/app/plugins.py tests/unit/test_theme_pattern.py
rtk git commit -m "feat(pptx): ThemePattern + built-in palette/font catalog"
```

---

### Task 15: `SlideGenPattern` — per-slide JSON schema, retry, freeform fallback

**Files:**
- Modify: `examples/pptx_generator/app/plugins.py`
- Create: `examples/pptx_generator/app/slot_schemas.py`
- Create: `tests/unit/test_slide_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_slide_generator.py
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.app.plugins import SlideGenPattern
from examples.pptx_generator.state import SlideIR


def _spec(index, type_):
    return {"index": index, "type": type_, "title": "T", "key_points": ["p"], "sources_cited": []}


@pytest.mark.asyncio
async def test_generates_valid_cover():
    llm_response = json.dumps({"title": "T", "subtitle": "sub", "author": "me"})
    llm = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content=llm_response, tool_calls=[])))
    context = SimpleNamespace(
        state={}, memory_view={}, tool_results=[], assembly_metadata={}, llm=llm,
        input_text=json.dumps({"target_spec": _spec(1, "cover"), "theme": {}}),
    )
    outcome = await SlideGenPattern(config={"max_retries": 2}).execute(context)
    assert isinstance(outcome.parsed, SlideIR)
    assert outcome.parsed.type == "cover"
    assert outcome.parsed.slots["title"] == "T"


@pytest.mark.asyncio
async def test_falls_back_to_freeform_after_retries():
    llm = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content="garbage", tool_calls=[])))
    context = SimpleNamespace(
        state={}, memory_view={}, tool_results=[], assembly_metadata={}, llm=llm,
        input_text=json.dumps({"target_spec": _spec(2, "content"), "theme": {}}),
    )
    outcome = await SlideGenPattern(config={"max_retries": 1, "allow_freeform_fallback": True}).execute(context)
    assert outcome.parsed.type == "freeform"
    assert outcome.parsed.freeform_js  # non-empty
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement slot schemas**

```python
# examples/pptx_generator/app/slot_schemas.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class CoverSlots(BaseModel):
    title: str
    subtitle: str | None = None
    author: str | None = None
    date: str | None = None


class AgendaItem(BaseModel):
    label: str
    sub: str | None = None


class AgendaSlots(BaseModel):
    title: str
    items: list[AgendaItem]


class BulletsBlock(BaseModel):
    kind: Literal["bullets"] = "bullets"
    items: list[str]


class TwoColumnBlock(BaseModel):
    kind: Literal["two_column"] = "two_column"
    left_items: list[str]
    right_items: list[str]


class CalloutBlock(BaseModel):
    kind: Literal["callout"] = "callout"
    text: str
    icon: str | None = None


ContentBlock = BulletsBlock | TwoColumnBlock | CalloutBlock


class ContentSlots(BaseModel):
    title: str
    body_blocks: list[ContentBlock]


class TransitionSlots(BaseModel):
    section_number: int
    section_title: str
    subtitle: str | None = None


class ClosingSlots(BaseModel):
    title: str
    call_to_action: str | None = None
    contact: str | None = None


SLOT_MODELS: dict[str, type[BaseModel]] = {
    "cover": CoverSlots,
    "agenda": AgendaSlots,
    "content": ContentSlots,
    "transition": TransitionSlots,
    "closing": ClosingSlots,
}
```

- [ ] **Step 4: Implement pattern (append)**

```python
# append to examples/pptx_generator/app/plugins.py
from datetime import datetime, timezone

from pydantic import ValidationError

from .slot_schemas import SLOT_MODELS
from ..state import SlideIR


_SLIDEGEN_SYSTEM_TMPL = """You are filling a slide template of type {slide_type}.
Return a JSON object matching the {slide_type} slot schema exactly. No markdown.
"""


class SlideGenPattern(PatternPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE})
        self.max_retries = int(self.config.get("max_retries", 2))
        self.allow_freeform = bool(self.config.get("allow_freeform_fallback", True))

    async def execute(self, context: Any) -> PatternOutcome:
        # Per-slide payload is passed via input_text as JSON:
        # {"target_spec": {...}, "theme": {...}}
        try:
            payload = json.loads(context.input_text or "{}")
        except json.JSONDecodeError:
            payload = {}
        spec = payload.get("target_spec") or context.state.get("target_spec") or {}
        theme = payload.get("theme") or context.state.get("theme") or {}
        slide_type = spec.get("type", "content")
        model = SLOT_MODELS.get(slide_type)
        if model is None:
            return self._freeform(spec, reason=f"unknown type {slide_type}")

        system = _SLIDEGEN_SYSTEM_TMPL.format(slide_type=slide_type)
        prompt = json.dumps({"spec": spec, "theme": theme}, ensure_ascii=False)
        last_raw = ""
        for attempt in range(self.max_retries + 1):
            resp = await context.llm.complete(system=system, prompt=prompt)
            last_raw = getattr(resp, "content", "")
            parsed = _try_parse_json(last_raw)
            if parsed is not None:
                try:
                    slots_model = model.model_validate(parsed)
                except ValidationError:
                    prompt = prompt + f"\n\nPrevious output failed schema: {last_raw}\nRetry."
                    continue
                slide = SlideIR(
                    index=spec.get("index", 0),
                    type=slide_type,
                    slots=slots_model.model_dump(),
                    generated_at=datetime.now(timezone.utc),
                )
                return PatternOutcome(parsed=slide, raw=last_raw, steps_used=attempt + 1)
            prompt = prompt + f"\n\nPrevious output not JSON: {last_raw}\nRetry."
        if not self.allow_freeform:
            raise RuntimeError(f"slide gen failed after {self.max_retries + 1} tries; last raw: {last_raw[:200]}")
        return self._freeform(spec, reason=f"schema-retry-exhausted: {last_raw[:80]}")

    def _freeform(self, spec: dict[str, Any], *, reason: str) -> PatternOutcome:
        placeholder_js = (
            f"// FREEFORM fallback for slide index={spec.get('index')} reason={reason!r}\n"
            "function createSlide(pres, theme) {\n"
            "  const slide = pres.addSlide();\n"
            "  slide.background = { color: theme.bg };\n"
            f"  slide.addText({json.dumps(spec.get('title', 'Untitled'))}, {{ x: 0.5, y: 2.4, w: 9, h: 0.8, "
            "fontSize: 32, fontFace: 'Arial', color: theme.primary, bold: true, align: 'center' }});\n"
            "  return slide;\n"
            "}\n"
            "module.exports = { createSlide };\n"
        )
        slide = SlideIR(
            index=spec.get("index", 0),
            type="freeform",
            slots={},
            freeform_js=placeholder_js,
            generated_at=datetime.now(timezone.utc),
        )
        return PatternOutcome(parsed=slide, raw="", steps_used=0)
```

- [ ] **Step 5: Run, expect pass**

```bash
uv run pytest tests/unit/test_slide_generator.py -v
```

- [ ] **Step 6: Commit**

```bash
rtk git add examples/pptx_generator/app/ tests/unit/test_slide_generator.py
rtk git commit -m "feat(pptx): SlideGenPattern with per-type slot validation and freeform fallback"
```

---

## Phase D — CLI + Wizards

### Task 16: CLI entry point + `resume` command

**Files:**
- Create: `examples/pptx_generator/cli.py`
- Create: `tests/unit/test_pptx_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_pptx_cli.py
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest

from examples.pptx_generator.cli import build_parser, main


def test_parser_has_new_and_resume():
    parser = build_parser()
    args = parser.parse_args(["new", "--topic", "hello"])
    assert args.command == "new"
    args2 = parser.parse_args(["resume", "my-slug"])
    assert args2.command == "resume"
    assert args2.slug == "my-slug"


@pytest.mark.asyncio
async def test_main_dispatches_new(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTX_AGENT_OUTPUTS", str(tmp_path))
    fake = AsyncMock(return_value=0)
    monkeypatch.setattr("examples.pptx_generator.cli.run_wizard", fake)
    rc = await main(["new", "--topic", "demo"])
    assert rc == 0
    fake.assert_awaited_once()
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/cli.py
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .persistence import load_project, save_project
from .state import DeckProject


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pptx-agent",
        description="Interactive PPT generator built on openagents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="start a new deck")
    p_new.add_argument("--topic", help="initial topic prompt (optional)")
    p_new.add_argument("--slug", help="override project slug")

    p_resume = sub.add_parser("resume", help="resume an existing deck by slug")
    p_resume.add_argument("slug")

    sub.add_parser("memory", help="list persisted memory entries").add_argument(
        "--section", default=None,
    )
    return parser


def _slugify(topic: str | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (topic or "deck").lower()).strip("-") or "deck"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{base}-{stamp}"


def outputs_root() -> Path:
    return Path(os.environ.get("PPTX_AGENT_OUTPUTS",
                               "examples/pptx_generator/outputs"))


async def run_wizard(project: DeckProject, *, resume: bool = False) -> int:
    # Implemented in Task 17 onward. For now, save and report.
    save_project(project, root=outputs_root())
    return 0


async def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "new":
        slug = args.slug or _slugify(args.topic)
        project = DeckProject(
            slug=slug, created_at=datetime.now(timezone.utc), stage="intent",
        )
        save_project(project, root=outputs_root())
        return await run_wizard(project)
    if args.command == "resume":
        project = load_project(args.slug, root=outputs_root())
        return await run_wizard(project, resume=True)
    if args.command == "memory":
        from openagents.plugins.builtin.memory.markdown_memory import MarkdownMemory
        mem = MarkdownMemory(config={"memory_dir": "~/.config/pptx-agent/memory"})
        sections = [args.section] if args.section else mem.cfg.sections
        for s in sections:
            print(f"## {s}")
            for e in mem.list_entries(s):
                print(f"- [{e['id']}] {e['rule']}  — {e['reason']}")
        return 0
    return 1


def main_sync() -> int:
    return asyncio.run(main(sys.argv[1:]))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main_sync())
```

- [ ] **Step 4: Adjust pyproject scripts entry**

In `pyproject.toml`:

```toml
[project.scripts]
pptx-agent = "examples.pptx_generator.cli:main_sync"
```

- [ ] **Step 5: Run, expect pass**

```bash
uv run pytest tests/unit/test_pptx_cli.py -v
```

- [ ] **Step 6: Commit**

```bash
rtk git add examples/pptx_generator/cli.py pyproject.toml tests/unit/test_pptx_cli.py
rtk git commit -m "feat(pptx): CLI entry with new/resume/memory subcommands"
```

---

### Task 17: Stage 1 — `IntentWizard`

**Files:**
- Create: `examples/pptx_generator/wizard/__init__.py`
- Create: `examples/pptx_generator/wizard/intent.py`
- Create: `tests/unit/test_intent_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_intent_wizard.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.state import DeckProject, IntentReport
from examples.pptx_generator.wizard.intent import IntentWizardStep


@pytest.mark.asyncio
async def test_intent_wizard_confirm_happy_path(monkeypatch):
    step = IntentWizardStep(runtime=SimpleNamespace(), topic_hint="draft")
    report = IntentReport(
        topic="t", audience="a", purpose="pitch", tone="formal",
        slide_count_hint=5, required_sections=[], visuals_hint=[],
        research_queries=[], language="zh",
    )
    step._invoke_agent = AsyncMock(return_value=report)  # type: ignore[attr-defined]
    monkeypatch.setattr("examples.pptx_generator.wizard.intent.Wizard.confirm",
                        AsyncMock(return_value=True))

    project = DeckProject(slug="s", created_at=report.__class__.model_construct.__self__.__class__ and __import__("datetime").datetime.now(__import__("datetime").timezone.utc), stage="intent")
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    assert project.intent is not None
    assert project.stage == "env"
```

(If that datetime construction is ugly, simplify by passing a clean `datetime.now(timezone.utc)` directly.)

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/intent.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openagents.cli.wizard import StepResult, Wizard

from ..state import DeckProject, IntentReport


@dataclass
class IntentWizardStep:
    runtime: Any
    topic_hint: str | None
    title: str = "intent"
    description: str = "Understand what you want to present."

    async def render(self, console: Any, project: DeckProject) -> StepResult:
        report = await self._invoke_agent(project)
        if console is not None:
            console.print(Wizard.panel("Intent", self._format_report(report)))
        confirmed = await Wizard.confirm("Does this match your intent?", default=True)
        if not confirmed:
            return StepResult(status="retry")
        project.intent = report
        project.stage = "env"
        save = await Wizard.confirm("Save these as long-term preferences?", default=False)
        if save:
            project_state = {"_pending_memory_writes": [
                {"category": "user_goals",
                 "rule": f"typical deck: {report.slide_count_hint} slides, tone={report.tone}",
                 "reason": "confirmed at intent stage"}
            ]}
            # In the full implementation, these writes are queued and the memory
            # plugin's writeback drains them on next run. For wizard-initiated
            # captures we can also import MarkdownMemory and call .capture directly:
            try:
                from openagents.plugins.builtin.memory.markdown_memory import MarkdownMemory
                MarkdownMemory(config={"memory_dir": "~/.config/pptx-agent/memory"}).capture(
                    category="user_goals",
                    rule=project_state["_pending_memory_writes"][0]["rule"],
                    reason=project_state["_pending_memory_writes"][0]["reason"],
                )
            except Exception:  # pragma: no cover
                pass
        return StepResult(status="completed", data=report)

    async def _invoke_agent(self, project: DeckProject) -> IntentReport:
        result = await self.runtime.run(
            agent_id="intent-analyst",
            session_id=project.slug,
            input_text=self.topic_hint or "",
        )
        # `result` shape depends on runtime.run_detailed; we expect an IntentReport
        # to be available via result.parsed or result.state["intent"]. Keep this
        # flexible so unit tests can mock it entirely.
        parsed = getattr(result, "parsed", None)
        if parsed is None and hasattr(result, "state"):
            parsed = IntentReport.model_validate(result.state.get("intent"))
        if not isinstance(parsed, IntentReport):
            raise RuntimeError("intent agent did not return IntentReport")
        return parsed

    @staticmethod
    def _format_report(r: IntentReport) -> str:
        lines = [
            f"Topic:      {r.topic}",
            f"Audience:   {r.audience}",
            f"Purpose:    {r.purpose}",
            f"Tone:       {r.tone}",
            f"Slides:     {r.slide_count_hint}",
            f"Language:   {r.language}",
            f"Sections:   {', '.join(r.required_sections) or '(none)'}",
            f"Visuals:    {', '.join(r.visuals_hint) or '(none)'}",
            f"Research:   {', '.join(r.research_queries) or '(none)'}",
        ]
        return "\n".join(lines)
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_intent_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/ tests/unit/test_intent_wizard.py
rtk git commit -m "feat(pptx): IntentWizardStep with agent call and memory capture"
```

---

### Task 18: Stage 2 — `EnvDoctorWizard`

**Files:**
- Create: `examples/pptx_generator/wizard/env.py`
- Create: `tests/unit/test_env_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_env_wizard.py
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from examples.pptx_generator.state import DeckProject
from examples.pptx_generator.wizard.env import EnvDoctorWizardStep
from openagents.utils.env_doctor import CheckResult, CheckStatus, EnvironmentReport


@pytest.mark.asyncio
async def test_all_ok_transitions_to_research(monkeypatch):
    doctor = MagicMock()
    doctor.run = AsyncMock(return_value=EnvironmentReport(
        checks=[CheckResult(name="python", status=CheckStatus.OK, detail="3.12")],
        missing_required=[], missing_optional=[], auto_fixable=[],
    ))
    step = EnvDoctorWizardStep(doctor=doctor)
    project = DeckProject(slug="x", created_at=datetime.now(timezone.utc), stage="env")
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    assert project.stage == "research"


@pytest.mark.asyncio
async def test_missing_required_prompts_user(monkeypatch):
    doctor = MagicMock()
    doctor.run = AsyncMock(return_value=EnvironmentReport(
        checks=[CheckResult(name="LLM_API_KEY", status=CheckStatus.MISSING,
                            detail="not set", get_url="https://example")],
        missing_required=["LLM_API_KEY"], missing_optional=[], auto_fixable=[],
    ))
    doctor.persist_env = MagicMock(return_value="path/to/.env")
    monkeypatch.setattr("examples.pptx_generator.wizard.env.Wizard.password",
                        AsyncMock(return_value="sk-xxx"))
    step = EnvDoctorWizardStep(doctor=doctor)
    project = DeckProject(slug="x", created_at=datetime.now(timezone.utc), stage="env")
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    doctor.persist_env.assert_called_once()
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/env.py
from __future__ import annotations

from dataclasses import dataclass

from openagents.cli.wizard import StepResult, Wizard
from openagents.utils.env_doctor import CheckStatus, EnvironmentDoctor

from ..state import DeckProject


@dataclass
class EnvDoctorWizardStep:
    doctor: EnvironmentDoctor
    title: str = "env"
    description: str = "Check required binaries and API keys."

    async def render(self, console, project: DeckProject) -> StepResult:
        report = await self.doctor.run()
        project.env_report = report
        if console is not None:
            self._print_table(console, report)

        for name in report.missing_required:
            check = next(c for c in report.checks if c.name == name)
            if name in ("LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL") or name.startswith("TAVILY"):
                value = await Wizard.password(
                    f"Enter {name} (get it at {check.get_url or 'your provider'}): "
                )
                if not value:
                    return StepResult(status="aborted")
                self.doctor.persist_env(name, value, level="user")
            else:
                proceed = await Wizard.confirm(
                    f"{name} is missing: {check.detail}. Proceed anyway?", default=False,
                )
                if not proceed:
                    return StepResult(status="aborted")

        for name in report.missing_optional:
            check = next(c for c in report.checks if c.name == name)
            enable = await Wizard.confirm(
                f"Optional {name} missing. Enable feature by providing the key?",
                default=False,
            )
            if enable:
                value = await Wizard.password(
                    f"Enter {name} (get it at {check.get_url or 'your provider'}): "
                )
                if value:
                    self.doctor.persist_env(name, value, level="user")

        project.stage = "research"
        return StepResult(status="completed")

    @staticmethod
    def _print_table(console, report):
        from rich.table import Table
        table = Table(title="Environment Check")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Detail")
        for c in report.checks:
            color = {CheckStatus.OK: "green", CheckStatus.MISSING: "red",
                     CheckStatus.OUTDATED: "yellow"}.get(c.status, "white")
            table.add_row(c.name, f"[{color}]{c.status.value}[/{color}]", c.detail)
        console.print(table)
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_env_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/env.py tests/unit/test_env_wizard.py
rtk git commit -m "feat(pptx): EnvDoctorWizardStep with interactive key capture"
```

---

### Task 19: Stage 3 — `ResearchWizard`

**Files:**
- Create: `examples/pptx_generator/wizard/research.py`
- Create: `tests/unit/test_research_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_research_wizard.py
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.state import (
    DeckProject, IntentReport, ResearchFindings, Source,
)
from examples.pptx_generator.wizard.research import ResearchWizardStep


def _intent(queries):
    return IntentReport(
        topic="t", audience="a", purpose="pitch", tone="formal",
        slide_count_hint=5, required_sections=[], visuals_hint=[],
        research_queries=queries, language="zh",
    )


@pytest.mark.asyncio
async def test_skipped_when_no_queries(monkeypatch):
    runtime = SimpleNamespace()
    step = ResearchWizardStep(runtime=runtime)
    project = DeckProject(slug="x", created_at=datetime.now(timezone.utc),
                          stage="research", intent=_intent([]))
    result = await step.render(console=None, project=project)
    assert result.status == "skipped"
    assert project.research.sources == []
    assert project.stage == "outline"


@pytest.mark.asyncio
async def test_runs_agent_and_filters(monkeypatch):
    findings = ResearchFindings(
        queries_executed=["q"],
        sources=[
            Source(url="https://a", title="A", snippet="sA"),
            Source(url="https://b", title="B", snippet="sB"),
        ],
        key_facts=["f1"], caveats=[],
    )
    runtime = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(
        parsed=findings, state={"research": findings.model_dump(mode="json")},
    )))
    monkeypatch.setattr(
        "examples.pptx_generator.wizard.research.Wizard.multi_select",
        AsyncMock(return_value=["A"]),
    )
    step = ResearchWizardStep(runtime=runtime)
    project = DeckProject(slug="x", created_at=datetime.now(timezone.utc),
                          stage="research", intent=_intent(["q"]))
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    assert len(project.research.sources) == 1
    assert project.research.sources[0].title == "A"
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/research.py
from __future__ import annotations

from dataclasses import dataclass

from openagents.cli.wizard import StepResult, Wizard

from ..state import DeckProject, ResearchFindings


@dataclass
class ResearchWizardStep:
    runtime: object
    title: str = "research"
    description: str = "Gather facts via Tavily (MCP → REST fallback)."

    async def render(self, console, project: DeckProject) -> StepResult:
        assert project.intent is not None
        if not project.intent.research_queries:
            project.research = ResearchFindings()
            project.stage = "outline"
            return StepResult(status="skipped")

        result = await self.runtime.run(
            agent_id="research-agent",
            session_id=project.slug,
            input_text="",
        )
        findings: ResearchFindings = getattr(result, "parsed", None) or \
            ResearchFindings.model_validate(result.state.get("research", {}))

        if console is not None:
            self._render_tree(console, findings)

        if findings.sources:
            chosen_titles = await Wizard.multi_select(
                "Keep which sources? (enter to select all)",
                choices=[s.title for s in findings.sources],
                min_selected=0,
            )
            keep = set(chosen_titles) if chosen_titles else {s.title for s in findings.sources}
            findings = findings.model_copy(update={
                "sources": [s for s in findings.sources if s.title in keep]
            })

        project.research = findings
        project.stage = "outline"
        return StepResult(status="completed")

    @staticmethod
    def _render_tree(console, findings: ResearchFindings):
        from rich.tree import Tree
        tree = Tree("Research Findings")
        for src in findings.sources:
            tree.add(f"[bold]{src.title}[/bold]  {src.url}\n   {src.snippet}")
        console.print(tree)
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_research_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/research.py tests/unit/test_research_wizard.py
rtk git commit -m "feat(pptx): ResearchWizardStep with skip-on-empty and source filtering"
```

---

### Task 20: Stage 4 — `OutlineWizard`

**Files:**
- Create: `examples/pptx_generator/wizard/outline.py`
- Create: `tests/unit/test_outline_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_outline_wizard.py
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.state import (
    DeckProject, IntentReport, ResearchFindings, SlideOutline, SlideSpec,
)
from examples.pptx_generator.wizard.outline import OutlineWizardStep


def _base_project():
    intent = IntentReport(
        topic="t", audience="a", purpose="pitch", tone="formal",
        slide_count_hint=3, required_sections=[], visuals_hint=[],
        research_queries=[], language="zh",
    )
    return DeckProject(slug="x", created_at=datetime.now(timezone.utc),
                       stage="outline", intent=intent, research=ResearchFindings())


@pytest.mark.asyncio
async def test_accepts_outline(monkeypatch):
    outline = SlideOutline(slides=[
        SlideSpec(index=1, type="cover", title="T", key_points=[], sources_cited=[]),
        SlideSpec(index=2, type="content", title="Why", key_points=[], sources_cited=[]),
        SlideSpec(index=3, type="closing", title="End", key_points=[], sources_cited=[]),
    ])
    runtime = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(
        parsed=outline, state={"outline": outline.model_dump(mode="json")},
    )))
    monkeypatch.setattr("examples.pptx_generator.wizard.outline.Wizard.select",
                        AsyncMock(return_value="accept"))
    step = OutlineWizardStep(runtime=runtime)
    project = _base_project()
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    assert project.outline and len(project.outline.slides) == 3
    assert project.stage == "theme"
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/outline.py
from __future__ import annotations

from dataclasses import dataclass

from openagents.cli.wizard import StepResult, Wizard

from ..state import DeckProject, SlideOutline


@dataclass
class OutlineWizardStep:
    runtime: object
    title: str = "outline"
    description: str = "Plan the slide-by-slide structure."

    async def render(self, console, project: DeckProject) -> StepResult:
        result = await self.runtime.run(
            agent_id="outliner",
            session_id=project.slug,
            input_text="",
        )
        outline: SlideOutline = getattr(result, "parsed", None) or \
            SlideOutline.model_validate(result.state.get("outline", {}))

        if console is not None:
            self._render_table(console, outline)

        action = await Wizard.select(
            "Outline action?", choices=["accept", "regenerate", "abort"], default="accept",
        )
        if action == "regenerate":
            return StepResult(status="retry")
        if action == "abort":
            return StepResult(status="aborted")

        project.outline = outline
        project.stage = "theme"
        return StepResult(status="completed")

    @staticmethod
    def _render_table(console, outline: SlideOutline):
        from rich.table import Table
        table = Table(title="Outline")
        table.add_column("#")
        table.add_column("Type")
        table.add_column("Title")
        table.add_column("Key Points")
        for s in outline.slides:
            table.add_row(str(s.index), s.type, s.title, "; ".join(s.key_points))
        console.print(table)
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_outline_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/outline.py tests/unit/test_outline_wizard.py
rtk git commit -m "feat(pptx): OutlineWizardStep with accept/regenerate/abort choice"
```

---

### Task 21: Stage 5 — `ThemeWizard`

**Files:**
- Create: `examples/pptx_generator/wizard/theme.py`
- Create: `tests/unit/test_theme_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_theme_wizard.py
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.state import (
    DeckProject, FontPairing, IntentReport, Palette, ThemeSelection,
)
from examples.pptx_generator.wizard.theme import ThemeWizardStep


@pytest.mark.asyncio
async def test_theme_accepted(monkeypatch):
    theme = ThemeSelection(
        palette=Palette(primary="111111", secondary="222222",
                        accent="333333", light="444444", bg="555555"),
        fonts=FontPairing(heading="Arial", body="Arial", cjk="Microsoft YaHei"),
        style="sharp", page_badge_style="circle",
    )
    runtime = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(
        parsed=theme, state={"theme": theme.model_dump(mode="json")},
    )))
    monkeypatch.setattr("examples.pptx_generator.wizard.theme.Wizard.select",
                        AsyncMock(return_value="accept"))
    step = ThemeWizardStep(runtime=runtime)
    project = DeckProject(
        slug="x", created_at=datetime.now(timezone.utc), stage="theme",
        intent=IntentReport(topic="t", audience="a", purpose="pitch", tone="formal",
                            slide_count_hint=5, required_sections=[], visuals_hint=[],
                            research_queries=[], language="zh"),
    )
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    assert project.theme is not None
    assert project.stage == "slides"
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/theme.py
from __future__ import annotations

from dataclasses import dataclass

from openagents.cli.wizard import StepResult, Wizard

from ..state import DeckProject, ThemeSelection


@dataclass
class ThemeWizardStep:
    runtime: object
    title: str = "theme"
    description: str = "Pick palette, fonts, and style."

    async def render(self, console, project: DeckProject) -> StepResult:
        result = await self.runtime.run(
            agent_id="theme-selector",
            session_id=project.slug,
            input_text="",
        )
        theme: ThemeSelection = getattr(result, "parsed", None) or \
            ThemeSelection.model_validate(result.state.get("theme", {}))

        if console is not None:
            self._render_preview(console, theme)

        action = await Wizard.select(
            "Theme action?", choices=["accept", "try another", "custom hex", "abort"],
            default="accept",
        )
        if action == "try another":
            return StepResult(status="retry")
        if action == "abort":
            return StepResult(status="aborted")
        if action == "custom hex":
            primary = await Wizard.text("primary hex (6 chars, no '#')", default=theme.palette.primary)
            theme.palette.primary = primary

        project.theme = theme
        project.stage = "slides"
        return StepResult(status="completed")

    @staticmethod
    def _render_preview(console, theme: ThemeSelection):
        from rich.columns import Columns
        from rich.panel import Panel
        p = theme.palette
        swatches = [
            Panel(f"[bold]{name}[/bold]\n#{val}", style=f"on #{val}",
                  width=20, height=4)
            for name, val in [
                ("primary", p.primary), ("secondary", p.secondary),
                ("accent", p.accent), ("light", p.light), ("bg", p.bg),
            ]
        ]
        console.print(Columns(swatches))
        console.print(
            f"Heading: [bold]{theme.fonts.heading}[/bold]   "
            f"Body: {theme.fonts.body}   CJK: {theme.fonts.cjk}"
        )
        console.print(f"Style: {theme.style}   Badge: {theme.page_badge_style}")
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_theme_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/theme.py tests/unit/test_theme_wizard.py
rtk git commit -m "feat(pptx): ThemeWizardStep with palette preview via Rich Columns"
```

---

### Task 22: Stage 6 — `SlideGeneratorWizard` (parallel, retry)

**Files:**
- Create: `examples/pptx_generator/wizard/slides.py`
- Create: `tests/unit/test_slides_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_slides_wizard.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.state import (
    DeckProject, IntentReport, Palette, FontPairing, ResearchFindings,
    SlideIR, SlideOutline, SlideSpec, ThemeSelection,
)
from examples.pptx_generator.wizard.slides import SlideGeneratorWizardStep


def _base_project(n=3):
    specs = [SlideSpec(index=i, type="content", title=f"S{i}",
                       key_points=[], sources_cited=[]) for i in range(1, n + 1)]
    return DeckProject(
        slug="x", created_at=datetime.now(timezone.utc), stage="slides",
        intent=IntentReport(topic="t", audience="a", purpose="pitch", tone="formal",
                            slide_count_hint=n, required_sections=[], visuals_hint=[],
                            research_queries=[], language="zh"),
        research=ResearchFindings(),
        outline=SlideOutline(slides=specs),
        theme=ThemeSelection(
            palette=Palette(primary="111111", secondary="222222",
                            accent="333333", light="444444", bg="555555"),
            fonts=FontPairing(heading="Arial", body="Arial", cjk="Microsoft YaHei"),
            style="sharp", page_badge_style="circle",
        ),
    )


@pytest.mark.asyncio
async def test_generates_all_slides_in_parallel():
    import json

    async def fake_run(*, agent_id, session_id, input_text, deps=None):
        payload = json.loads(input_text)
        i = payload["target_spec"]["index"]
        return SimpleNamespace(parsed=SlideIR(
            index=i, type="content",
            slots={"title": f"S{i}", "body_blocks": []},
            generated_at=datetime.now(timezone.utc),
        ))

    runtime = SimpleNamespace(run=AsyncMock(side_effect=fake_run))
    step = SlideGeneratorWizardStep(runtime=runtime, concurrency=3)
    project = _base_project(n=3)
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    assert len(project.slides) == 3
    assert project.stage == "compile"
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/slides.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from openagents.cli.wizard import StepResult

from ..state import DeckProject, SlideIR


@dataclass
class SlideGeneratorWizardStep:
    runtime: object
    concurrency: int = 3
    title: str = "slides"
    description: str = "Generate each slide's content JSON and convert to IR."

    async def render(self, console, project: DeckProject) -> StepResult:
        assert project.outline is not None
        sem = asyncio.Semaphore(self.concurrency)

        async def run_one(spec) -> SlideIR:
            import json as _json
            async with sem:
                payload = _json.dumps({
                    "target_spec": spec.model_dump(),
                    "theme": project.theme.model_dump() if project.theme else {},
                }, ensure_ascii=False)
                result = await self.runtime.run(
                    agent_id="slide-generator",
                    session_id=project.slug,
                    input_text=payload,
                )
                parsed = getattr(result, "parsed", None)
                if parsed is None:
                    raise RuntimeError(f"slide {spec.index} returned no SlideIR")
                return parsed

        tasks = [run_one(s) for s in project.outline.slides]
        slides = await asyncio.gather(*tasks, return_exceptions=False)
        project.slides = sorted(slides, key=lambda s: s.index)
        project.stage = "compile"

        if console is not None:
            ok = sum(1 for s in project.slides if s.type != "freeform")
            fallback = sum(1 for s in project.slides if s.type == "freeform")
            console.print(
                f"Generated {len(project.slides)} slides "
                f"([green]{ok} strict[/green], [yellow]{fallback} freeform[/yellow])"
            )
        return StepResult(status="completed")
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_slides_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/slides.py tests/unit/test_slides_wizard.py
rtk git commit -m "feat(pptx): SlideGeneratorWizardStep parallel per-slide runs"
```

---

### Task 23: Stage 7 — `CompileQAWizard`

**Files:**
- Create: `examples/pptx_generator/wizard/compile_qa.py`
- Create: `tests/unit/test_compile_qa_wizard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_compile_qa_wizard.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.state import (
    DeckProject, FontPairing, IntentReport, Palette, ResearchFindings,
    SlideIR, SlideOutline, SlideSpec, ThemeSelection,
)
from examples.pptx_generator.wizard.compile_qa import CompileQAWizardStep


def _project(tmp_path):
    theme = ThemeSelection(
        palette=Palette(primary="111111", secondary="222222",
                        accent="333333", light="444444", bg="555555"),
        fonts=FontPairing(heading="Arial", body="Arial", cjk="Microsoft YaHei"),
        style="sharp", page_badge_style="circle",
    )
    p = DeckProject(
        slug="x", created_at=datetime.now(timezone.utc), stage="compile",
        intent=IntentReport(topic="t", audience="a", purpose="pitch", tone="formal",
                            slide_count_hint=1, required_sections=[], visuals_hint=[],
                            research_queries=[], language="zh"),
        research=ResearchFindings(),
        outline=SlideOutline(slides=[SlideSpec(index=1, type="cover",
                                                title="T", key_points=[], sources_cited=[])]),
        theme=theme,
        slides=[SlideIR(index=1, type="cover",
                         slots={"title": "T"},
                         generated_at=datetime.now(timezone.utc))],
    )
    return p, theme


@pytest.mark.asyncio
async def test_writes_slide_files_and_compiles(tmp_path):
    calls = []
    async def fake_invoke(params, context=None):
        calls.append(params["command"])
        return {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False, "truncated": False}

    tool = SimpleNamespace(invoke=fake_invoke)
    step = CompileQAWizardStep(
        shell_tool=tool,
        output_root=tmp_path,
        templates_dir=Path("examples/pptx_generator/templates"),
    )
    project, _ = _project(tmp_path)
    result = await step.render(console=None, project=project)
    assert result.status == "completed"
    # slide file written
    slide_file = tmp_path / project.slug / "slides" / "slide-01.js"
    assert slide_file.exists()
    # npm install + node compile + markitdown called
    assert any("npm" in " ".join(c) for c in calls)
    assert any("node" in " ".join(c) for c in calls)
    assert project.stage == "done"
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# examples/pptx_generator/wizard/compile_qa.py
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from openagents.cli.wizard import StepResult

from ..state import DeckProject


@dataclass
class CompileQAWizardStep:
    shell_tool: object  # ShellExecTool instance
    output_root: Path
    templates_dir: Path
    title: str = "compile"
    description: str = "Render JS, run PptxGenJS, QA via MarkItDown."

    async def render(self, console, project: DeckProject) -> StepResult:
        out_dir = Path(self.output_root) / project.slug / "slides"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "output").mkdir(exist_ok=True)

        for slide in project.slides:
            filename = f"slide-{slide.index:02d}.js"
            path = out_dir / filename
            if slide.type == "freeform" and slide.freeform_js:
                path.write_text(slide.freeform_js, encoding="utf-8")
            else:
                template = (self.templates_dir / f"{slide.type}.js").read_text(encoding="utf-8")
                content = (
                    f"const base = (function() {{ var module = {{ exports: {{}} }};\n"
                    f"{template}\n"
                    f"return module.exports; }})();\n"
                    f"const slots = {json.dumps(slide.slots)};\n"
                    f"function createSlide(pres, theme) {{ return base.createSlide(pres, theme, slots); }}\n"
                    f"module.exports = {{ createSlide }};\n"
                )
                path.write_text(content, encoding="utf-8")

        assert project.theme is not None
        compile_js = _compile_script(project)
        (out_dir / "compile.js").write_text(compile_js, encoding="utf-8")

        # npm init/install if needed
        pkg = out_dir / "package.json"
        if not pkg.exists():
            pkg.write_text(json.dumps({
                "name": f"deck-{project.slug}",
                "private": True,
                "dependencies": {"pptxgenjs": "^3.12.0"},
            }, indent=2), encoding="utf-8")
            await self.shell_tool.invoke({"command": ["npm", "install"], "cwd": str(out_dir)}, context=None)

        await self.shell_tool.invoke({"command": ["node", "compile.js"], "cwd": str(out_dir)}, context=None)

        # QA: markitdown + rg
        pptx = out_dir / "output" / "presentation.pptx"
        md = out_dir / "output" / "presentation.md"
        if shutil.which("markitdown"):
            await self.shell_tool.invoke(
                {"command": ["markitdown", str(pptx), "-o", str(md)]},
                context=None,
            )

        project.stage = "done"
        return StepResult(status="completed")


def _compile_script(project: DeckProject) -> str:
    theme = project.theme.palette.model_dump()
    return f"""const pptxgen = require("pptxgenjs");

async function main() {{
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = {json.dumps(project.intent.topic if project.intent else "Deck")};
  const theme = {json.dumps({**theme})};
{"  ".join(f'\n  require("./slide-{s.index:02d}.js").createSlide(pres, theme);' for s in project.slides)}
  await pres.writeFile({{ fileName: "./output/presentation.pptx" }});
}}

main().catch((err) => {{ console.error(err); process.exitCode = 1; }});
"""
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/unit/test_compile_qa_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/wizard/compile_qa.py tests/unit/test_compile_qa_wizard.py
rtk git commit -m "feat(pptx): CompileQAWizardStep renders JS, compiles, and runs MarkItDown QA"
```

---

### Task 24: Wire CLI `run_wizard` to all 7 steps

**Files:**
- Modify: `examples/pptx_generator/cli.py`
- Create: `tests/integration/test_pptx_generator_example.py`

- [ ] **Step 1: Write integration test (end-to-end mocked)**

```python
# tests/integration/test_pptx_generator_example.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.pptx_generator.cli import run_wizard
from examples.pptx_generator.state import DeckProject


@pytest.mark.asyncio
async def test_end_to_end_all_stages_mocked(tmp_path, monkeypatch):
    """Run the full wizard with every external service mocked."""
    monkeypatch.setenv("PPTX_AGENT_OUTPUTS", str(tmp_path))
    monkeypatch.setenv("LLM_API_KEY", "fake")
    monkeypatch.setenv("LLM_API_BASE", "https://fake")
    monkeypatch.setenv("LLM_MODEL", "fake-model")

    # Mock every Wizard prompt to default accept path
    from openagents.cli import wizard as wiz
    monkeypatch.setattr(wiz.Wizard, "confirm", AsyncMock(return_value=True))
    monkeypatch.setattr(wiz.Wizard, "select", AsyncMock(return_value="accept"))
    monkeypatch.setattr(wiz.Wizard, "multi_select", AsyncMock(return_value=[]))
    monkeypatch.setattr(wiz.Wizard, "password", AsyncMock(return_value="sk-fake"))
    monkeypatch.setattr(wiz.Wizard, "text", AsyncMock(return_value=""))

    # Construct project
    project = DeckProject(
        slug="int-test", created_at=datetime.now(timezone.utc), stage="intent",
    )

    # Expect run_wizard to accept an override parameter `runtime_factory` / `shell_tool`
    # that lets tests inject fakes. (Task 24 implementation must expose these.)
    from examples.pptx_generator import cli as cli_mod

    intent = {"topic": "t", "audience": "a", "purpose": "pitch", "tone": "formal",
              "slide_count_hint": 3, "required_sections": [], "visuals_hint": [],
              "research_queries": [], "language": "zh"}

    async def fake_runtime_run(*, agent_id, session_id, input_text, deps=None):
        from examples.pptx_generator.state import (
            IntentReport, SlideOutline, SlideSpec, ThemeSelection, Palette,
            FontPairing, SlideIR, ResearchFindings,
        )
        if agent_id == "intent-analyst":
            return SimpleNamespace(parsed=IntentReport(**intent), state={"intent": intent})
        if agent_id == "research-agent":
            return SimpleNamespace(parsed=ResearchFindings(), state={"research": {}})
        if agent_id == "outliner":
            outline = SlideOutline(slides=[
                SlideSpec(index=1, type="cover", title="T", key_points=[], sources_cited=[]),
                SlideSpec(index=2, type="content", title="W", key_points=[], sources_cited=[]),
                SlideSpec(index=3, type="closing", title="E", key_points=[], sources_cited=[]),
            ])
            return SimpleNamespace(parsed=outline, state={"outline": outline.model_dump()})
        if agent_id == "theme-selector":
            theme = ThemeSelection(
                palette=Palette(primary="111111", secondary="222222",
                                accent="333333", light="444444", bg="555555"),
                fonts=FontPairing(heading="Arial", body="Arial", cjk="Microsoft YaHei"),
                style="sharp", page_badge_style="circle",
            )
            return SimpleNamespace(parsed=theme, state={"theme": theme.model_dump()})
        if agent_id == "slide-generator":
            payload = json.loads(input_text)
            i = payload["target_spec"]["index"]
            return SimpleNamespace(parsed=SlideIR(
                index=i, type=payload["target_spec"]["type"],
                slots={"title": f"S{i}"},
                generated_at=datetime.now(timezone.utc),
            ))
        raise AssertionError(f"unexpected agent {agent_id}")

    fake_runtime = SimpleNamespace(run=fake_runtime_run)
    fake_shell = SimpleNamespace(invoke=AsyncMock(return_value={
        "exit_code": 0, "stdout": "", "stderr": "", "timed_out": False, "truncated": False,
    }))

    rc = await run_wizard(project, runtime=fake_runtime, shell_tool=fake_shell)
    assert rc == 0
    # project.json should exist
    assert (Path(tmp_path) / "int-test" / "project.json").exists()
    # slides dir populated
    assert (Path(tmp_path) / "int-test" / "slides" / "slide-01.js").exists()
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement `run_wizard` body**

Replace the stub in `examples/pptx_generator/cli.py`:

```python
# replace run_wizard in examples/pptx_generator/cli.py
from pathlib import Path as _Path

from openagents.cli.wizard import Wizard
from openagents.plugins.builtin.tool.shell_exec import ShellExecTool
from openagents.runtime.runtime import Runtime as _Runtime
from openagents.utils.env_doctor import (
    CliBinaryCheck, EnvVarCheck, EnvironmentDoctor,
    NodeVersionCheck, NpmCheck, PythonVersionCheck,
)

from .wizard.compile_qa import CompileQAWizardStep
from .wizard.env import EnvDoctorWizardStep
from .wizard.intent import IntentWizardStep
from .wizard.outline import OutlineWizardStep
from .wizard.research import ResearchWizardStep
from .wizard.slides import SlideGeneratorWizardStep
from .wizard.theme import ThemeWizardStep


async def run_wizard(project: DeckProject, *, resume: bool = False,
                      runtime=None, shell_tool=None) -> int:
    outputs = outputs_root()
    save_project(project, root=outputs)

    if runtime is None:
        runtime = _Runtime.from_config(
            _Path("examples/pptx_generator/agent.json")
        )
    if shell_tool is None:
        shell_tool = ShellExecTool(config={
            "command_allowlist": ["node", "npx", "npm", "markitdown"],
            "env_passthrough": ["PATH", "HOME", "APPDATA"],
            "default_timeout_ms": 300_000,
        })

    doctor = EnvironmentDoctor(
        checks=[
            PythonVersionCheck(min_version="3.10"),
            NodeVersionCheck(min_version="18"),
            NpmCheck(),
            CliBinaryCheck(name="markitdown",
                           install_hint="pip install 'markitdown[all]'",
                           get_url="https://pypi.org/project/markitdown/"),
            EnvVarCheck(name="LLM_API_KEY", required=True, description="LLM API key",
                         get_url="https://docs.anthropic.com/"),
            EnvVarCheck(name="LLM_API_BASE", required=True, description="LLM base URL",
                         get_url=None),
            EnvVarCheck(name="LLM_MODEL", required=True, description="LLM model name",
                         get_url=None),
            EnvVarCheck(name="TAVILY_API_KEY", required=False, description="Tavily API key",
                         get_url="https://tavily.com/"),
        ],
        dotenv_paths=[
            _Path(outputs) / project.slug / ".env",
            _Path("~/.config/pptx-agent/.env").expanduser(),
        ],
    )

    steps = [
        IntentWizardStep(runtime=runtime, topic_hint=None),
        EnvDoctorWizardStep(doctor=doctor),
        ResearchWizardStep(runtime=runtime),
        OutlineWizardStep(runtime=runtime),
        ThemeWizardStep(runtime=runtime),
        SlideGeneratorWizardStep(runtime=runtime, concurrency=3),
        CompileQAWizardStep(
            shell_tool=shell_tool,
            output_root=outputs,
            templates_dir=_Path("examples/pptx_generator/templates"),
        ),
    ]

    wizard = Wizard(steps=steps, project=project)
    outcome = await wizard.resume(from_step=project.stage) if resume else await wizard.run()
    save_project(project, root=outputs)
    return 0 if outcome == "completed" else 1
```

- [ ] **Step 4: Run, expect pass**

```bash
uv run pytest tests/integration/test_pptx_generator_example.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add examples/pptx_generator/cli.py tests/integration/test_pptx_generator_example.py
rtk git commit -m "feat(pptx): wire full 7-step wizard + end-to-end integration test"
```

---

## Phase E — Docs, Final Polish

### Task 25: Update docs

**Files:**
- Modify: `docs/examples.md`, `docs/examples.en.md`
- Modify: `docs/seams-and-extension-points.md`, `docs/seams-and-extension-points.en.md`
- Modify: `docs/builtin-tools.md`, `docs/builtin-tools.en.md`
- Create: `docs/pptx-agent-cli.md`, `docs/pptx-agent-cli.en.md`

- [ ] **Step 1: Append pptx-generator section to `docs/examples.md`**

Add near the end:

```markdown
## pptx-agent （生产级 PPT 生成 CLI）

位置：`examples/pptx_generator/`。7 阶段交互式向导（意图 → 环境 → 研究 → 大纲 → 主题 → 切片 → 编译QA），基于 Rich+questionary 的 TUI，默认通过 Tavily MCP 联网研究。

- 安装：`uv add "io-openagent-sdk[pptx]"`
- 运行：`pptx-agent new --topic "..."` 或 `pptx-agent resume <slug>`
- 详细 CLI 说明：`docs/pptx-agent-cli.md`
```

Mirror the same section in `docs/examples.en.md` (English).

- [ ] **Step 2: Add `markdown_memory` to memory builtin table in `docs/seams-and-extension-points.md`**

Find the `memory` row table and add:

```markdown
| `markdown_memory` | 可读的文件型长期记忆（用户目标 / 反馈 / 决策 / 引用）；跨会话持久化到 `MEMORY.md` 索引 + section 子文件 |
```

Mirror in `.en.md`.

- [ ] **Step 3: Append to `docs/builtin-tools.md`**

```markdown
### `shell_exec`
受限 shell 命令执行工具：`asyncio.create_subprocess_exec` + allowlist + timeout。Config: `cwd`, `env_passthrough`, `command_allowlist`, `default_timeout_ms`, `capture_bytes`.

### `tavily_search`
Tavily REST 搜索工具（作为 Tavily MCP 的 fallback）。API key 从 `TAVILY_API_KEY` 读取。

### `remember_preference`
与 `markdown_memory` 配套的工具：把 `{category, rule, reason}` 推入 `context.state['_pending_memory_writes']`，由 `markdown_memory.writeback` 持久化。
```

Mirror in `.en.md`.

- [ ] **Step 4: Write `docs/pptx-agent-cli.md`**

```markdown
# pptx-agent CLI 使用指南

## 安装

```bash
uv add "io-openagent-sdk[pptx]"
```

还需要系统级依赖：Python ≥3.10、Node.js ≥18、npm、`markitdown`（Python 包）。首次运行时，CLI 会检测并引导你安装缺项。

## 命令

- `pptx-agent new [--topic "..."] [--slug ...]` — 开始新 deck
- `pptx-agent resume <slug>` — 恢复一个被中断的 deck
- `pptx-agent memory [--section user_feedback]` — 查看已保存的用户偏好

## 7 阶段流程

1. **Intent Analysis** — 把你的自然语言描述转成结构化 IntentReport
2. **Environment Check** — 检查 Python / Node / npm / markitdown / API keys，缺项交互修复
3. **Research** — 用 Tavily MCP（或 REST fallback）联网搜索
4. **Outline** — 生成 slide-by-slide 的大纲，支持接受 / 重新生成 / 中止
5. **Theme** — 从调色板 / 字体 / 风格目录里选择
6. **Slide Generation** — 每张 slide 独立的 agent run，并行生成；JSON schema 校验失败自动重试，仍失败时 fallback 到 freeform
7. **Compile + QA** — 生成 PptxGenJS 源码、运行 `node compile.js`、`markitdown` 回读校验

## Resume

所有项目状态持久化在 `outputs/<slug>/project.json`（atomic write，每次写入前备份）。任何阶段 Ctrl+C 退出后，都可以 `pptx-agent resume <slug>` 从该阶段恢复。

## Keys & `.env`

- 必需：`LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL`
- 可选：`TAVILY_API_KEY`（启用联网研究）
- 用户级 `.env`：`~/.config/pptx-agent/.env`（跨项目共享）
- 项目级 `.env`：`outputs/<slug>/.env`（覆盖用户级）
```

Mirror in `docs/pptx-agent-cli.en.md`.

- [ ] **Step 5: Commit**

```bash
rtk git add docs/
rtk git commit -m "docs: add pptx-agent example, CLI guide, and markdown_memory to seam map"
```

---

### Task 26: CHANGELOG 0.4.0 + final verification

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Prepend 0.4.0 block to CHANGELOG.md**

```markdown
## [0.4.0] - 2026-04-18

### Added

- New builtin tool `shell_exec`: allowlist-aware `asyncio.create_subprocess_exec` wrapper with cwd/env/timeout/capture-bytes controls.
- New builtin tool `tavily_search`: REST fallback for Tavily MCP.
- New builtin memory `markdown_memory`: human-readable file-backed long-term memory (MEMORY.md index + per-section files) for user goals / feedback / decisions / references.
- New builtin tool `remember_preference`: companion to `markdown_memory` for agent-side preference capture.
- New utility `openagents.utils.env_doctor`: reusable environment check framework with built-in Python/Node/npm/CLI/EnvVar checks and interactive dotenv fix.
- New CLI helper `openagents.cli.wizard`: Rich+questionary Wizard component for building multi-step interactive CLIs.
- New example app `examples/pptx_generator/`: production-grade 7-stage interactive PPT generator CLI (`pptx-agent`).

### Changed

- Bumped `version` to 0.4.0.
- New `pptx` optional-dependency group.

### Docs

- Added `docs/pptx-agent-cli.md` (Chinese + English mirror).
- Updated `docs/examples.md`, `docs/seams-and-extension-points.md`, `docs/builtin-tools.md`.
```

- [ ] **Step 2: Run full suite + coverage**

```bash
uv run coverage run -m pytest && uv run coverage report
```

Expected: all tests pass; total coverage ≥ 92%. `markdown_memory`, `shell_exec`, `tavily_search`, `memory_tools`, `env_doctor`, and `wizard` are NOT in `coverage.omit`.

- [ ] **Step 3: Commit**

```bash
rtk git add CHANGELOG.md
rtk git commit -m "chore: release 0.4.0 — pptx-agent example + 6 new SDK builtins"
```

- [ ] **Step 4: Final smoke test**

```bash
uv run pytest -q
uv run openagents list-plugins | grep -E "markdown_memory|shell_exec|tavily_search|remember_preference"
```

Expected: all tests pass; all four new plugins listed.

---

## Self-Review Checklist

Before handing off:

- [ ] Every spec section (Goal, Architecture, New SDK Builtins, Data Models, Slide Template Slot Schemas, 7-Stage Pipeline, UI Layout, Memory Integration, Error Handling, Testing Strategy, Packaging, Skill Integration, Version, Docs Updates) has at least one task implementing or documenting it.
- [ ] No placeholder text ("TBD", "TODO", "similar to Task N", "add appropriate error handling").
- [ ] Types are consistent: `DeckProject` / `IntentReport` / `SlideIR` / `StepResult` signatures match across all tasks that reference them.
- [ ] Coverage config remains at floor 92% and newly added builtin files are NOT in `coverage.omit`.
- [ ] CLI entry script matches between `pyproject.toml` (`pptx-agent = "examples.pptx_generator.cli:main_sync"`) and `examples/pptx_generator/cli.py` (exports `main_sync`).
- [ ] Integration test (Task 24) exercises the whole wizard end-to-end without hitting any real network or subprocess.

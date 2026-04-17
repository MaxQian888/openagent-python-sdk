# Plugin Interface Seam Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Absorb three top-level seams (`execution_policy`, `followup_resolver`, `response_repair_policy`) into override methods on `ToolExecutorPlugin` and `PatternPlugin`, reducing seam count from 11 to 8.

**Architecture:** `ToolExecutorPlugin` gains `evaluate_policy()` (default allow-all), called internally from `execute()`. `PatternPlugin` gains `resolve_followup()` and `repair_empty_response()` (both default `None`/abstain), called by all three builtin pattern classes. Three seam slots are removed from the loader, config schema, RunContext, registry, and public API. A new `FilesystemAwareExecutor` replaces the old `execution_policy: filesystem` config pattern.

**Tech Stack:** Python, Pydantic, pytest, uv

**Spec:** `docs/superpowers/specs/2026-04-18-plugin-interface-seam-consolidation-design.md`

---

## File Map

**Create:**
- `openagents/plugins/builtin/tool_executor/filesystem_aware.py` — new `FilesystemAwareExecutor`
- `tests/unit/test_filesystem_aware_executor.py`
- `tests/unit/test_pattern_followup_repair_methods.py`

**Modify:**
- `openagents/interfaces/tool.py` — add `evaluate_policy` to `ToolExecutorPlugin`
- `openagents/interfaces/pattern.py` — add two methods, remove three params from `setup()`
- `openagents/interfaces/run_context.py` — remove three dead fields
- `openagents/plugins/builtin/runtime/default_runtime.py` — remove `_BoundTool._policy`, fix dispatch, remove 6 resolver methods
- `openagents/plugins/builtin/execution_policy/filesystem.py` — decouple from `BasePlugin`
- `openagents/plugins/builtin/execution_policy/network.py` — decouple from `BasePlugin`
- `openagents/plugins/builtin/execution_policy/composite.py` — compose helpers directly
- `openagents/plugins/builtin/pattern/react.py` — activate followup/repair
- `openagents/plugins/builtin/pattern/reflexion.py` — activate followup/repair
- `openagents/plugins/builtin/pattern/plan_execute.py` — activate followup/repair
- `openagents/plugins/registry.py` — remove three seam registries
- `openagents/decorators.py` — remove three decorators + six accessors
- `openagents/__init__.py` — remove from imports and `__all__`
- `openagents/config/schema.py` — remove three config fields
- `openagents/plugins/loader.py` — remove three load functions and `AgentPlugins` fields
- `openagents/cli/list_plugins_cmd.py` — remove three seam entries
- `openagents/cli/validate_cmd.py` — remove three seam names
- `skills/openagent-agent-builder/src/openagent_agent_builder/render.py` — emit `filesystem_aware` executor instead of `execution_policy`
- `docs/seams-and-extension-points.md` — update section 2, 9, table

---

## Task 1: Add `evaluate_policy` to `ToolExecutorPlugin`

**Files:**
- Modify: `openagents/interfaces/tool.py`
- Create: `tests/unit/test_tool_executor_evaluate_policy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_tool_executor_evaluate_policy.py
import pytest
from openagents.interfaces.tool import (
    ToolExecutorPlugin, ToolExecutionRequest, ToolExecutionResult, PolicyDecision
)


class _MinimalTool:
    async def invoke(self, params, context):
        return "ok"


@pytest.mark.asyncio
async def test_default_evaluate_policy_allows_all():
    executor = ToolExecutorPlugin()
    req = ToolExecutionRequest(tool_id="t", tool=_MinimalTool(), params={})
    decision = await executor.evaluate_policy(req)
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_execute_calls_evaluate_policy_and_denies():
    class DenyExecutor(ToolExecutorPlugin):
        async def evaluate_policy(self, request):
            return PolicyDecision(allowed=False, reason="nope")

    executor = DenyExecutor()
    req = ToolExecutionRequest(tool_id="t", tool=_MinimalTool(), params={})
    result = await executor.execute(req)
    assert result.success is False
    assert "nope" in result.error


@pytest.mark.asyncio
async def test_execute_calls_evaluate_policy_and_allows():
    executor = ToolExecutorPlugin()
    req = ToolExecutionRequest(tool_id="t", tool=_MinimalTool(), params={})
    result = await executor.execute(req)
    assert result.success is True
    assert result.data == "ok"
```

- [ ] **Step 2: Run to confirm FAIL**

```
uv run pytest tests/unit/test_tool_executor_evaluate_policy.py -v
```
Expected: FAIL — `evaluate_policy` not defined on `ToolExecutorPlugin`

- [ ] **Step 3: Add `evaluate_policy` to `ToolExecutorPlugin` and call it in `execute`**

In `openagents/interfaces/tool.py`, update `ToolExecutorPlugin`:

```python
class ToolExecutorPlugin(BasePlugin):
    async def evaluate_policy(self, request: ToolExecutionRequest) -> PolicyDecision:
        """Override to restrict tool execution. Default: allow all."""
        return PolicyDecision(allowed=True)

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        decision = await self.evaluate_policy(request)
        if not decision.allowed:
            return ToolExecutionResult(
                tool_id=request.tool_id,
                success=False,
                error=f"policy denied: {decision.reason}",
            )
        try:
            data = await request.tool.invoke(request.params or {}, request.context)
            return ToolExecutionResult(tool_id=request.tool_id, success=True, data=data)
        except OpenAgentsError as exc:
            return ToolExecutionResult(
                tool_id=request.tool_id, success=False, error=str(exc), exception=exc
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_id=request.tool_id, success=False, error=str(exc),
                exception=ToolError(str(exc), tool_name=request.tool_id),
            )
```

- [ ] **Step 4: Run to confirm PASS**

```
uv run pytest tests/unit/test_tool_executor_evaluate_policy.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/interfaces/tool.py tests/unit/test_tool_executor_evaluate_policy.py
rtk git commit -m "feat(interfaces): add ToolExecutorPlugin.evaluate_policy() with default allow-all"
```

---

## Task 2: Add `resolve_followup` and `repair_empty_response` to `PatternPlugin`

**Files:**
- Modify: `openagents/interfaces/pattern.py`
- Create: `tests/unit/test_pattern_followup_repair_methods.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_pattern_followup_repair_methods.py
import pytest
from unittest.mock import MagicMock
from openagents.interfaces.pattern import PatternPlugin


def _make_pattern():
    p = PatternPlugin()
    p.context = MagicMock()
    return p


@pytest.mark.asyncio
async def test_resolve_followup_default_returns_none():
    p = _make_pattern()
    result = await p.resolve_followup(context=p.context)
    assert result is None


@pytest.mark.asyncio
async def test_repair_empty_response_default_returns_none():
    p = _make_pattern()
    result = await p.repair_empty_response(
        context=p.context,
        messages=[],
        assistant_content=[],
        stop_reason=None,
        retries=0,
    )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_followup_can_be_overridden():
    from openagents.interfaces.followup import FollowupResolution

    class MyPattern(PatternPlugin):
        async def resolve_followup(self, *, context):
            return FollowupResolution(status="resolved", output="42")

    p = MyPattern()
    p.context = MagicMock()
    result = await p.resolve_followup(context=p.context)
    assert result.status == "resolved"
    assert result.output == "42"
```

- [ ] **Step 2: Run to confirm FAIL**

```
uv run pytest tests/unit/test_pattern_followup_repair_methods.py -v
```

- [ ] **Step 3: Add two methods to `PatternPlugin` in `openagents/interfaces/pattern.py`**

Add after the `finalize` method:

```python
async def resolve_followup(
    self, *, context: "RunContext[Any]"
) -> "FollowupResolution | None":
    """Override to answer follow-ups locally. Return None to abstain (call LLM)."""
    return None

async def repair_empty_response(
    self,
    *,
    context: "RunContext[Any]",
    messages: list[dict[str, Any]],
    assistant_content: list[dict[str, Any]],
    stop_reason: str | None,
    retries: int,
) -> "ResponseRepairDecision | None":
    """Override to handle bad LLM responses. Return None to abstain (propagate)."""
    return None
```

Add to `TYPE_CHECKING` imports at top of file:
```python
from .followup import FollowupResolution
from .response_repair import ResponseRepairDecision
```

- [ ] **Step 4: Run to confirm PASS**

```
uv run pytest tests/unit/test_pattern_followup_repair_methods.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/interfaces/pattern.py tests/unit/test_pattern_followup_repair_methods.py
rtk git commit -m "feat(interfaces): add PatternPlugin.resolve_followup() and repair_empty_response()"
```

---

## Task 3: Remove three params from `PatternPlugin.setup()` and clean RunContext

**Files:**
- Modify: `openagents/interfaces/pattern.py`
- Modify: `openagents/interfaces/run_context.py`

- [ ] **Step 1: Remove `execution_policy`, `followup_resolver`, `response_repair_policy` from `PatternPlugin.setup()` signature**

In `openagents/interfaces/pattern.py`, `setup()` currently accepts these three params and passes them to `RunContext`. Remove them from the signature and from the `RunContext(...)` constructor call inside `setup()`.

Before (relevant lines):
```python
async def setup(
    self,
    ...
    tool_executor: "ToolExecutor | None" = None,
    execution_policy: "ExecutionPolicy | None" = None,
    followup_resolver: "FollowupResolverPlugin | None" = None,
    response_repair_policy: "ResponseRepairPolicyPlugin | None" = None,
    ...
) -> None:
    self.context = RunContext[Any](
        ...
        execution_policy=execution_policy,
        followup_resolver=followup_resolver,
        response_repair_policy=response_repair_policy,
        ...
    )
```

After: remove the three params and the three `RunContext` keyword args.

Also remove the TYPE_CHECKING imports for `ExecutionPolicy`, `FollowupResolverPlugin`, `ResponseRepairPolicyPlugin` from the top of the file (verify they aren't used elsewhere in the file first).

- [ ] **Step 2: Remove three dead fields from `RunContext`**

In `openagents/interfaces/run_context.py`, remove:
```python
execution_policy: Any | None = None      # line 43
followup_resolver: Any | None = None     # line 44
response_repair_policy: Any | None = None  # line 45
```

- [ ] **Step 2b: Run tests after RunContext cleanup**

```
uv run pytest -q 2>&1 | head -40
```

Note failures — these are the sites still referencing the removed fields. They will be fixed in Task 4.

- [ ] **Step 3: Run full test suite to see accumulated breakage**

```
uv run pytest -q 2>&1 | head -60
```

Note which tests fail — they'll be fixed in subsequent tasks.

- [ ] **Step 4: Commit interface cleanup**

```bash
rtk git add openagents/interfaces/pattern.py openagents/interfaces/run_context.py
rtk git commit -m "refactor(interfaces): remove three subordinate seam params from PatternPlugin.setup() and RunContext"
```

---

## Task 4: Update `_BoundTool` and `default_runtime` dispatch path

**Files:**
- Modify: `openagents/plugins/builtin/runtime/default_runtime.py`

This is the largest single change. Work section by section.

- [ ] **Step 1: Remove `_policy` from `_BoundTool`**

In `_BoundTool.__init__` (around line 164), remove the `policy: ExecutionPolicy` param and `self._policy = policy`.

In `_BoundTool.invoke` (around line 184), remove the policy evaluation block:
```python
# DELETE these lines:
decision = await self._policy.evaluate(request)
if not decision.allowed:
    raise PermissionError(decision.reason or f"Tool '{self._tool_id}' denied by policy")
```

The executor's `evaluate_policy()` now handles this internally.

- [ ] **Step 2: Update `_bind_tools` to drop policy param**

`_bind_tools` (line 692) currently takes `executor` and `policy`. Remove `policy` param. Update the `_BoundTool(...)` constructor call to drop `policy=policy`.

- [ ] **Step 3: Update `run()` call site for `_bind_tools`**

Around line 418, `_bind_tools(plugins.tools, tool_executor, execution_policy)` → `_bind_tools(plugins.tools, tool_executor)`.

- [ ] **Step 4: Remove the three resolve/get methods (~90 lines)**

Delete all six of these methods (lines 803–893 approx):
- `_get_execution_policy`
- `_resolve_execution_policy`
- `_get_followup_resolver`
- `_resolve_followup_resolver`
- `_get_response_repair_policy`
- `_resolve_response_repair_policy`

Also remove their call sites around line 384–388.

- [ ] **Step 5: Update `_setup_pattern` to drop three params**

`_setup_pattern` (line 717) currently passes `execution_policy`, `followup_resolver`, `response_repair_policy` to `pattern.setup()`. Remove these three kwargs from the `pattern.setup(...)` call. Remove the three params from `_setup_pattern`'s own signature.

Also remove lines 777–779 that set these on `context`:
```python
# DELETE:
context.execution_policy = execution_policy
context.followup_resolver = followup_resolver
context.response_repair_policy = response_repair_policy
```

- [ ] **Step 6: Remove references in `run()` and instrumentation**

Remove the three `_resolve_*` calls around line 384–388 and the three corresponding variables passed to `_setup_pattern` around line 431–432.

Also clean up the `__init__` instance vars (lines 313–316):
```python
# DELETE:
self._execution_policy: ExecutionPolicy | None = None
self._followup_resolver: FollowupResolverPlugin | None = None
self._response_repair_policy: ResponseRepairPolicyPlugin | None = None
```

And the instrumentation dict entries around lines 483–500 that report their class names.

- [ ] **Step 7: Remove unused imports at top of default_runtime.py**

Remove imports for `ExecutionPolicy`, `FollowupResolverPlugin`, `ResponseRepairPolicyPlugin` if no longer used.

- [ ] **Step 8: Run tests**

```
uv run pytest -q 2>&1 | head -60
```

- [ ] **Step 9: Commit**

```bash
rtk git add openagents/plugins/builtin/runtime/default_runtime.py
rtk git commit -m "refactor(runtime): remove policy/followup/repair from _BoundTool and DefaultRuntime dispatch"
```

---

## Task 5: Migrate execution policy builtins to standalone helpers

**Files:**
- Modify: `openagents/plugins/builtin/execution_policy/filesystem.py`
- Modify: `openagents/plugins/builtin/execution_policy/network.py`
- Modify: `openagents/plugins/builtin/execution_policy/composite.py`

The three policy classes become plain Python classes (no `BasePlugin` inheritance, no registry). Their logic is unchanged — only the inheritance and plugin machinery are stripped.

- [ ] **Step 1: Decouple `FilesystemExecutionPolicy`**

In `filesystem.py`:
- Change class declaration: `class FilesystemExecutionPolicy:` (remove `TypedConfigPluginMixin, ExecutionPolicyPlugin`)
- Remove `__init__` call to `super().__init__(config=config or {}, capabilities=set())` and `self._init_typed_config()`
- Inline the config parsing using Pydantic directly:
  ```python
  def __init__(self, config: dict[str, Any] | None = None):
      cfg = self.Config.model_validate(config or {})
      self._read_roots = _normalize_roots(cfg.read_roots)
      self._write_roots = _normalize_roots(cfg.write_roots)
      self._allow_tools = set(cfg.allow_tools)
      self._deny_tools = set(cfg.deny_tools)
  ```
- Rename `evaluate` → `evaluate_policy` to match the new interface name, keeping identical logic.
- Remove `ExecutionPolicyPlugin` import.

- [ ] **Step 2: Decouple `NetworkAllowlistExecutionPolicy`**

Same pattern in `network.py`:
- Remove `ExecutionPolicyPlugin` inheritance
- Remove `super().__init__(...)`
- Rename `evaluate` → `evaluate_policy`

- [ ] **Step 3: Refactor `CompositeExecutionPolicy`**

In `composite.py`, replace `_load_child` which calls `load_plugin("execution_policy", ...)` with direct instantiation. The composite now accepts a list of instantiated helper objects rather than config dicts. Simplest migration:

```python
class CompositePolicy:
    """Compose multiple policy helpers with AND/OR semantics."""

    def __init__(
        self,
        children: list[Any],  # FilesystemExecutionPolicy | NetworkAllowlistExecutionPolicy
        mode: Literal["all", "any"] = "all",
    ):
        self._children = children
        self._mode = mode

    async def evaluate_policy(self, request: ToolExecutionRequest) -> PolicyDecision:
        # ... same combine logic, calling child.evaluate_policy(request)
```

- [ ] **Step 4: Update `__init__.py` for the execution_policy package**

In `openagents/plugins/builtin/execution_policy/__init__.py`, update exports to reflect the new standalone nature.

- [ ] **Step 5: Run tests**

```
uv run pytest tests/unit/test_composite_execution_policy.py -v 2>&1 | head -40
```

Fix any failures. Tests for composite policy will need updating since the class API changed.

- [ ] **Step 6: Commit**

```bash
rtk git add openagents/plugins/builtin/execution_policy/
rtk git commit -m "refactor(execution-policy): convert to standalone helpers, remove BasePlugin inheritance"
```

---

## Task 6: Create `FilesystemAwareExecutor` *(depends on Task 5)*

**Files:**
- Create: `openagents/plugins/builtin/tool_executor/filesystem_aware.py`
- Create: `tests/unit/test_filesystem_aware_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_filesystem_aware_executor.py
import pytest
from openagents.plugins.builtin.tool_executor.filesystem_aware import FilesystemAwareExecutor
from openagents.interfaces.tool import ToolExecutionRequest, ToolExecutionSpec


class _MockTool:
    async def invoke(self, params, context):
        return "result"


def _req(tool_id="read_file", params=None, reads_files=False, writes_files=False):
    spec = ToolExecutionSpec(reads_files=reads_files, writes_files=writes_files)
    return ToolExecutionRequest(
        tool_id=tool_id, tool=_MockTool(), params=params or {}, execution_spec=spec
    )


@pytest.mark.asyncio
async def test_allow_tools_blocks_unlisted():
    ex = FilesystemAwareExecutor(config={"allow_tools": ["read_file"]})
    result = await ex.execute(_req(tool_id="write_file"))
    assert result.success is False
    assert "not in allow_tools" in result.error


@pytest.mark.asyncio
async def test_allow_tools_permits_listed():
    ex = FilesystemAwareExecutor(config={"allow_tools": ["read_file"]})
    result = await ex.execute(_req(tool_id="read_file", params={"path": "/tmp/x"}))
    assert result.success is True


@pytest.mark.asyncio
async def test_read_roots_blocks_outside_path(tmp_path):
    ex = FilesystemAwareExecutor(config={"read_roots": [str(tmp_path)]})
    result = await ex.execute(
        _req(tool_id="read_file", params={"path": "/etc/passwd"}, reads_files=True)
    )
    assert result.success is False
    assert "outside read_roots" in result.error


@pytest.mark.asyncio
async def test_no_config_allows_all():
    ex = FilesystemAwareExecutor()
    result = await ex.execute(_req(tool_id="anything"))
    assert result.success is True
```

- [ ] **Step 2: Run to confirm FAIL**

```
uv run pytest tests/unit/test_filesystem_aware_executor.py -v
```

- [ ] **Step 3: Implement `FilesystemAwareExecutor`**

```python
# openagents/plugins/builtin/tool_executor/filesystem_aware.py
"""ToolExecutor with filesystem policy embedded."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openagents.interfaces.tool import PolicyDecision, ToolExecutionRequest, ToolExecutorPlugin
from openagents.interfaces.typed_config import TypedConfigPluginMixin

from openagents.plugins.builtin.execution_policy.filesystem import FilesystemExecutionPolicy


class FilesystemAwareExecutor(TypedConfigPluginMixin, ToolExecutorPlugin):
    """ToolExecutor with filesystem policy built in.

    Config keys: allow_tools, deny_tools, read_roots, write_roots —
    same fields previously used by execution_policy: filesystem.

    Usage in agent config:
        tool_executor:
          type: filesystem_aware
          config:
            allow_tools: [read_file, list_files]
            read_roots: ["./src"]
            write_roots: ["./out"]
    """

    class Config(BaseModel):
        allow_tools: list[str] = Field(default_factory=list)
        deny_tools: list[str] = Field(default_factory=list)
        read_roots: list[str] = Field(default_factory=list)
        write_roots: list[str] = Field(default_factory=list)

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        self._init_typed_config()
        self._policy = FilesystemExecutionPolicy(config=config)

    async def evaluate_policy(self, request: ToolExecutionRequest) -> PolicyDecision:
        return await self._policy.evaluate_policy(request)
```

Register it in `openagents/plugins/builtin/tool_executor/__init__.py` and `openagents/plugins/registry.py` under the `"tool_executor"` registry with name `"filesystem_aware"`.

- [ ] **Step 4: Run to confirm PASS**

```
uv run pytest tests/unit/test_filesystem_aware_executor.py -v
```

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/plugins/builtin/tool_executor/filesystem_aware.py tests/unit/test_filesystem_aware_executor.py openagents/plugins/registry.py
rtk git commit -m "feat(tool-executor): add FilesystemAwareExecutor with embedded policy"
```

---

## Task 7: Activate `resolve_followup` and `repair_empty_response` in builtin patterns

**Files:**
- Modify: `openagents/plugins/builtin/pattern/react.py`
- Modify: `openagents/plugins/builtin/pattern/reflexion.py`
- Modify: `openagents/plugins/builtin/pattern/plan_execute.py`

First, inspect the three files to understand where the calls should go. You are looking for:
1. Where the pattern might handle a follow-up question (typically after the first LLM call, when the response looks like a follow-up rather than a new task)
2. Where the pattern handles empty/bad LLM responses (typically when `generate()` returns empty content)

The existing `ReActPattern` is the most important. Add calls at the appropriate points:

```python
# After receiving LLM response, before processing:
if is_followup_question(input_text):
    resolution = await self.resolve_followup(context=ctx)
    if resolution is not None and resolution.status == "resolved":
        return resolution.output

# When response is empty:
if not response_text:
    repair = await self.repair_empty_response(
        context=ctx,
        messages=messages,
        assistant_content=raw_content,
        stop_reason=stop_reason,
        retries=retries,
    )
    if repair is not None and repair.status == "repaired":
        response_text = repair.output
```

- [ ] **Step 1: Read `react.py` and identify insertion points**

```
uv run python -c "import ast, pathlib; print(ast.dump(ast.parse(pathlib.Path('openagents/plugins/builtin/pattern/react.py').read_text()), indent=2))" 2>/dev/null | head -5
```

Actually just read the file:
```
cat -n openagents/plugins/builtin/pattern/react.py
```

- [ ] **Step 2: Add `resolve_followup` call in `ReActPattern`**

Search `react.py` for the existing `followup_resolver` call site (e.g. `ctx.followup_resolver.resolve(...)`). **Replace** that delegation with `await self.resolve_followup(context=ctx)`. Do not add a new conditional branch — replace the existing one.

- [ ] **Step 3: Add `repair_empty_response` call in `ReActPattern`**

Search `react.py` for the existing `response_repair_policy` call site (e.g. `ctx.response_repair_policy.repair_empty_response(...)`). **Replace** that delegation with `await self.repair_empty_response(...)`. Replace, do not duplicate.

- [ ] **Step 4: Repeat for `reflexion.py` and `plan_execute.py`**

Apply the same insertions to the other two pattern files.

- [ ] **Step 5: Run pattern tests**

```
uv run pytest tests/unit/test_builtin_patterns_additional.py tests/unit/test_research_analyst_followup_pattern.py -v
```

Fix any failures.

- [ ] **Step 6: Commit**

```bash
rtk git add openagents/plugins/builtin/pattern/
rtk git commit -m "feat(patterns): activate resolve_followup and repair_empty_response in all builtin patterns"
```

---

## Task 8: Remove three seams from registry, decorators, and public API

**Files:**
- Modify: `openagents/plugins/registry.py`
- Modify: `openagents/decorators.py`
- Modify: `openagents/__init__.py`

- [ ] **Step 1: Clean `registry.py`**

Remove:
- Imports of `FilesystemExecutionPolicy`, `CompositeExecutionPolicy`, `NetworkAllowlistExecutionPolicy`
- Imports of `BasicResponseRepairPolicy`, `StrictJsonResponseRepairPolicy`
- Imports of followup resolver classes
- The `_EXECUTION_POLICY_REGISTRY`, `_FOLLOWUP_RESOLVER_REGISTRY`, `_RESPONSE_REPAIR_POLICY_REGISTRY` dicts
- Their entries in `PLUGIN_REGISTRY` (keys `"execution_policy"`, `"followup_resolver"`, `"response_repair_policy"`)
- Their entries in the `REQUIRED_METHODS` dict

- [ ] **Step 2: Clean `decorators.py`**

Remove the three decorator functions (`@execution_policy`, `@followup_resolver`, `@response_repair_policy`) and their associated private registries (`_EXECUTION_POLICY_REGISTRY`, `_FOLLOWUP_RESOLVER_REGISTRY`, `_RESPONSE_REPAIR_POLICY_REGISTRY`).

Remove accessor functions: `get_execution_policy`, `get_followup_resolver`, `get_response_repair_policy`, `list_execution_policies`, `list_followup_resolvers`, `list_response_repair_policies`.

- [ ] **Step 3: Clean `__init__.py`**

Remove the six symbols from imports and from `__all__`.

- [ ] **Step 4: Run tests**

```
uv run pytest -q 2>&1 | head -40
```

- [ ] **Step 5: Commit**

```bash
rtk git add openagents/plugins/registry.py openagents/decorators.py openagents/__init__.py
rtk git commit -m "refactor: remove execution_policy/followup_resolver/response_repair_policy from registry, decorators, and public API"
```

---

## Task 9: Remove three seams from config schema and plugin loader

**Files:**
- Modify: `openagents/config/schema.py`
- Modify: `openagents/plugins/loader.py`

- [ ] **Step 1: Clean `schema.py`**

Remove:
- `ExecutionPolicyRef`, `FollowupResolverRef`, `ResponseRepairPolicyRef` dataclasses/models (if they exist only for these seams)
- `execution_policy`, `followup_resolver`, `response_repair_policy` fields from `AgentConfig`
- The `__plugin_keys__` list entries for these three

Verify that `ExecutionPolicyRef` etc. are not used anywhere else before deleting.

- [ ] **Step 2: Clean `loader.py`**

Remove:
- `execution_policy`, `followup_resolver`, `response_repair_policy` fields from `AgentPlugins`
- `load_execution_policy_plugin`, `load_followup_resolver_plugin`, `load_response_repair_policy_plugin` functions
- Their call sites inside `load_agent_plugins`
- The three assignments in `load_agent_plugins` that set these on the returned `AgentPlugins`

- [ ] **Step 3: Run tests**

```
uv run pytest -q 2>&1 | head -40
```

- [ ] **Step 4: Commit**

```bash
rtk git add openagents/config/schema.py openagents/plugins/loader.py
rtk git commit -m "refactor(config+loader): remove three subordinate seam slots from AgentConfig and loader"
```

---

## Task 10: Clean CLI commands

**Files:**
- Modify: `openagents/cli/list_plugins_cmd.py`
- Modify: `openagents/cli/validate_cmd.py`

- [ ] **Step 1: Update `list_plugins_cmd.py`**

Remove the three registry imports and their entries from the display dict.

- [ ] **Step 2: Update `validate_cmd.py`**

Remove the three seam names from the allowed-keys list (lines 52–55) and from the comprehensive list (lines 74–75).

- [ ] **Step 3: Run CLI smoke test**

```
uv run python -m openagents.cli list-plugins 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
rtk git add openagents/cli/list_plugins_cmd.py openagents/cli/validate_cmd.py
rtk git commit -m "refactor(cli): remove three removed seam names from list-plugins and validate commands"
```

---

## Task 11: Update agent-builder skill

**Files:**
- Modify: `skills/openagent-agent-builder/src/openagent_agent_builder/render.py`

- [ ] **Step 1: Read `render.py` to understand current structure**

```
cat -n skills/openagent-agent-builder/src/openagent_agent_builder/render.py
```

- [ ] **Step 2: Update `_build_execution_policy` → emit `tool_executor`**

The function `_build_execution_policy()` (line 21) currently returns a dict like `{"type": "filesystem", "config": {...}}` assigned to `execution_policy`. Change it to return a `tool_executor` config instead:

```python
def _build_tool_executor(payload, tool_ids) -> dict[str, Any] | None:
    # ... same logic as before, but return:
    return {
        "type": "filesystem_aware",
        "config": {
            "allow_tools": tool_ids,
            "read_roots": payload.read_roots or [],
            "write_roots": payload.write_roots or [],
        }
    }
```

Assign this to `"tool_executor"` in the agent config instead of `"execution_policy"`.

- [ ] **Step 3: Remove `followup_resolver` and `response_repair_policy` keys**

Remove lines 62–63 (initial build) and lines 76–77 (overrides loop) that set these keys.

- [ ] **Step 4: Remove from the "pass-through" override list**

Lines 74–77 currently include `"execution_policy"`, `"followup_resolver"`, `"response_repair_policy"` in the list of keys that override the archetype. Remove all three. Add `"tool_executor"` to the override list instead.

- [ ] **Step 5: Run agent-builder tests**

```
uv run pytest tests/ -k "agent_builder" -v 2>&1 | head -40
```

- [ ] **Step 6: Commit**

```bash
rtk git add skills/openagent-agent-builder/
rtk git commit -m "feat(agent-builder): emit filesystem_aware tool_executor instead of execution_policy"
```

---

## Task 12: Update docs and fix tests broken by removal

**Files:**
- Modify: `docs/seams-and-extension-points.md`
- Fix any remaining test failures

- [ ] **Step 1: Run full test suite**

```
uv run pytest -q
```

List all failures.

- [ ] **Step 2: Fix remaining test failures**

Common expected failures:
- `test_composite_execution_policy.py` — test the new `CompositePolicy` class API
- `test_rule_based_followup.py` — followup resolver no longer a seam, update as needed
- `test_strict_json_response_repair.py` — response repair no longer a seam, update
- `test_runtime_orchestration.py` — no `execution_policy` in config
- Any test that creates an `AgentConfig` with `execution_policy`/`followup_resolver`/`response_repair_policy` keys

For each: remove the removed config keys or update to use the new `evaluate_policy`/pattern override API.

- [ ] **Step 3: Update `docs/seams-and-extension-points.md`**

- Section 2 ("Current seams"): remove `execution_policy`, `followup_resolver`, `response_repair_policy` from the lists
- Section 3 table: remove their rows
- Section 9 ("Anti-patterns"): update "follow-up fallback → followup_resolver" to say "override `resolve_followup()` on your `PatternPlugin` subclass"
- Update the seam count to 8

- [ ] **Step 4: Run full suite and verify coverage**

```
uv run coverage run -m pytest && uv run coverage report
```

Coverage must remain ≥ 90%.

- [ ] **Step 5: Commit**

```bash
rtk git add docs/seams-and-extension-points.md tests/
rtk git commit -m "docs+tests: update seam doc and fix tests for seam removal"
```

---

## Final Verification

- [ ] Run full test suite: `uv run pytest -q`
- [ ] Run coverage: `uv run coverage run -m pytest && uv run coverage report` (must be ≥ 90%)
- [ ] Verify seam count by reading `docs/seams-and-extension-points.md` section 2
- [ ] Verify `AgentConfig` no longer has `execution_policy`/`followup_resolver`/`response_repair_policy` fields
- [ ] Verify `openagents.__all__` no longer exports the three removed symbols
- [ ] Verify `_BoundTool` has no `_policy` attribute

# OpenAgents SDK Modernization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved `0.2.0` modernization spec for OpenAgents so the SDK gains typed config/runtime models, typed local dependency injection, explicit plugin loading, and visible runtime failure handling.

**Architecture:** Keep OpenAgents as a single-agent kernel, but replace weak dataclass/manual-parser surfaces with Pydantic-backed public contracts. Introduce one shared `RunContext[DepsT]` carrier across runtime, pattern, tool, and memory paths, then tighten loader/runtime behavior around explicit constructor rules, structured errors, and budget/error visibility. Follow the project rule to work directly on the current branch — do **not** create a worktree.

**Tech Stack:** Python 3.10+, `uv`, `pytest`, Pydantic v2, existing OpenAgents runtime/plugin interfaces

---

**Execution notes:**

- Use `@test-driven-development` discipline for every code task.
- Use `@verification-before-completion` before closing each chunk.
- Keep changes focused; do not widen the scope into graph orchestration or unrelated refactors.

## Chunk 1: Foundation Contracts

### Task 1: Add the new dependency and formalize the exception surface

**Files:**
- Modify: `pyproject.toml`
- Modify: `openagents/errors/exceptions.py`
- Modify: `openagents/interfaces/runtime.py`
- Modify: `openagents/interfaces/tool.py`
- Modify: `openagents/interfaces/__init__.py`
- Create: `tests/unit/test_errors.py`
- Modify: `tests/unit/test_interfaces_and_exports.py`

- [ ] **Step 1: Write the failing exception tests**

```python
from openagents.errors.exceptions import (
    AgentNotFoundError,
    ConfigLoadError,
    MaxStepsExceeded,
    OpenAgentsError,
    PluginCapabilityError,
)


def test_openagents_error_with_context_returns_typed_instance():
    err = MaxStepsExceeded("tool call limit").with_context(
        agent_id="assistant",
        session_id="demo",
        run_id="run-1",
    )
    assert isinstance(err, OpenAgentsError)
    assert err.agent_id == "assistant"
    assert err.session_id == "demo"
    assert err.run_id == "run-1"
```

- [ ] **Step 2: Run the new targeted tests to confirm they fail**

Run: `uv run pytest -q tests/unit/test_errors.py`

Expected: FAIL because the new exception classes and `with_context()` do not exist yet.

- [ ] **Step 3: Add `pydantic>=2.0` and expand the exception hierarchy**

Implementation targets:

- add `pydantic>=2.0` to `[project].dependencies` in `pyproject.toml`
- replace the four-line exception module with the structured hierarchy from the approved spec
- keep `PluginLoadError` and capability-related errors exported under their new typed parents
- update `RunResult.exception` typing in `openagents/interfaces/runtime.py`
- keep `ToolError` subclasses in `interfaces/tool.py`, but rebase them on the new shared error surface instead of an isolated tree

- [ ] **Step 4: Export the new public error types**

Update:

- `openagents/interfaces/__init__.py`
- any public package export surface that should re-export `StopReason` / runtime error types later

- [ ] **Step 5: Re-run the error and export tests**

Run: `uv run pytest -q tests/unit/test_errors.py tests/unit/test_interfaces_and_exports.py`

Expected: PASS

- [ ] **Step 6: Commit the foundation error/dependency change**

```bash
git add pyproject.toml openagents/errors/exceptions.py openagents/interfaces/runtime.py openagents/interfaces/tool.py openagents/interfaces/__init__.py tests/unit/test_errors.py tests/unit/test_interfaces_and_exports.py
git commit -m "feat(runtime): add typed sdk error hierarchy"
```

### Task 2: Replace config dataclasses and manual parsing with Pydantic models

**Files:**
- Modify: `openagents/config/schema.py`
- Modify: `openagents/config/loader.py`
- Modify: `openagents/config/__init__.py`
- Modify: `tests/unit/test_config_loader_validator.py`
- Create: `tests/unit/test_config_models.py`

- [ ] **Step 1: Write failing tests for `model_validate()`-based config parsing**

```python
from openagents.config.schema import AppConfig, MemoryRef


def test_app_config_model_validate_parses_minimal_payload():
    config = AppConfig.model_validate(
        {
            "version": "1.0",
            "agents": [
                {
                    "id": "assistant",
                    "name": "demo",
                    "memory": {"type": "window_buffer"},
                    "pattern": {"type": "react"},
                    "llm": {"provider": "mock"},
                    "tools": [],
                }
            ],
        }
    )
    assert config.agents[0].memory == MemoryRef(type="window_buffer")
```

- [ ] **Step 2: Run the config model tests to verify the current code fails**

Run: `uv run pytest -q tests/unit/test_config_models.py tests/unit/test_config_loader_validator.py`

Expected: FAIL because `AppConfig` is still a dataclass and `model_validate()` is unavailable.

- [ ] **Step 3: Convert config schema models to Pydantic v2**

Implementation targets:

- convert `PluginRef`, `MemoryRef`, `PatternRef`, `ToolRef`, `RuntimeRef`, `SessionRef`, `EventBusRef`, `SkillsRef`, `AgentDefinition`, `AppConfig`, `LLMOptions`, and runtime option models to `BaseModel`
- replace repetitive `from_dict()` logic with validators and typed defaults
- model `memory.on_error` as `Literal["continue", "fail"]`
- preserve `extra="allow"` only where the spec explicitly wants extension-friendly payloads

- [ ] **Step 4: Simplify `load_config_dict()` to wrap Pydantic validation**

Implementation targets:

- `openagents/config/loader.py` should call `AppConfig.model_validate(payload)`
- wrap JSON/file failures in `ConfigLoadError`
- wrap validation failures in `ConfigValidationError`
- remove the dependency on the old `validate_config(...)` path once all rules live in model validators

- [ ] **Step 5: Re-run config parsing tests**

Run: `uv run pytest -q tests/unit/test_config_models.py tests/unit/test_config_loader_validator.py`

Expected: PASS

- [ ] **Step 6: Commit the config migration**

```bash
git add openagents/config/schema.py openagents/config/loader.py openagents/config/__init__.py tests/unit/test_config_models.py tests/unit/test_config_loader_validator.py
git commit -m "feat(config): migrate schema parsing to pydantic"
```

## Chunk 2: Typed Runtime Surface

### Task 3: Introduce `RunContext[DepsT]` and migrate runtime/session contracts to Pydantic models

**Files:**
- Create: `openagents/interfaces/run_context.py`
- Modify: `openagents/interfaces/runtime.py`
- Modify: `openagents/interfaces/pattern.py`
- Modify: `openagents/interfaces/tool.py`
- Modify: `openagents/interfaces/session.py`
- Modify: `openagents/interfaces/__init__.py`
- Modify: `openagents/__init__.py`
- Create: `tests/unit/test_run_context_models.py`
- Modify: `tests/unit/test_interfaces_and_exports.py`

- [ ] **Step 1: Write failing tests for `RunContext`, `StopReason`, and immutable session models**

```python
from dataclasses import dataclass

from openagents.interfaces.run_context import RunContext
from openagents.interfaces.runtime import StopReason


@dataclass
class DemoDeps:
    token: str


def test_run_context_keeps_typed_deps():
    ctx = RunContext[DemoDeps](
        agent_id="assistant",
        session_id="demo",
        run_id="run-1",
        input_text="hello",
        deps=DemoDeps(token="abc"),
        event_bus=object(),
    )
    assert ctx.deps.token == "abc"
    assert StopReason.COMPLETED.value == "completed"
```

- [ ] **Step 2: Run the targeted runtime-contract tests to confirm failure**

Run: `uv run pytest -q tests/unit/test_run_context_models.py tests/unit/test_interfaces_and_exports.py`

Expected: FAIL because `RunContext` and `StopReason` are not public models yet.

- [ ] **Step 3: Add the new `RunContext` module and migrate runtime data models**

Implementation targets:

- add `openagents/interfaces/run_context.py`
- convert `RunBudget`, `RunArtifact`, `RunUsage`, `RunRequest`, `RunResult` to `BaseModel`
- introduce `StopReason` enum
- convert `SessionArtifact` and `SessionCheckpoint` to frozen Pydantic models where practical
- remove `deepcopy()`-based serialization helpers once model dump/copy covers the same needs

- [ ] **Step 4: Replace `ExecutionContext` with `RunContext` in the pattern/tool surface**

Implementation targets:

- migrate `PatternPlugin.context` to `RunContext[Any] | None`
- update `PatternPlugin.setup(...)` to build the new context object
- update `ToolExecutionRequest.context` typing from `Any` to `RunContext[Any] | None`
- update public exports in `openagents/interfaces/__init__.py` and `openagents/__init__.py`

- [ ] **Step 5: Re-run the contract/export tests**

Run: `uv run pytest -q tests/unit/test_run_context_models.py tests/unit/test_interfaces_and_exports.py`

Expected: PASS

- [ ] **Step 6: Commit the typed runtime-contract layer**

```bash
git add openagents/interfaces/run_context.py openagents/interfaces/runtime.py openagents/interfaces/pattern.py openagents/interfaces/tool.py openagents/interfaces/session.py openagents/interfaces/__init__.py openagents/__init__.py tests/unit/test_run_context_models.py tests/unit/test_interfaces_and_exports.py
git commit -m "feat(runtime): add typed run context contracts"
```

### Task 4: Thread `deps` through runtime entrypoints and default runtime orchestration

**Files:**
- Modify: `openagents/runtime/runtime.py`
- Modify: `openagents/runtime/sync.py`
- Modify: `openagents/plugins/builtin/runtime/default_runtime.py`
- Modify: `tests/unit/test_runtime_core.py`
- Modify: `tests/unit/test_runtime_orchestration.py`
- Modify: `tests/unit/test_runtime_sync_helpers.py`
- Modify: `tests/fixtures/custom_plugins.py`
- Modify: `tests/fixtures/runtime_plugins.py`
- Modify: `examples/production_coding_agent/app/plugins.py`

- [ ] **Step 1: Write failing runtime tests for `deps=` passthrough**

```python
from dataclasses import dataclass

from openagents.interfaces.run_context import RunContext


@dataclass
class DemoDeps:
    value: str


async def test_runtime_run_passes_deps_to_tool(runtime):
    result = await runtime.run(
        agent_id="assistant",
        session_id="demo",
        input_text="hello",
        deps=DemoDeps(value="abc"),
    )
    assert result == "abc"
```

- [ ] **Step 2: Run the runtime entrypoint tests to verify failure**

Run: `uv run pytest -q tests/unit/test_runtime_core.py tests/unit/test_runtime_orchestration.py tests/unit/test_runtime_sync_helpers.py`

Expected: FAIL because `Runtime.run(...)` and sync helpers do not yet accept `deps=`.

- [ ] **Step 3: Update runtime entrypoints and sync helpers**

Implementation targets:

- add optional `deps: Any = None` to:
  - `Runtime.run(...)`
  - `Runtime.run_detailed(...)` through `RunRequest`
  - sync helpers in `openagents/runtime/sync.py`
- extend `RunRequest` with a `deps` field if that is the cleanest way to carry dependencies into runtime-managed execution
- keep backward-compatible calling style for callers that do not pass deps

- [ ] **Step 4: Update `DefaultRuntime` to construct and preserve `RunContext`**

Implementation targets:

- `_setup_pattern(...)` should attach `request.deps` into the context object
- `_BoundTool.invoke(...)` and `ToolExecutorPlugin.execute(...)` should now carry typed run context rather than raw `Any`
- adapt test fixtures and the production example plugin file so their custom patterns/tools use `RunContext` instead of `ExecutionContext`

- [ ] **Step 5: Re-run the runtime/deps tests**

Run: `uv run pytest -q tests/unit/test_runtime_core.py tests/unit/test_runtime_orchestration.py tests/unit/test_runtime_sync_helpers.py`

Expected: PASS

- [ ] **Step 6: Commit the runtime/deps threading change**

```bash
git add openagents/runtime/runtime.py openagents/runtime/sync.py openagents/plugins/builtin/runtime/default_runtime.py tests/unit/test_runtime_core.py tests/unit/test_runtime_orchestration.py tests/unit/test_runtime_sync_helpers.py tests/fixtures/custom_plugins.py tests/fixtures/runtime_plugins.py examples/production_coding_agent/app/plugins.py
git commit -m "feat(runtime): thread deps through run context"
```

## Chunk 3: Loader Reliability and Failure Visibility

### Task 5: Make plugin construction explicit and surface registry conflicts

**Files:**
- Modify: `openagents/plugins/loader.py`
- Modify: `openagents/plugins/registry.py`
- Modify: `openagents/decorators.py`
- Modify: `tests/unit/test_plugin_loader.py`
- Modify: `tests/unit/test_plugins_loader.py`
- Modify: `tests/unit/test_decorators.py`

- [ ] **Step 1: Write failing tests for constructor keyword enforcement and warnings**

```python
import warnings

import pytest

from openagents.decorators import tool
from openagents.errors.exceptions import PluginLoadError


def test_register_tool_warns_on_duplicate_name():
    class FirstTool:
        pass

    class SecondTool:
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tool(name="dup_tool")(FirstTool)
        tool(name="dup_tool")(SecondTool)
    assert any("overridden" in str(item.message).lower() for item in caught)
```

- [ ] **Step 2: Run the loader/decorator tests to confirm failure**

Run: `uv run pytest -q tests/unit/test_plugin_loader.py tests/unit/test_plugins_loader.py tests/unit/test_decorators.py`

Expected: FAIL because duplicate registry writes are silent and constructor fallback still accepts multiple shapes.

- [ ] **Step 3: Replace `_instantiate()` fallback loops with one explicit constructor contract**

Implementation targets:

- define the constructor expectation around `config=...`
- preserve the original `TypeError` as the cause inside `PluginLoadError`
- apply the same rule in both:
  - `openagents/plugins/loader.py`
  - `openagents/plugins/builtin/runtime/default_runtime.py` runtime dependency loading path if it still duplicates instantiation logic

- [ ] **Step 4: Validate class capabilities before instantiation**

Implementation targets:

- add class-level capability checks before creating plugin instances
- keep post-instantiation checks only where instance state is genuinely required

- [ ] **Step 5: Emit warnings for registry collisions**

Implementation targets:

- warn on decorator-over-decorator name reuse
- warn when a decorator name collides with a builtin plugin name
- document and preserve builtin precedence for `0.2.0`

- [ ] **Step 6: Re-run loader/decorator tests**

Run: `uv run pytest -q tests/unit/test_plugin_loader.py tests/unit/test_plugins_loader.py tests/unit/test_decorators.py`

Expected: PASS

- [ ] **Step 7: Commit the loader reliability change**

```bash
git add openagents/plugins/loader.py openagents/plugins/registry.py openagents/decorators.py tests/unit/test_plugin_loader.py tests/unit/test_plugins_loader.py tests/unit/test_decorators.py
git commit -m "feat(plugins): enforce explicit loader construction"
```

### Task 6: Add visible logging, event isolation, and budget enforcement

**Files:**
- Modify: `openagents/plugins/builtin/events/async_event_bus.py`
- Modify: `openagents/plugins/builtin/runtime/default_runtime.py`
- Modify: `openagents/interfaces/events.py`
- Create: `tests/unit/test_runtime_failures_and_budgets.py`
- Modify: `tests/unit/test_builtin_plugins_runtime.py`

- [ ] **Step 1: Write failing tests for suppressed-error logging and budget enforcement**

```python
import logging

import pytest


@pytest.mark.asyncio
async def test_event_bus_keeps_emitting_after_handler_failure(caplog):
    caplog.set_level(logging.ERROR, logger="openagents")
    # first handler raises, second handler records success
    ...
    assert "handler failed" in caplog.text.lower()
    assert success_marker["called"] is True
```

- [ ] **Step 2: Run the runtime failure tests to confirm failure**

Run: `uv run pytest -q tests/unit/test_runtime_failures_and_budgets.py tests/unit/test_builtin_plugins_runtime.py`

Expected: FAIL because event handler errors currently abort the loop and memory failures are not logged.

- [ ] **Step 3: Introduce `openagents` logger usage in runtime suppression paths**

Implementation targets:

- log memory inject/writeback failures when `on_error == "continue"`
- include `agent_id`, `session_id`, and `run_id` in structured log extras
- keep matching runtime event emission

- [ ] **Step 4: Isolate event handler failures in `AsyncEventBus.emit(...)`**

Implementation targets:

- history append still happens first
- each handler runs independently
- failed handlers are logged
- later handlers still run

- [ ] **Step 5: Enforce budgets where runtime can actually observe execution**

Implementation targets:

- enforce `max_tool_calls` in the shared tool invocation path
- enforce `max_duration_ms` around runtime-controlled boundaries
- map budget failures to typed runtime exceptions / `StopReason`
- document in code comments that arbitrary custom pattern loops cannot be preempted unless they yield control

- [ ] **Step 6: Re-run the failure/budget tests**

Run: `uv run pytest -q tests/unit/test_runtime_failures_and_budgets.py tests/unit/test_builtin_plugins_runtime.py`

Expected: PASS

- [ ] **Step 7: Commit the failure-visibility/budget change**

```bash
git add openagents/plugins/builtin/events/async_event_bus.py openagents/plugins/builtin/runtime/default_runtime.py openagents/interfaces/events.py tests/unit/test_runtime_failures_and_budgets.py tests/unit/test_builtin_plugins_runtime.py
git commit -m "feat(runtime): log suppressed failures and enforce budgets"
```

## Chunk 4: Public Surface, Docs, and Final Verification

### Task 7: Update docs, examples, public exports, and release metadata for `0.2.0`

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `README_CN.md`
- Modify: `docs/api-reference.md`
- Modify: `docs/configuration.md`
- Modify: `docs/plugin-development.md`
- Modify: `docs/README.md`
- Modify: `examples/quickstart/run_demo.py`
- Modify: `examples/production_coding_agent/app/plugins.py`
- Modify: `tests/unit/test_interfaces_and_exports.py`

- [ ] **Step 1: Write failing tests or assertions for the new public API surface**

Targets to cover:

- `RunContext` is importable from the intended public module
- docs/examples no longer teach `context: Any` as the primary tool contract
- package version in `pyproject.toml` is `0.2.0`

- [ ] **Step 2: Run the public-surface checks to verify failure**

Run: `uv run pytest -q tests/unit/test_interfaces_and_exports.py`

Expected: FAIL until docs/exports/version are updated.

- [ ] **Step 3: Update docs and examples to match the new runtime model**

Implementation targets:

- show `RunContext[DepsT]` in plugin-development examples
- explain `deps` and `StopReason` in API/config docs
- keep the narrative explicit that `RunContext` is local-only and not passed to the LLM
- update the production example plugin file to the new context type
- only update quickstart if a new `deps=` example materially improves the public surface; otherwise leave quickstart simple

- [ ] **Step 4: Bump package version to `0.2.0`**

Implementation targets:

- update `pyproject.toml`
- update any versioned docs snippets if they exist

- [ ] **Step 5: Run the full repository verification**

Run: `uv run pytest -q`

Expected: PASS

- [ ] **Step 6: Run import-level smoke checks for the public API**

Run:

```bash
uv run python -c "from openagents import Runtime, RunContext, load_config_dict; from openagents.interfaces.runtime import StopReason; print(Runtime, RunContext, StopReason)"
```

Expected: prints imported symbols without raising.

- [ ] **Step 7: Review the final diff and commit**

```bash
git status --short
git diff --stat
git add pyproject.toml README.md README_EN.md README_CN.md docs/api-reference.md docs/configuration.md docs/plugin-development.md docs/README.md examples/quickstart/run_demo.py examples/production_coding_agent/app/plugins.py tests/unit/test_interfaces_and_exports.py
git commit -m "feat: ship openagents sdk modernization v0.2.0"
```

## Final handoff checklist

- [ ] Config models use Pydantic v2 and no longer rely on manual `from_dict()` parsing
- [ ] `RunContext[DepsT]` is the shared local runtime context for tools/patterns
- [ ] plugin constructors require `config=` and fail loudly on bad signatures
- [ ] event-bus handler failures are isolated and logged
- [ ] memory suppression paths log warnings/errors when continuing
- [ ] budget enforcement is visible and tested
- [ ] docs/examples/public exports match the new API surface
- [ ] `uv run pytest -q` passes


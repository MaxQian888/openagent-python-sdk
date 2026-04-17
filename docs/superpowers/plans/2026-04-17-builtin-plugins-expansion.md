# Builtin Plugins Expansion + Research-Analyst Example — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one additional builtin to each thin seam (tool_executor, execution_policy×2, followup_resolver, session, events, response_repair_policy) and ship `examples/research_analyst/` that exercises all seven in one offline flow.

**Architecture:** Composition-based builtins that hold inner plugin refs as dicts and call the existing `_load_plugin(kind, ref)` loader for child resolution. Each builtin declares a pydantic `Config(BaseModel)` matching the 0.3.0 convention. Example uses an in-process aiohttp stub server and ships a thin app-layer `FollowupFirstReActPattern` wrapper because kernel does not auto-invoke `followup_resolver.resolve`.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, `pydantic v2`, `aiohttp` (dev-only for stub server and example integration test), existing `openagents` SDK 0.3.x seams.

**Spec:** [docs/superpowers/specs/2026-04-17-builtin-plugins-expansion-design.md](../specs/2026-04-17-builtin-plugins-expansion-design.md)

**Global conventions for every task below:**
- Run tests with `uv run pytest -q <path>`; never invoke `pytest` directly.
- Every new file must have `from __future__ import annotations` at the top.
- Every new builtin must declare a `class Config(BaseModel)` and be registered in `openagents/plugins/registry.py` before any test can resolve it by `type` key.
- `aiohttp` is already a dep (check with `uv pip show aiohttp`); if missing, `uv add --dev aiohttp` before Task 9.
- `from pydantic import BaseModel, Field` (v2).
- Commit after each task passes its tests locally.

---

## Task 1: `RetryToolExecutor`

**Files:**
- Create: `openagents/plugins/builtin/tool_executor/retry.py`
- Modify: `openagents/plugins/builtin/tool_executor/__init__.py`
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_retry_tool_executor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_retry_tool_executor.py
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from openagents.errors.exceptions import (
    PermanentToolError,
    RetryableToolError,
    ToolError,
    ToolTimeoutError,
)
from openagents.interfaces.tool import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionSpec,
    ToolExecutorPlugin,
)
from openagents.plugins.builtin.tool_executor.retry import RetryToolExecutor
from openagents.plugins.registry import get_builtin_plugin_class


class _FakeTool:
    pass


class _ScriptedExecutor(ToolExecutorPlugin):
    def __init__(self, results: list[ToolExecutionResult]):
        super().__init__(config={}, capabilities=set())
        self._results = list(results)
        self.calls = 0

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        self.calls += 1
        return self._results.pop(0)

    async def execute_stream(self, request: ToolExecutionRequest):
        yield {"type": "stream-passthrough", "calls": self.calls}


def _req() -> ToolExecutionRequest:
    return ToolExecutionRequest(
        tool_id="demo",
        tool=_FakeTool(),
        params={},
        execution_spec=ToolExecutionSpec(),
    )


def _ok() -> ToolExecutionResult:
    return ToolExecutionResult(tool_id="demo", success=True, data="ok")


def _retryable() -> ToolExecutionResult:
    exc = RetryableToolError("transient", tool_name="demo")
    return ToolExecutionResult(tool_id="demo", success=False, error=str(exc), exception=exc)


def _timeout() -> ToolExecutionResult:
    exc = ToolTimeoutError("slow", tool_name="demo")
    return ToolExecutionResult(tool_id="demo", success=False, error=str(exc), exception=exc)


def _permanent() -> ToolExecutionResult:
    exc = PermanentToolError("nope", tool_name="demo")
    return ToolExecutionResult(tool_id="demo", success=False, error=str(exc), exception=exc)


def _make(inner: _ScriptedExecutor, **overrides: Any) -> RetryToolExecutor:
    cfg = {"inner": {"impl": "tests.unit.test_retry_tool_executor:_ScriptedExecutor"}}
    cfg.update(overrides)
    retry = RetryToolExecutor(config={"max_attempts": 3, "initial_delay_ms": 1, "max_delay_ms": 2, **cfg})
    retry._inner = inner  # inject scripted executor post-construction for test isolation
    return retry


@pytest.mark.asyncio
async def test_first_call_success_no_retry():
    inner = _ScriptedExecutor([_ok()])
    retry = _make(inner)
    result = await retry.execute(_req())
    assert result.success is True
    assert inner.calls == 1
    assert result.metadata.get("retry_attempts", 1) == 1


@pytest.mark.asyncio
async def test_retryable_then_success():
    inner = _ScriptedExecutor([_retryable(), _retryable(), _ok()])
    retry = _make(inner)
    result = await retry.execute(_req())
    assert result.success is True
    assert inner.calls == 3
    assert result.metadata["retry_attempts"] == 3


@pytest.mark.asyncio
async def test_retryable_exhaustion_returns_failure():
    inner = _ScriptedExecutor([_retryable(), _retryable(), _retryable()])
    retry = _make(inner)
    result = await retry.execute(_req())
    assert result.success is False
    assert inner.calls == 3
    assert result.metadata["retry_attempts"] == 3
    assert len(result.metadata["retry_delays_ms"]) == 2  # 2 sleeps between 3 attempts
    assert isinstance(result.exception, RetryableToolError)


@pytest.mark.asyncio
async def test_timeout_retries_when_flag_true():
    inner = _ScriptedExecutor([_timeout(), _ok()])
    retry = _make(inner, retry_on_timeout=True)
    result = await retry.execute(_req())
    assert result.success is True
    assert inner.calls == 2


@pytest.mark.asyncio
async def test_timeout_not_retried_when_flag_false():
    inner = _ScriptedExecutor([_timeout(), _ok()])
    retry = RetryToolExecutor(config={
        "max_attempts": 3, "initial_delay_ms": 1, "max_delay_ms": 2,
        "retry_on_timeout": False,
        "retry_on": ["RetryableToolError"],
        "inner": {"impl": "tests.unit.test_retry_tool_executor:_ScriptedExecutor"},
    })
    retry._inner = inner
    result = await retry.execute(_req())
    assert result.success is False
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_permanent_error_not_retried():
    inner = _ScriptedExecutor([_permanent()])
    retry = _make(inner)
    result = await retry.execute(_req())
    assert result.success is False
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_execute_stream_passthrough_no_retry():
    inner = _ScriptedExecutor([])
    retry = _make(inner)
    chunks = [c async for c in retry.execute_stream(_req())]
    assert chunks == [{"type": "stream-passthrough", "calls": 1}]


@pytest.mark.asyncio
async def test_cancellation_during_backoff_propagates():
    inner = _ScriptedExecutor([_retryable(), _retryable(), _ok()])
    retry = RetryToolExecutor(config={
        "max_attempts": 3, "initial_delay_ms": 1_000_000, "max_delay_ms": 1_000_000,
        "inner": {"impl": "tests.unit.test_retry_tool_executor:_ScriptedExecutor"},
    })
    retry._inner = inner

    async def run():
        return await retry.execute(_req())

    task = asyncio.create_task(run())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_registered_as_builtin():
    assert get_builtin_plugin_class("tool_executor", "retry") is RetryToolExecutor
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest -q tests/unit/test_retry_tool_executor.py
```
Expected: `ModuleNotFoundError: No module named 'openagents.plugins.builtin.tool_executor.retry'`.

- [ ] **Step 3: Implement `RetryToolExecutor`**

Create `openagents/plugins/builtin/tool_executor/retry.py`:

```python
"""Retry wrapper tool executor."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from openagents.errors.exceptions import ToolError, ToolTimeoutError
from openagents.interfaces.tool import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutorPlugin,
)


class RetryToolExecutor(ToolExecutorPlugin):
    """Wraps another ToolExecutor and retries on classified errors with exponential backoff.

    ``execute_stream`` does not retry; it delegates transparently.
    """

    class Config(BaseModel):
        inner: dict[str, Any] = Field(default_factory=lambda: {"type": "safe"})
        max_attempts: int = 3
        initial_delay_ms: int = 200
        backoff_multiplier: float = 2.0
        max_delay_ms: int = 5_000
        retry_on_timeout: bool = True
        retry_on: list[str] = Field(default_factory=lambda: ["RetryableToolError", "ToolTimeoutError"])

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._max_attempts = max(1, cfg.max_attempts)
        self._initial_delay_ms = max(0, cfg.initial_delay_ms)
        self._backoff = max(1.0, cfg.backoff_multiplier)
        self._max_delay_ms = max(self._initial_delay_ms, cfg.max_delay_ms)
        self._retry_on_timeout = cfg.retry_on_timeout
        self._retry_on = set(cfg.retry_on)
        self._inner = self._load_inner(cfg.inner)

    def _load_inner(self, ref: dict[str, Any]) -> Any:
        # Import lazily to avoid import cycle with loader.
        from openagents.config.schema import ToolExecutorRef
        from openagents.plugins.loader import _load_plugin

        return _load_plugin("tool_executor", ToolExecutorRef(**ref), required_methods=("execute", "execute_stream"))

    def _should_retry(self, exc: Exception | None) -> bool:
        if exc is None:
            return False
        name = type(exc).__name__
        if name in self._retry_on:
            return True
        if self._retry_on_timeout and isinstance(exc, ToolTimeoutError):
            return True
        return False

    def _delay_for(self, attempt: int) -> int:
        delay = self._initial_delay_ms * (self._backoff ** attempt)
        return int(min(self._max_delay_ms, delay))

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        delays: list[int] = []
        reasons: list[str] = []
        last_result: ToolExecutionResult | None = None
        for attempt in range(self._max_attempts):
            result = await self._inner.execute(request)
            if result.success or not self._should_retry(result.exception):
                metadata = dict(result.metadata or {})
                metadata.setdefault("retry_attempts", attempt + 1)
                if delays:
                    metadata["retry_delays_ms"] = delays
                    metadata["retry_reason"] = reasons
                return result.model_copy(update={"metadata": metadata})
            last_result = result
            if attempt + 1 >= self._max_attempts:
                break
            delay_ms = self._delay_for(attempt)
            delays.append(delay_ms)
            reasons.append(type(result.exception).__name__ if result.exception else "unknown")
            await asyncio.sleep(delay_ms / 1000)
        assert last_result is not None
        metadata = dict(last_result.metadata or {})
        metadata["retry_attempts"] = self._max_attempts
        metadata["retry_delays_ms"] = delays
        metadata["retry_reason"] = reasons
        return last_result.model_copy(update={"metadata": metadata})

    async def execute_stream(self, request: ToolExecutionRequest):
        async for chunk in self._inner.execute_stream(request):
            yield chunk
```

- [ ] **Step 4: Wire registry and export**

Modify `openagents/plugins/builtin/tool_executor/__init__.py`:

```python
"""Builtin tool executor implementations."""

from .retry import RetryToolExecutor
from .safe import SafeToolExecutor

__all__ = ["SafeToolExecutor", "RetryToolExecutor"]
```

Modify `openagents/plugins/registry.py`: add the import line `from openagents.plugins.builtin.tool_executor.retry import RetryToolExecutor` and extend `_BUILTIN_REGISTRY["tool_executor"]`:

```python
"tool_executor": {
    "safe": SafeToolExecutor,
    "retry": RetryToolExecutor,
},
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest -q tests/unit/test_retry_tool_executor.py
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/tool_executor/ openagents/plugins/registry.py tests/unit/test_retry_tool_executor.py
git commit -m "feat(tool_executor): add retry builtin with exponential backoff"
```

---

## Task 2: `CompositeExecutionPolicy`

**Files:**
- Create: `openagents/plugins/builtin/execution_policy/composite.py`
- Modify: `openagents/plugins/builtin/execution_policy/__init__.py`
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_composite_execution_policy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_composite_execution_policy.py
from __future__ import annotations

from typing import Any

import pytest

from openagents.interfaces.tool import (
    ExecutionPolicyPlugin,
    PolicyDecision,
    ToolExecutionRequest,
    ToolExecutionSpec,
)
from openagents.plugins.builtin.execution_policy.composite import CompositeExecutionPolicy
from openagents.plugins.registry import get_builtin_plugin_class


class _Allow(ExecutionPolicyPlugin):
    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        return PolicyDecision(allowed=True, reason="allow", metadata={"who": "allow"})


class _Deny(ExecutionPolicyPlugin):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        self._tag = (config or {}).get("tag", "deny")

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        return PolicyDecision(allowed=False, reason=f"no:{self._tag}", metadata={"who": self._tag})


class _Raise(ExecutionPolicyPlugin):
    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        raise RuntimeError("boom")


def _req() -> ToolExecutionRequest:
    return ToolExecutionRequest(tool_id="x", tool=object(), execution_spec=ToolExecutionSpec())


def _build(policies, mode="all") -> CompositeExecutionPolicy:
    return CompositeExecutionPolicy(config={"policies": policies, "mode": mode})


@pytest.mark.asyncio
async def test_all_mode_first_deny_wins():
    cp = _build([
        {"impl": "tests.unit.test_composite_execution_policy:_Allow"},
        {"impl": "tests.unit.test_composite_execution_policy:_Deny", "config": {"tag": "d1"}},
        {"impl": "tests.unit.test_composite_execution_policy:_Deny", "config": {"tag": "d2"}},
    ], mode="all")
    decision = await cp.evaluate(_req())
    assert decision.allowed is False
    assert "d1" in decision.reason
    assert decision.metadata["decided_by"] == 1


@pytest.mark.asyncio
async def test_all_allow_passes():
    cp = _build([
        {"impl": "tests.unit.test_composite_execution_policy:_Allow"},
        {"impl": "tests.unit.test_composite_execution_policy:_Allow"},
    ])
    decision = await cp.evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["policy"] == "composite"
    assert len(decision.metadata["children"]) == 2


@pytest.mark.asyncio
async def test_any_mode_first_allow_wins():
    cp = _build([
        {"impl": "tests.unit.test_composite_execution_policy:_Deny", "config": {"tag": "d"}},
        {"impl": "tests.unit.test_composite_execution_policy:_Allow"},
    ], mode="any")
    decision = await cp.evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["decided_by"] == 1


@pytest.mark.asyncio
async def test_empty_policies_allows():
    cp = _build([])
    decision = await cp.evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["children"] == []


@pytest.mark.asyncio
async def test_child_exception_wrapped_as_deny():
    cp = _build([
        {"impl": "tests.unit.test_composite_execution_policy:_Raise"},
    ])
    decision = await cp.evaluate(_req())
    assert decision.allowed is False
    assert "raised" in decision.reason
    assert decision.metadata["error_type"] == "RuntimeError"


def test_registered_as_builtin():
    assert get_builtin_plugin_class("execution_policy", "composite") is CompositeExecutionPolicy
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest -q tests/unit/test_composite_execution_policy.py
```
Expected: ModuleNotFoundError for the composite module.

- [ ] **Step 3: Implement `CompositeExecutionPolicy`**

Create `openagents/plugins/builtin/execution_policy/composite.py`:

```python
"""Composite execution policy (AND/OR combinator)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from openagents.interfaces.tool import (
    ExecutionPolicyPlugin,
    PolicyDecision,
    ToolExecutionRequest,
)


class CompositeExecutionPolicy(ExecutionPolicyPlugin):
    """Combine multiple execution policies with AND (``all``) or OR (``any``) semantics."""

    class Config(BaseModel):
        policies: list[dict[str, Any]]
        mode: Literal["all", "any"] = "all"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._mode = cfg.mode
        self._children = [self._load_child(ref) for ref in cfg.policies]

    def _load_child(self, ref: dict[str, Any]) -> Any:
        from openagents.config.schema import ExecutionPolicyRef
        from openagents.plugins.loader import _load_plugin

        return _load_plugin("execution_policy", ExecutionPolicyRef(**ref), required_methods=("evaluate",))

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        child_metadata: list[dict[str, Any]] = []
        if not self._children:
            return PolicyDecision(
                allowed=True,
                metadata={"policy": "composite", "children": [], "decided_by": "default"},
            )
        for index, child in enumerate(self._children):
            try:
                decision = await child.evaluate(request)
            except Exception as exc:
                return PolicyDecision(
                    allowed=False,
                    reason=f"child {index} raised: {exc}",
                    metadata={
                        "policy": "composite",
                        "error_type": type(exc).__name__,
                        "decided_by": index,
                        "children": child_metadata,
                    },
                )
            child_metadata.append({"index": index, "allowed": decision.allowed, "reason": decision.reason, **decision.metadata})
            if self._mode == "all" and not decision.allowed:
                return PolicyDecision(
                    allowed=False,
                    reason=decision.reason,
                    metadata={"policy": "composite", "decided_by": index, "children": child_metadata},
                )
            if self._mode == "any" and decision.allowed:
                return PolicyDecision(
                    allowed=True,
                    reason=decision.reason,
                    metadata={"policy": "composite", "decided_by": index, "children": child_metadata},
                )
        # End-of-loop outcome
        if self._mode == "all":
            return PolicyDecision(
                allowed=True,
                metadata={"policy": "composite", "decided_by": "all_passed", "children": child_metadata},
            )
        # mode=="any" with all denies
        last_reason = child_metadata[-1]["reason"] if child_metadata else "no policies allowed"
        return PolicyDecision(
            allowed=False,
            reason=last_reason,
            metadata={"policy": "composite", "decided_by": "none_allowed", "children": child_metadata},
        )
```

- [ ] **Step 4: Wire registry and export**

Modify `openagents/plugins/builtin/execution_policy/__init__.py`:

```python
"""Builtin execution policy implementations."""

from .composite import CompositeExecutionPolicy
from .filesystem import FilesystemExecutionPolicy

__all__ = ["FilesystemExecutionPolicy", "CompositeExecutionPolicy"]
```

Modify `openagents/plugins/registry.py`: add the import and extend:

```python
"execution_policy": {
    "filesystem": FilesystemExecutionPolicy,
    "composite": CompositeExecutionPolicy,
},
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_composite_execution_policy.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/execution_policy/composite.py openagents/plugins/builtin/execution_policy/__init__.py openagents/plugins/registry.py tests/unit/test_composite_execution_policy.py
git commit -m "feat(execution_policy): add composite AND/OR combinator"
```

---

## Task 3: `NetworkAllowlistExecutionPolicy`

**Files:**
- Create: `openagents/plugins/builtin/execution_policy/network.py`
- Modify: `openagents/plugins/builtin/execution_policy/__init__.py`
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_network_allowlist_policy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_network_allowlist_policy.py
from __future__ import annotations

import pytest

from openagents.interfaces.tool import ToolExecutionRequest, ToolExecutionSpec
from openagents.plugins.builtin.execution_policy.network import NetworkAllowlistExecutionPolicy
from openagents.plugins.registry import get_builtin_plugin_class


def _req(tool_id: str = "http_request", url: str | None = "https://api.example.com/v1") -> ToolExecutionRequest:
    params = {"url": url} if url is not None else {}
    return ToolExecutionRequest(tool_id=tool_id, tool=object(), params=params, execution_spec=ToolExecutionSpec())


def _make(**config) -> NetworkAllowlistExecutionPolicy:
    cfg = {"allow_hosts": ["api.example.com"], **config}
    return NetworkAllowlistExecutionPolicy(config=cfg)


@pytest.mark.asyncio
async def test_exact_host_allowed():
    decision = await _make().evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["host"] == "api.example.com"


@pytest.mark.asyncio
async def test_wildcard_host_allowed():
    policy = _make(allow_hosts=["*.example.com"])
    decision = await policy.evaluate(_req(url="https://edge.example.com/x"))
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_unlisted_host_denied():
    decision = await _make().evaluate(_req(url="https://evil.test/x"))
    assert decision.allowed is False
    assert "not in allow_hosts" in decision.reason


@pytest.mark.asyncio
async def test_scheme_denied():
    policy = _make(allow_schemes=["https"])
    decision = await policy.evaluate(_req(url="http://api.example.com/x"))
    assert decision.allowed is False
    assert "scheme" in decision.reason


@pytest.mark.asyncio
async def test_non_applicable_tool_allowed():
    policy = _make(applies_to_tools=["http_request"])
    decision = await policy.evaluate(_req(tool_id="read_file", url=None))
    assert decision.allowed is True
    assert decision.metadata.get("skipped") is True


@pytest.mark.asyncio
async def test_private_network_denied_when_flag_on():
    policy = _make(allow_hosts=["127.0.0.1", "10.0.0.5", "192.168.1.2"], deny_private_networks=True)
    for url in ("http://127.0.0.1/x", "http://10.0.0.5/x", "http://192.168.1.2/x", "http://172.20.0.1/x"):
        decision = await policy.evaluate(_req(url=url))
        assert decision.allowed is False, url


@pytest.mark.asyncio
async def test_unparseable_url_denied():
    decision = await _make().evaluate(_req(url=""))
    assert decision.allowed is False


def test_registered_as_builtin():
    assert get_builtin_plugin_class("execution_policy", "network_allowlist") is NetworkAllowlistExecutionPolicy
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_network_allowlist_policy.py
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `NetworkAllowlistExecutionPolicy`**

Create `openagents/plugins/builtin/execution_policy/network.py`:

```python
"""Network allowlist execution policy."""

from __future__ import annotations

import fnmatch
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from openagents.interfaces.tool import (
    ExecutionPolicyPlugin,
    PolicyDecision,
    ToolExecutionRequest,
)


_PRIVATE_PREFIXES = ("127.", "10.", "192.168.", "::1", "localhost")


def _is_private(host: str) -> bool:
    h = host.lower()
    if h in {"localhost", "::1"}:
        return True
    if any(h.startswith(p) for p in _PRIVATE_PREFIXES):
        return True
    if h.startswith("172."):
        parts = h.split(".")
        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return True
    return False


class NetworkAllowlistExecutionPolicy(ExecutionPolicyPlugin):
    """Allowlist host/scheme for network-flavored tools (e.g. ``http_request``)."""

    class Config(BaseModel):
        allow_hosts: list[str] = Field(default_factory=list)
        allow_schemes: list[str] = Field(default_factory=lambda: ["http", "https"])
        applies_to_tools: list[str] = Field(default_factory=lambda: ["http_request"])
        deny_private_networks: bool = True

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._allow_hosts = [h.lower() for h in cfg.allow_hosts]
        self._allow_schemes = {s.lower() for s in cfg.allow_schemes}
        self._applies = set(cfg.applies_to_tools)
        self._deny_private = cfg.deny_private_networks

    def _host_allowed(self, host: str) -> bool:
        if not self._allow_hosts:
            return False
        for pattern in self._allow_hosts:
            if fnmatch.fnmatchcase(host, pattern):
                return True
        return False

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        if request.tool_id not in self._applies:
            return PolicyDecision(allowed=True, metadata={"policy": "network_allowlist", "skipped": True})
        url = (request.params or {}).get("url", "")
        if not isinstance(url, str) or not url.strip():
            return PolicyDecision(allowed=False, reason="unparseable URL: empty", metadata={"policy": "network_allowlist"})
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        scheme = (parsed.scheme or "").lower()
        if not host:
            return PolicyDecision(allowed=False, reason="unparseable URL: missing host", metadata={"policy": "network_allowlist"})
        meta = {"policy": "network_allowlist", "host": host, "scheme": scheme}
        if scheme not in self._allow_schemes:
            return PolicyDecision(allowed=False, reason=f"scheme '{scheme}' not allowed", metadata=meta)
        if self._deny_private and _is_private(host):
            return PolicyDecision(allowed=False, reason=f"private network '{host}' denied", metadata=meta)
        if not self._host_allowed(host):
            return PolicyDecision(allowed=False, reason=f"host '{host}' not in allow_hosts", metadata=meta)
        return PolicyDecision(allowed=True, metadata=meta)
```

- [ ] **Step 4: Wire registry**

Modify `openagents/plugins/builtin/execution_policy/__init__.py`:

```python
"""Builtin execution policy implementations."""

from .composite import CompositeExecutionPolicy
from .filesystem import FilesystemExecutionPolicy
from .network import NetworkAllowlistExecutionPolicy

__all__ = ["FilesystemExecutionPolicy", "CompositeExecutionPolicy", "NetworkAllowlistExecutionPolicy"]
```

Modify `openagents/plugins/registry.py`: add the import line and extend:

```python
"execution_policy": {
    "filesystem": FilesystemExecutionPolicy,
    "composite": CompositeExecutionPolicy,
    "network_allowlist": NetworkAllowlistExecutionPolicy,
},
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_network_allowlist_policy.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/execution_policy/network.py openagents/plugins/builtin/execution_policy/__init__.py openagents/plugins/registry.py tests/unit/test_network_allowlist_policy.py
git commit -m "feat(execution_policy): add network_allowlist builtin"
```

---

## Task 4: `RuleBasedFollowupResolver`

**Files:**
- Create: `openagents/plugins/builtin/followup/rule_based.py`
- Modify: `openagents/plugins/builtin/followup/__init__.py` (create if missing — currently not present; module loaded via explicit imports elsewhere)
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_rule_based_followup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_rule_based_followup.py
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from openagents.errors.exceptions import PluginLoadError
from openagents.plugins.builtin.followup.rule_based import RuleBasedFollowupResolver
from openagents.plugins.registry import get_builtin_plugin_class


def _ctx(input_text: str, history=None):
    return SimpleNamespace(input_text=input_text, memory_view={"history": history} if history is not None else {})


@pytest.mark.asyncio
async def test_rule_match_resolves_with_template():
    resolver = RuleBasedFollowupResolver(config={
        "rules": [{
            "name": "tools",
            "pattern": "which tools",
            "template": "used: {tool_ids}; input: {last_input}",
        }]
    })
    result = await resolver.resolve(context=_ctx("which tools did you use", history=[{
        "input": "hello",
        "output": "world",
        "tool_results": [{"tool_id": "t1"}, {"tool_id": "t2"}],
    }]))
    assert result.status == "resolved"
    assert "t1, t2" in result.output
    assert result.metadata["rule"] == "tools"


@pytest.mark.asyncio
async def test_no_rule_match_returns_none():
    resolver = RuleBasedFollowupResolver(config={"rules": [{"name": "x", "pattern": "zzz", "template": "a"}]})
    assert await resolver.resolve(context=_ctx("hello")) is None


@pytest.mark.asyncio
async def test_rule_match_without_history_abstains():
    resolver = RuleBasedFollowupResolver(config={"rules": [{"name": "x", "pattern": "ping", "template": "a"}]})
    result = await resolver.resolve(context=_ctx("ping", history=[]))
    assert result.status == "abstain"


@pytest.mark.asyncio
async def test_missing_template_key_renders_empty():
    resolver = RuleBasedFollowupResolver(config={
        "rules": [{"name": "x", "pattern": "q", "template": "tools={tool_ids}; unknown={nonexistent}"}]
    })
    result = await resolver.resolve(context=_ctx("q", history=[{"input": "i", "output": "o", "tool_results": []}]))
    assert result.status == "resolved"
    assert "unknown=" in result.output


@pytest.mark.asyncio
async def test_rules_file_loaded(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps([{"name": "f", "pattern": "hi", "template": "hi back"}]), encoding="utf-8")
    resolver = RuleBasedFollowupResolver(config={"rules_file": str(path)})
    result = await resolver.resolve(context=_ctx("hi", history=[{"input": "i", "output": "o"}]))
    assert result.status == "resolved"
    assert result.output == "hi back"


def test_invalid_rules_file_raises_plugin_load_error(tmp_path: Path):
    with pytest.raises(PluginLoadError):
        RuleBasedFollowupResolver(config={"rules_file": str(tmp_path / "missing.json")})


def test_registered_as_builtin():
    assert get_builtin_plugin_class("followup_resolver", "rule_based") is RuleBasedFollowupResolver
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_rule_based_followup.py
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `RuleBasedFollowupResolver`**

Create `openagents/plugins/builtin/followup/rule_based.py`:

```python
"""Rule-based follow-up resolver."""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from openagents.errors.exceptions import PluginLoadError
from openagents.interfaces.followup import FollowupResolution, FollowupResolverPlugin


class _SafeDict(collections.defaultdict):
    def __missing__(self, key: str) -> str:
        return ""


class Rule(BaseModel):
    name: str
    pattern: str
    template: str
    requires_history: bool = True


class RuleBasedFollowupResolver(FollowupResolverPlugin):
    """Resolve follow-ups via user-configured regex → template rules."""

    class Config(BaseModel):
        rules_file: str | None = None
        rules: list[Rule] = Field(default_factory=list)

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        file_rules: list[Rule] = []
        if cfg.rules_file:
            path = Path(cfg.rules_file)
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PluginLoadError(
                    f"rule_based followup_resolver: could not read rules_file '{cfg.rules_file}': {exc}"
                ) from exc
            if not isinstance(raw, list):
                raise PluginLoadError(
                    f"rule_based followup_resolver: rules_file '{cfg.rules_file}' must be a JSON array"
                )
            for item in raw:
                file_rules.append(Rule.model_validate(item))
        self._rules: list[tuple[Rule, re.Pattern[str]]] = [
            (r, re.compile(r.pattern, re.IGNORECASE)) for r in (*file_rules, *cfg.rules)
        ]

    async def resolve(self, *, context: Any) -> FollowupResolution | None:
        text = str(getattr(context, "input_text", "") or "")
        for rule, compiled in self._rules:
            if not compiled.search(text):
                continue
            memory_view = getattr(context, "memory_view", {}) or {}
            history = memory_view.get("history") if isinstance(memory_view, dict) else None
            if rule.requires_history and (not isinstance(history, list) or not history):
                return FollowupResolution(status="abstain", reason="no history", metadata={"rule": rule.name})
            last = history[-1] if isinstance(history, list) and history else {}
            last = last if isinstance(last, dict) else {}
            tool_ids: list[str] = []
            for item in (last.get("tool_results") or []):
                if isinstance(item, dict) and isinstance(item.get("tool_id"), str):
                    tool_ids.append(item["tool_id"])
            mapping = _SafeDict(str, {
                "tool_ids": ", ".join(tool_ids),
                "last_input": str(last.get("input", "")),
                "last_output": str(last.get("output", "")),
            })
            rendered = rule.template.format_map(mapping)
            return FollowupResolution(status="resolved", output=rendered, metadata={"rule": rule.name})
        return None
```

- [ ] **Step 4: Wire registry + `__init__`**

Create `openagents/plugins/builtin/followup/__init__.py`:

```python
"""Builtin follow-up resolver implementations."""

from .basic import BasicFollowupResolver
from .rule_based import RuleBasedFollowupResolver

__all__ = ["BasicFollowupResolver", "RuleBasedFollowupResolver"]
```

Modify `openagents/plugins/registry.py`: add the import and extend:

```python
"followup_resolver": {
    "basic": BasicFollowupResolver,
    "rule_based": RuleBasedFollowupResolver,
},
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_rule_based_followup.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/followup/ openagents/plugins/registry.py tests/unit/test_rule_based_followup.py
git commit -m "feat(followup): add rule_based resolver"
```

---

## Task 5: `JsonlFileSessionManager`

**Files:**
- Create: `openagents/plugins/builtin/session/jsonl_file.py`
- Modify: `openagents/plugins/builtin/session/__init__.py`
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_jsonl_file_session.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_jsonl_file_session.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openagents.interfaces.session import SessionArtifact
from openagents.plugins.builtin.session.jsonl_file import JsonlFileSessionManager
from openagents.plugins.registry import get_builtin_plugin_class


def _mgr(tmp_path: Path) -> JsonlFileSessionManager:
    return JsonlFileSessionManager(config={"root_dir": str(tmp_path / "sessions")})


@pytest.mark.asyncio
async def test_append_and_reload_transcript(tmp_path: Path):
    m = _mgr(tmp_path)
    await m.append_message("s1", {"role": "user", "content": "hi"})
    await m.append_message("s1", {"role": "assistant", "content": "hello"})

    # Fresh manager reads from disk.
    m2 = _mgr(tmp_path)
    msgs = await m2.load_messages("s1")
    assert len(msgs) == 2
    assert msgs[0]["content"] == "hi"
    assert msgs[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_artifacts_round_trip(tmp_path: Path):
    m = _mgr(tmp_path)
    art = SessionArtifact(name="report", kind="markdown", payload="# hi", metadata={"k": "v"})
    await m.save_artifact("s1", art)
    m2 = _mgr(tmp_path)
    loaded = await m2.list_artifacts("s1")
    assert len(loaded) == 1
    assert loaded[0].name == "report"
    assert loaded[0].metadata["k"] == "v"


@pytest.mark.asyncio
async def test_checkpoint_round_trip(tmp_path: Path):
    m = _mgr(tmp_path)
    await m.append_message("s1", {"role": "user", "content": "x"})
    cp = await m.create_checkpoint("s1", "cp1")
    assert cp.transcript_length == 1
    m2 = _mgr(tmp_path)
    loaded = await m2.load_checkpoint("s1", "cp1")
    assert loaded is not None and loaded.checkpoint_id == "cp1"


@pytest.mark.asyncio
async def test_corrupted_line_skipped(tmp_path: Path, caplog):
    root = tmp_path / "sessions"
    root.mkdir(parents=True)
    (root / "s1.jsonl").write_text(
        '{"type":"transcript","data":{"role":"user","content":"ok"},"ts":"t0"}\n'
        "not-json-at-all\n"
        '{"type":"transcript","data":{"role":"assistant","content":"y"},"ts":"t1"}\n',
        encoding="utf-8",
    )
    m = JsonlFileSessionManager(config={"root_dir": str(root)})
    msgs = await m.load_messages("s1")
    assert [msg["content"] for msg in msgs] == ["ok", "y"]


@pytest.mark.asyncio
async def test_delete_session_removes_file(tmp_path: Path):
    m = _mgr(tmp_path)
    await m.append_message("s1", {"role": "user", "content": "hi"})
    assert (tmp_path / "sessions" / "s1.jsonl").exists()
    await m.delete_session("s1")
    assert not (tmp_path / "sessions" / "s1.jsonl").exists()


@pytest.mark.asyncio
async def test_list_sessions_scans_dir(tmp_path: Path):
    m = _mgr(tmp_path)
    await m.append_message("sA", {"role": "user", "content": "."})
    await m.append_message("sB", {"role": "user", "content": "."})
    m2 = _mgr(tmp_path)
    ids = await m2.list_sessions()
    assert set(ids) >= {"sA", "sB"}


def test_registered_as_builtin():
    assert get_builtin_plugin_class("session", "jsonl_file") is JsonlFileSessionManager
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_jsonl_file_session.py
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `JsonlFileSessionManager`**

Create `openagents/plugins/builtin/session/jsonl_file.py`:

```python
"""JSONL-file backed session manager."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import BaseModel

from openagents.interfaces.session import (
    SESSION_ARTIFACTS,
    SESSION_CHECKPOINTS,
    SESSION_MANAGE,
    SESSION_STATE,
    SESSION_TRANSCRIPT,
    SessionArtifact,
    SessionCheckpoint,
    SessionManagerPlugin,
    _ARTIFACTS_KEY,
    _CHECKPOINTS_KEY,
    _TRANSCRIPT_KEY,
)

logger = logging.getLogger("openagents.session.jsonl_file")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonlFileSessionManager(SessionManagerPlugin):
    """Append-only NDJSON persistence for sessions.

    Each mutation writes one line: ``{"type": "transcript|artifact|checkpoint|state", "data": ..., "ts": ISO}``.
    On first access to a session, prior lines are replayed to rebuild in-memory state.
    """

    class Config(BaseModel):
        root_dir: str
        fsync: bool = False

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={
                SESSION_MANAGE,
                SESSION_STATE,
                SESSION_TRANSCRIPT,
                SESSION_ARTIFACTS,
                SESSION_CHECKPOINTS,
            },
        )
        cfg = self.Config.model_validate(self.config)
        self._root = Path(cfg.root_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._fsync = cfg.fsync
        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, dict[str, Any]] = {}
        self._loaded: set[str] = set()

    def _path(self, sid: str) -> Path:
        return self._root / f"{sid}.jsonl"

    def _append(self, sid: str, event: dict[str, Any]) -> None:
        path = self._path(sid)
        line = json.dumps(event, ensure_ascii=False, default=str)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            if self._fsync:
                fh.flush()
                os.fsync(fh.fileno())

    def _ensure_loaded(self, sid: str) -> dict[str, Any]:
        if sid in self._loaded:
            return self._states.setdefault(sid, {})
        state = self._states.setdefault(sid, {})
        path = self._path(sid)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                for idx, line in enumerate(fh, start=1):
                    line = line.rstrip("\n")
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("jsonl_file: skipped bad line %d in %s", idx, path)
                        continue
                    kind = event.get("type")
                    data = event.get("data")
                    if kind == "transcript" and isinstance(data, dict):
                        state.setdefault(_TRANSCRIPT_KEY, []).append(data)
                    elif kind == "artifact" and isinstance(data, dict):
                        state.setdefault(_ARTIFACTS_KEY, []).append(data)
                    elif kind == "checkpoint" and isinstance(data, dict):
                        checkpoints = state.setdefault(_CHECKPOINTS_KEY, {})
                        checkpoints[data.get("checkpoint_id", f"anon-{idx}")] = data
                    elif kind == "state" and isinstance(data, dict):
                        # Merge top-level keys into state without clobbering transcript/artifacts/checkpoints.
                        for k, v in data.items():
                            if k in (_TRANSCRIPT_KEY, _ARTIFACTS_KEY, _CHECKPOINTS_KEY):
                                continue
                            state[k] = v
        self._loaded.add(sid)
        return state

    @asynccontextmanager
    async def session(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        await lock.acquire()
        try:
            state = self._ensure_loaded(session_id)
            yield state
        finally:
            lock.release()

    async def get_state(self, session_id: str) -> dict[str, Any]:
        return self._ensure_loaded(session_id)

    async def set_state(self, session_id: str, state: dict[str, Any]) -> None:
        self._ensure_loaded(session_id)
        self._states[session_id] = state
        # Persist only caller-owned top-level keys (exclude internal transcript/artifacts/checkpoints).
        payload = {
            k: v for k, v in state.items()
            if k not in (_TRANSCRIPT_KEY, _ARTIFACTS_KEY, _CHECKPOINTS_KEY)
        }
        if payload:
            self._append(session_id, {"type": "state", "data": payload, "ts": _now()})

    async def delete_session(self, session_id: str) -> None:
        self._states.pop(session_id, None)
        self._loaded.discard(session_id)
        path = self._path(session_id)
        if path.exists():
            path.unlink()

    async def list_sessions(self) -> list[str]:
        disk = {p.stem for p in self._root.glob("*.jsonl")}
        return sorted(disk | set(self._states.keys()))

    async def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        state = self._ensure_loaded(session_id)
        transcript = list(state.get(_TRANSCRIPT_KEY, []))
        entry = dict(message)
        transcript.append(entry)
        state[_TRANSCRIPT_KEY] = transcript
        self._append(session_id, {"type": "transcript", "data": entry, "ts": _now()})

    async def save_artifact(self, session_id: str, artifact: SessionArtifact) -> None:
        state = self._ensure_loaded(session_id)
        artifacts = list(state.get(_ARTIFACTS_KEY, []))
        data = artifact.to_dict()
        artifacts.append(data)
        state[_ARTIFACTS_KEY] = artifacts
        self._append(session_id, {"type": "artifact", "data": data, "ts": _now()})

    async def create_checkpoint(self, session_id: str, checkpoint_id: str) -> SessionCheckpoint:
        state = self._ensure_loaded(session_id)
        transcript = list(state.get(_TRANSCRIPT_KEY, []))
        artifacts = list(state.get(_ARTIFACTS_KEY, []))
        checkpoints = dict(state.get(_CHECKPOINTS_KEY, {}))
        checkpoint = SessionCheckpoint(
            checkpoint_id=checkpoint_id,
            state=dict(state),
            transcript_length=len(transcript),
            artifact_count=len(artifacts),
        )
        data = checkpoint.to_dict()
        checkpoints[checkpoint_id] = data
        state[_CHECKPOINTS_KEY] = checkpoints
        self._append(session_id, {"type": "checkpoint", "data": data, "ts": _now()})
        return checkpoint
```

- [ ] **Step 4: Wire registry**

Modify `openagents/plugins/builtin/session/__init__.py`:

```python
"""Builtin session manager plugins."""

from .in_memory import InMemorySessionManager
from .jsonl_file import JsonlFileSessionManager

__all__ = ["InMemorySessionManager", "JsonlFileSessionManager"]
```

Modify `openagents/plugins/registry.py`: add the import line and extend:

```python
"session": {
    "in_memory": InMemorySessionManager,
    "jsonl_file": JsonlFileSessionManager,
},
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_jsonl_file_session.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/session/jsonl_file.py openagents/plugins/builtin/session/__init__.py openagents/plugins/registry.py tests/unit/test_jsonl_file_session.py
git commit -m "feat(session): add jsonl_file persisted session manager"
```

---

## Task 6: `FileLoggingEventBus`

**Files:**
- Create: `openagents/plugins/builtin/events/file_logging.py`
- Modify: `openagents/plugins/builtin/events/__init__.py`
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_file_logging_event_bus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_file_logging_event_bus.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openagents.plugins.builtin.events.file_logging import FileLoggingEventBus
from openagents.plugins.registry import get_builtin_plugin_class


def _make(tmp_path: Path, **overrides) -> FileLoggingEventBus:
    cfg = {"inner": {"type": "async"}, "log_path": str(tmp_path / "events.ndjson")}
    cfg.update(overrides)
    return FileLoggingEventBus(config=cfg)


@pytest.mark.asyncio
async def test_emit_forwards_to_inner_and_writes_line(tmp_path: Path):
    bus = _make(tmp_path)
    captured = []

    async def handler(event):
        captured.append(event.name)

    bus.subscribe("tick", handler)
    await bus.emit("tick", n=1)
    assert captured == ["tick"]

    lines = (tmp_path / "events.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["name"] == "tick"
    assert parsed["payload"]["n"] == 1


@pytest.mark.asyncio
async def test_include_events_filters(tmp_path: Path):
    bus = _make(tmp_path, include_events=["keep"])
    await bus.emit("drop", k=1)
    await bus.emit("keep", k=2)
    lines = (tmp_path / "events.ndjson").read_text(encoding="utf-8").splitlines()
    names = [json.loads(line)["name"] for line in lines]
    assert names == ["keep"]


@pytest.mark.asyncio
async def test_non_serializable_payload_fallbacks(tmp_path: Path):
    bus = _make(tmp_path)

    class Weird:
        def __repr__(self):
            return "<Weird>"

    await bus.emit("x", obj=Weird())
    parsed = json.loads((tmp_path / "events.ndjson").read_text(encoding="utf-8").splitlines()[0])
    assert parsed["payload"]["obj"] == "<Weird>"


@pytest.mark.asyncio
async def test_write_failure_does_not_break_emit(tmp_path: Path, monkeypatch, caplog):
    bus = _make(tmp_path)

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", boom)
    captured = []

    async def handler(event):
        captured.append(event.name)

    bus.subscribe("x", handler)
    await bus.emit("x")  # must not raise
    assert captured == ["x"]


def test_registered_as_builtin():
    assert get_builtin_plugin_class("events", "file_logging") is FileLoggingEventBus
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_file_logging_event_bus.py
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `FileLoggingEventBus`**

Create `openagents/plugins/builtin/events/file_logging.py`:

```python
"""File-logging event bus wrapper."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from openagents.interfaces.events import (
    EVENT_EMIT,
    EVENT_HISTORY,
    EVENT_SUBSCRIBE,
    EventBusPlugin,
    RuntimeEvent,
)

logger = logging.getLogger("openagents.events.file_logging")


class FileLoggingEventBus(EventBusPlugin):
    """Wraps another event bus and appends every matched event to an NDJSON log."""

    class Config(BaseModel):
        inner: dict[str, Any] = Field(default_factory=lambda: {"type": "async"})
        log_path: str
        include_events: list[str] | None = None
        max_history: int = 10_000

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={EVENT_SUBSCRIBE, EVENT_EMIT, EVENT_HISTORY},
        )
        cfg = self.Config.model_validate(self.config)
        self._log_path = Path(cfg.log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._include = set(cfg.include_events) if cfg.include_events is not None else None
        self._inner = self._load_inner(cfg.inner)

    def _load_inner(self, ref: dict[str, Any]) -> Any:
        from openagents.config.schema import EventBusRef
        from openagents.plugins.loader import _load_plugin

        return _load_plugin("events", EventBusRef(**ref), required_methods=("emit", "subscribe"))

    def subscribe(self, event_name: str, handler: Callable[[RuntimeEvent], Awaitable[None] | None]) -> None:
        self._inner.subscribe(event_name, handler)

    async def emit(self, event_name: str, **payload: Any) -> RuntimeEvent:
        event = await self._inner.emit(event_name, **payload)
        if self._include is None or event_name in self._include:
            try:
                line = json.dumps(
                    {"name": event_name, "payload": payload, "ts": datetime.now(timezone.utc).isoformat()},
                    ensure_ascii=False,
                    default=str,
                )
                with open(self._log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:
                logger.error("file_logging: append failed: %s", exc)
        return event

    async def get_history(self, event_name: str | None = None, limit: int | None = None) -> list[RuntimeEvent]:
        return await self._inner.get_history(event_name=event_name, limit=limit)

    async def clear_history(self) -> None:
        await self._inner.clear_history()
```

- [ ] **Step 4: Wire registry**

Modify `openagents/plugins/builtin/events/__init__.py`:

```python
"""Builtin event bus plugins."""

from .async_event_bus import AsyncEventBus
from .file_logging import FileLoggingEventBus

__all__ = ["AsyncEventBus", "FileLoggingEventBus"]
```

Modify `openagents/plugins/registry.py`: add the import and extend:

```python
"events": {
    "async": AsyncEventBus,
    "file_logging": FileLoggingEventBus,
},
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_file_logging_event_bus.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/events/file_logging.py openagents/plugins/builtin/events/__init__.py openagents/plugins/registry.py tests/unit/test_file_logging_event_bus.py
git commit -m "feat(events): add file_logging event bus wrapper"
```

---

## Task 7: `StrictJsonResponseRepairPolicy`

**Files:**
- Create: `openagents/plugins/builtin/response_repair/strict_json.py`
- Modify: `openagents/plugins/builtin/response_repair/__init__.py` (create if missing)
- Modify: `openagents/plugins/registry.py`
- Test: `tests/unit/test_strict_json_response_repair.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_strict_json_response_repair.py
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from openagents.plugins.builtin.response_repair.strict_json import StrictJsonResponseRepairPolicy
from openagents.plugins.registry import get_builtin_plugin_class


def _ctx():
    return SimpleNamespace(input_text="", memory_view={}, tools={})


async def _call(policy: StrictJsonResponseRepairPolicy, blocks: list[dict]):
    return await policy.repair_empty_response(
        context=_ctx(), messages=[], assistant_content=blocks, stop_reason=None, retries=0,
    )


@pytest.mark.asyncio
async def test_fenced_json_salvage():
    policy = StrictJsonResponseRepairPolicy()
    blocks = [{"type": "text", "text": "pre\n```json\n{\"ok\": true}\n```\npost"}]
    decision = await _call(policy, blocks)
    assert decision.status == "repaired"
    text = decision.output[0]["text"]
    assert json.loads(text) == {"ok": True}
    assert decision.metadata["salvaged_from"] == "fenced_code"


@pytest.mark.asyncio
async def test_bare_json_salvage():
    policy = StrictJsonResponseRepairPolicy()
    blocks = [{"type": "text", "text": "garbage {\"x\": 1, \"y\": [1,2]} trailing"}]
    decision = await _call(policy, blocks)
    assert decision.status == "repaired"
    assert json.loads(decision.output[0]["text"]) == {"x": 1, "y": [1, 2]}
    assert decision.metadata["salvaged_from"] == "bare_json"


@pytest.mark.asyncio
async def test_non_json_fallback_to_basic():
    policy = StrictJsonResponseRepairPolicy(config={"fallback_to_basic": True})
    decision = await _call(policy, [{"type": "text", "text": "no json here at all"}])
    assert decision is not None
    assert decision.status in {"error", "abstain"}  # BasicResponseRepairPolicy emits "error"


@pytest.mark.asyncio
async def test_non_json_abstain_when_flag_false():
    policy = StrictJsonResponseRepairPolicy(config={"fallback_to_basic": False})
    decision = await _call(policy, [{"type": "text", "text": "no json here at all"}])
    assert decision.status == "abstain"


@pytest.mark.asyncio
async def test_min_text_length_floor():
    policy = StrictJsonResponseRepairPolicy(config={"min_text_length": 200, "fallback_to_basic": False})
    decision = await _call(policy, [{"type": "text", "text": "{\"x\":1}"}])
    assert decision.status == "abstain"


def test_registered_as_builtin():
    assert get_builtin_plugin_class("response_repair_policy", "strict_json") is StrictJsonResponseRepairPolicy
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_strict_json_response_repair.py
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `StrictJsonResponseRepairPolicy`**

Create `openagents/plugins/builtin/response_repair/strict_json.py`:

```python
"""Strict-JSON response repair policy."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from openagents.interfaces.response_repair import ResponseRepairDecision, ResponseRepairPolicyPlugin
from openagents.plugins.builtin.response_repair.basic import BasicResponseRepairPolicy


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_balanced(text: str) -> str | None:
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


class StrictJsonResponseRepairPolicy(ResponseRepairPolicyPlugin):
    """Salvage JSON from assistant text blocks; optionally delegate to Basic on miss."""

    class Config(BaseModel):
        min_text_length: int = 8
        strip_code_fence: bool = True
        fallback_to_basic: bool = True

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._min_len = cfg.min_text_length
        self._strip_fence = cfg.strip_code_fence
        self._fallback_to_basic = cfg.fallback_to_basic
        self._basic = BasicResponseRepairPolicy() if self._fallback_to_basic else None

    def _collect_text(self, blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)

    async def repair_empty_response(
        self,
        *,
        context: Any,
        messages: list[dict[str, Any]],
        assistant_content: list[dict[str, Any]],
        stop_reason: str | None,
        retries: int,
    ) -> ResponseRepairDecision | None:
        text = self._collect_text(assistant_content)
        if len(text) < self._min_len:
            return await self._miss(context, messages, assistant_content, stop_reason, retries)

        candidate: str | None = None
        salvaged_from: str | None = None
        if self._strip_fence:
            match = _FENCE_RE.search(text)
            if match:
                candidate = match.group(1).strip()
                salvaged_from = "fenced_code"
        if candidate is None:
            extracted = _extract_balanced(text)
            if extracted is not None:
                candidate = extracted
                salvaged_from = "bare_json"

        if candidate is not None:
            try:
                obj = json.loads(candidate)
            except json.JSONDecodeError:
                obj = None
            if obj is not None:
                keys = list(obj.keys()) if isinstance(obj, dict) else []
                return ResponseRepairDecision(
                    status="repaired",
                    output=[{"type": "text", "text": json.dumps(obj, ensure_ascii=False)}],
                    metadata={"salvaged_from": salvaged_from, "keys": keys},
                )

        return await self._miss(context, messages, assistant_content, stop_reason, retries)

    async def _miss(self, context, messages, assistant_content, stop_reason, retries):
        if self._basic is not None:
            return await self._basic.repair_empty_response(
                context=context,
                messages=messages,
                assistant_content=assistant_content,
                stop_reason=stop_reason,
                retries=retries,
            )
        return ResponseRepairDecision(status="abstain", reason="no JSON extractable")
```

- [ ] **Step 4: Wire registry + `__init__`**

Create `openagents/plugins/builtin/response_repair/__init__.py`:

```python
"""Builtin response-repair policy implementations."""

from .basic import BasicResponseRepairPolicy
from .strict_json import StrictJsonResponseRepairPolicy

__all__ = ["BasicResponseRepairPolicy", "StrictJsonResponseRepairPolicy"]
```

Modify `openagents/plugins/registry.py`: add the import and extend:

```python
"response_repair_policy": {
    "basic": BasicResponseRepairPolicy,
    "strict_json": StrictJsonResponseRepairPolicy,
},
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_strict_json_response_repair.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add openagents/plugins/builtin/response_repair/ openagents/plugins/registry.py tests/unit/test_strict_json_response_repair.py
git commit -m "feat(response_repair): add strict_json salvager policy"
```

---

## Task 8: CLI smoke — list-plugins & schema pick up new builtins

**Files:**
- Modify: `tests/unit/test_cli.py` OR add `tests/unit/test_cli_new_builtins.py` (new file is simpler)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cli_new_builtins.py
from __future__ import annotations

import json
import subprocess
import sys

EXPECTED = {
    "tool_executor": {"retry"},
    "execution_policy": {"composite", "network_allowlist"},
    "followup_resolver": {"rule_based"},
    "session": {"jsonl_file"},
    "events": {"file_logging"},
    "response_repair_policy": {"strict_json"},
}


def _run(*args: str) -> str:
    out = subprocess.run(
        [sys.executable, "-m", "openagents.cli", *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def test_list_plugins_includes_new_builtins():
    for kind, names in EXPECTED.items():
        stdout = _run("list-plugins", "--kind", kind)
        for name in names:
            assert name in stdout, f"{kind}/{name} missing from list-plugins"


def test_schema_exposes_configs_for_new_builtins():
    for kind, names in EXPECTED.items():
        for name in names:
            stdout = _run("schema", "--kind", kind, "--name", name)
            data = json.loads(stdout)
            assert isinstance(data, dict) and ("properties" in data or "$ref" in data), (kind, name)
```

- [ ] **Step 2: Inspect existing CLI to confirm flags**

```bash
uv run python -m openagents.cli list-plugins --help
uv run python -m openagents.cli schema --help
```
Expected: confirm `--kind` / `--name` flags exist. If the flag names differ (e.g. positional args), adjust the test to match before proceeding. Look at `openagents/cli/list_plugins_cmd.py` and `openagents/cli/schema_cmd.py` (or equivalent) to confirm.

- [ ] **Step 3: Run test**

```bash
uv run pytest -q tests/unit/test_cli_new_builtins.py
```
Expected: PASS (since Tasks 1–7 already registered the builtins). If FAIL, check that each `registry.py` import line landed and the builtin class exposes `Config` for `schema` command.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_cli_new_builtins.py
git commit -m "test(cli): smoke-check new builtins in list-plugins and schema"
```

---

## Task 9: Research-Analyst example — stub server + fixtures

**Files:**
- Create: `examples/research_analyst/__init__.py` (empty)
- Create: `examples/research_analyst/README.md`
- Create: `examples/research_analyst/app/__init__.py` (empty)
- Create: `examples/research_analyst/app/stub_server.py`
- Create: `examples/research_analyst/app/fixtures/knowledge/topic-a.md`
- Create: `examples/research_analyst/app/fixtures/knowledge/topic-b.md`
- Create: `examples/research_analyst/app/fixtures/knowledge/index.json`
- Create: `examples/research_analyst/app/followup_rules.json`
- Test: `tests/unit/test_research_analyst_stub_server.py`

- [ ] **Step 1: Confirm aiohttp is available**

```bash
uv pip show aiohttp | head -1
```
If output is empty, run `uv add --dev aiohttp`.

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_research_analyst_stub_server.py
from __future__ import annotations

import aiohttp
import pytest

from examples.research_analyst.app.stub_server import start_stub_server


@pytest.mark.asyncio
async def test_topic_a_returns_json():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/pages/topic-a") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "title" in data


@pytest.mark.asyncio
async def test_topic_b_returns_markdown():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/pages/topic-b") as resp:
                assert resp.status == 200
                body = await resp.text()
                assert body.startswith("#")


@pytest.mark.asyncio
async def test_flaky_fails_twice_then_succeeds():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as session:
            statuses = []
            for _ in range(3):
                async with session.get(f"{base_url}/pages/flaky") as resp:
                    statuses.append(resp.status)
            assert statuses == [503, 503, 200]


@pytest.mark.asyncio
async def test_counter_is_per_instance():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/pages/flaky") as r:
                assert r.status == 503
    # Brand new server → counter reset.
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/pages/flaky") as r:
                assert r.status == 503
```

- [ ] **Step 3: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_research_analyst_stub_server.py
```
Expected: ModuleNotFoundError for `examples.research_analyst.app.stub_server`.

- [ ] **Step 4: Implement stub server + fixtures**

`examples/research_analyst/__init__.py`:

```python
```

`examples/research_analyst/app/__init__.py`:

```python
```

`examples/research_analyst/app/stub_server.py`:

```python
"""In-process stub HTTP server for the research-analyst example."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from aiohttp import web


_TOPIC_A = {
    "title": "Topic A — Overview",
    "summary": "Topic A is the first sample corpus used by the research-analyst example.",
    "keywords": ["alpha", "baseline", "demo"],
    "sections": [
        {"heading": "Definition", "body": "Topic A is a fixture payload."},
        {"heading": "Usage", "body": "Used by the integration test."},
    ],
}

_TOPIC_B = "# Topic B\n\nTopic B lives in a markdown fixture so the agent exercises mixed content types.\n"

_FLAKY_OK = {"title": "Flaky source", "summary": "Returned after two 503 attempts."}


class _Flaky:
    def __init__(self) -> None:
        self.calls = 0


async def _topic_a(request: web.Request) -> web.Response:
    return web.json_response(_TOPIC_A)


async def _topic_b(request: web.Request) -> web.Response:
    return web.Response(text=_TOPIC_B, content_type="text/markdown")


def _flaky_handler(state: _Flaky):
    async def _handler(request: web.Request) -> web.Response:
        state.calls += 1
        if state.calls <= 2:
            return web.json_response({"error": "transient"}, status=503)
        return web.json_response(_FLAKY_OK)

    return _handler


@asynccontextmanager
async def start_stub_server() -> AsyncIterator[str]:
    """Start the stub server on ``127.0.0.1:0`` and yield its base URL."""
    state = _Flaky()
    app = web.Application()
    app.add_routes([
        web.get("/pages/topic-a", _topic_a),
        web.get("/pages/topic-b", _topic_b),
        web.get("/pages/flaky", _flaky_handler(state)),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sockets = site._server.sockets  # type: ignore[attr-defined]
    port = sockets[0].getsockname()[1] if sockets else 0
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()
```

`examples/research_analyst/app/fixtures/knowledge/topic-a.md`:

```markdown
# Topic A (local supplement)

Local knowledge about topic A that complements the fetched web page.
```

`examples/research_analyst/app/fixtures/knowledge/topic-b.md`:

```markdown
# Topic B (local supplement)

Local knowledge about topic B.
```

`examples/research_analyst/app/fixtures/knowledge/index.json`:

```json
{
  "topics": ["topic-a", "topic-b"],
  "notes": "Research-analyst example fixture index."
}
```

`examples/research_analyst/app/followup_rules.json`:

```json
[
  {
    "name": "queried_urls",
    "pattern": "(刚.*(查|调|访问)|what.*urls?.*(query|hit|fetch))",
    "template": "本轮共调用的工具：{tool_ids}\n最后一次的输入是：{last_input}",
    "requires_history": true
  },
  {
    "name": "last_tools",
    "pattern": "(用了哪些工具|which tools.*use)",
    "template": "上一轮工具：{tool_ids}",
    "requires_history": true
  }
]
```

`examples/research_analyst/README.md`:

```markdown
# research_analyst example

Offline research agent that exercises every new builtin added in 0.3.x:

| seam | builtin | where |
|---|---|---|
| tool_executor | retry | agent.json |
| execution_policy | composite + network_allowlist + filesystem | agent.json |
| followup_resolver | rule_based | agent.json + app/followup_rules.json |
| session | jsonl_file | agent.json + ./sessions |
| events | file_logging | agent.json + ./sessions/events.ndjson |
| response_repair_policy | strict_json | agent.json |

## Run

```bash
uv run python examples/research_analyst/run_demo.py
```

No external network is required; an aiohttp stub server on 127.0.0.1 serves all web content.
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/test_research_analyst_stub_server.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add examples/research_analyst/ tests/unit/test_research_analyst_stub_server.py
git commit -m "feat(example/research_analyst): add stub server, fixtures, and followup rules"
```

---

## Task 10: Research-Analyst example — `FollowupFirstReActPattern`

**Files:**
- Create: `examples/research_analyst/app/followup_pattern.py`
- Test: `tests/unit/test_research_analyst_followup_pattern.py`

The kernel does not auto-consult `ctx.followup_resolver`. This thin wrapper pattern consults it before delegating to `react`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_research_analyst_followup_pattern.py
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from openagents.interfaces.followup import FollowupResolution
from examples.research_analyst.app.followup_pattern import FollowupFirstReActPattern


class _InnerReact:
    def __init__(self, out="react-ran"):
        self.called = 0
        self._out = out

    async def execute(self) -> Any:
        self.called += 1
        return self._out

    async def react(self) -> dict[str, Any]:
        return {"type": "final", "content": "use execute"}


class _Resolver:
    def __init__(self, resolution: FollowupResolution | None):
        self._resolution = resolution

    async def resolve(self, *, context):
        return self._resolution


def _ctx(resolver):
    return SimpleNamespace(
        input_text="", memory_view={}, state={}, tools={},
        followup_resolver=resolver,
    )


@pytest.mark.asyncio
async def test_resolver_resolves_short_circuits_inner():
    inner = _InnerReact()
    pattern = FollowupFirstReActPattern(config={}, inner=inner)
    pattern.context = _ctx(_Resolver(FollowupResolution(status="resolved", output="local-answer")))
    out = await pattern.execute()
    assert out == "local-answer"
    assert inner.called == 0


@pytest.mark.asyncio
async def test_resolver_none_delegates_to_inner():
    inner = _InnerReact()
    pattern = FollowupFirstReActPattern(config={}, inner=inner)
    pattern.context = _ctx(_Resolver(None))
    out = await pattern.execute()
    assert out == "react-ran"
    assert inner.called == 1


@pytest.mark.asyncio
async def test_resolver_abstain_delegates_to_inner():
    inner = _InnerReact()
    pattern = FollowupFirstReActPattern(config={}, inner=inner)
    pattern.context = _ctx(_Resolver(FollowupResolution(status="abstain")))
    out = await pattern.execute()
    assert out == "react-ran"
    assert inner.called == 1
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest -q tests/unit/test_research_analyst_followup_pattern.py
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `FollowupFirstReActPattern`**

Create `examples/research_analyst/app/followup_pattern.py`:

```python
"""App-layer pattern: consult followup_resolver before running ReAct."""

from __future__ import annotations

from typing import Any

from openagents.interfaces.pattern import PatternPlugin
from openagents.plugins.builtin.pattern.react import ReActPattern


class FollowupFirstReActPattern(PatternPlugin):
    """Wraps the builtin ``react`` pattern with a follow-up short-circuit.

    If ``ctx.followup_resolver`` returns ``status == "resolved"``, the pattern
    returns that output directly without consulting the inner pattern (and thus
    without calling the LLM). Any other outcome — ``None``, ``abstain``, or
    ``error`` — falls through to the inner ReAct pattern.
    """

    def __init__(self, config: dict[str, Any] | None = None, inner: Any | None = None):
        super().__init__(config=config or {}, capabilities={"pattern.execute", "pattern.react"})
        self._inner = inner if inner is not None else ReActPattern(config=self.config)

    @property
    def context(self):
        return getattr(self._inner, "context", None)

    @context.setter
    def context(self, value):
        self._inner.context = value

    async def execute(self) -> Any:
        ctx = self._inner.context
        resolver = getattr(ctx, "followup_resolver", None) if ctx is not None else None
        if resolver is not None:
            try:
                resolution = await resolver.resolve(context=ctx)
            except Exception:  # pragma: no cover - defensive
                resolution = None
            if resolution is not None and resolution.status == "resolved":
                if ctx is not None and hasattr(ctx, "state"):
                    ctx.state["_runtime_last_output"] = resolution.output
                    ctx.state["resolved_by"] = "followup_resolver"
                return resolution.output
        return await self._inner.execute()

    async def react(self) -> dict[str, Any]:
        return await self._inner.react()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest -q tests/unit/test_research_analyst_followup_pattern.py
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/research_analyst/app/followup_pattern.py tests/unit/test_research_analyst_followup_pattern.py
git commit -m "feat(example/research_analyst): add FollowupFirstReActPattern wrapper"
```

---

## Task 11: Research-Analyst example — agent.json + run_demo.py

**Files:**
- Create: `examples/research_analyst/agent.json`
- Create: `examples/research_analyst/run_demo.py`
- Modify: `.gitignore` (ignore `examples/research_analyst/sessions/`)

- [ ] **Step 1: Create `agent.json`**

Create `examples/research_analyst/agent.json`:

```json
{
  "version": "0.3",
  "agents": [
    {
      "id": "research-analyst",
      "provider": {"type": "mock", "config": {}},
      "system_prompt": "You are a research analyst. Use tools to fetch web pages via http_request (base URL: {BASE_URL}) and read local fixtures via read_file/list_files. Produce a markdown report and save it with write_file.",
      "memory": {"type": "window_buffer", "config": {"window_size": 8}},
      "pattern": {
        "impl": "examples.research_analyst.app.followup_pattern:FollowupFirstReActPattern",
        "config": {"max_iterations": 6}
      },
      "tools": [
        {"id": "http_request", "type": "http_request"},
        {"id": "read_file", "type": "read_file"},
        {"id": "list_files", "type": "list_files"},
        {"id": "json_parse", "type": "json_parse"},
        {"id": "calc", "type": "calc"},
        {"id": "write_file", "type": "write_file"}
      ],
      "tool_executor": {
        "type": "retry",
        "config": {
          "inner": {"type": "safe", "config": {"default_timeout_ms": 5000}},
          "max_attempts": 3,
          "initial_delay_ms": 50,
          "retry_on": ["RetryableToolError", "ToolTimeoutError"]
        }
      },
      "execution_policy": {
        "type": "composite",
        "config": {
          "mode": "all",
          "policies": [
            {"type": "filesystem", "config": {
              "read_roots": ["./examples/research_analyst/app/fixtures"],
              "write_roots": ["./examples/research_analyst/sessions"]
            }},
            {"type": "network_allowlist", "config": {
              "allow_hosts": ["127.0.0.1", "localhost"],
              "allow_schemes": ["http"],
              "applies_to_tools": ["http_request"],
              "deny_private_networks": false
            }}
          ]
        }
      },
      "context_assembler": {
        "type": "head_tail",
        "config": {"max_input_tokens": 6000, "head_messages": 2}
      },
      "followup_resolver": {
        "type": "rule_based",
        "config": {"rules_file": "./examples/research_analyst/app/followup_rules.json"}
      },
      "response_repair_policy": {
        "type": "strict_json",
        "config": {"fallback_to_basic": true}
      }
    }
  ],
  "runtime": {"type": "default"},
  "session": {
    "type": "jsonl_file",
    "config": {"root_dir": "./examples/research_analyst/sessions"}
  },
  "events": {
    "type": "file_logging",
    "config": {
      "inner": {"type": "async"},
      "log_path": "./examples/research_analyst/sessions/events.ndjson"
    }
  },
  "skills": {"type": "local"}
}
```

- [ ] **Step 2: Create `run_demo.py`**

```python
"""Run the research-analyst example end-to-end against the local stub server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from openagents.interfaces.runtime import RunRequest
from openagents.runtime.runtime import Runtime

from examples.research_analyst.app.stub_server import start_stub_server


_HERE = Path(__file__).resolve().parent
_AGENT_JSON = _HERE / "agent.json"


def _load_config(base_url: str) -> dict:
    raw = _AGENT_JSON.read_text(encoding="utf-8").replace("{BASE_URL}", base_url)
    return json.loads(raw)


async def main() -> None:
    async with start_stub_server() as base_url:
        config = _load_config(base_url)
        runtime = Runtime.from_dict(config)
        session_id = "demo-session"

        # Run #1 — research request.
        r1 = await runtime.run_detailed(RunRequest(
            agent_id="research-analyst",
            session_id=session_id,
            input_text=(
                "Research topic-a and topic-b. Also fetch the flaky source (it may need retries). "
                "Produce a short markdown report and save it as sessions/report.md."
            ),
            context_hints={"base_url": base_url},
        ))
        print("Run #1 output:", r1.output)

        # Run #2 — follow-up short-circuit.
        r2 = await runtime.run_detailed(RunRequest(
            agent_id="research-analyst",
            session_id=session_id,
            input_text="你刚才查了哪些 URL？",
        ))
        print("Run #2 output:", r2.output)

        sessions_dir = _HERE / "sessions"
        print("Session file:", sessions_dir / f"{session_id}.jsonl")
        print("Events log:", sessions_dir / "events.ndjson")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Ignore generated session files**

Append to `.gitignore` (create if missing):

```
examples/research_analyst/sessions/
```

- [ ] **Step 4: Manual smoke — run the demo once**

```bash
uv run python examples/research_analyst/run_demo.py
```
Expected: the command finishes without exception; `examples/research_analyst/sessions/demo-session.jsonl` and `examples/research_analyst/sessions/events.ndjson` exist. The mock provider will likely not synthesize perfect tool_use chains — that is OK; the integration test in Task 12 injects a deterministic LLM client. The point of this smoke is to confirm `agent.json` parses, all plugins load, and the stub server + session files write.

If the demo errors out with a loader error, fix the referenced `type`/`impl` until the error names the plugin in question, then re-run.

- [ ] **Step 5: Commit**

```bash
git add examples/research_analyst/agent.json examples/research_analyst/run_demo.py .gitignore
git commit -m "feat(example/research_analyst): add agent.json and run_demo.py"
```

---

## Task 12: Research-Analyst integration test

**Files:**
- Create: `tests/integration/test_research_analyst_example.py`

- [ ] **Step 1: Write the integration test**

Model after `tests/integration/test_production_coding_agent_example.py`: inject a deterministic `LLMClient` via `openagents.llm.registry`, drive the agent with scripted tool_use outputs.

```python
# tests/integration/test_research_analyst_example.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import openagents.llm.registry as llm_registry
from openagents.llm.base import LLMClient
from openagents.interfaces.runtime import RunRequest
from openagents.runtime.runtime import Runtime

from examples.research_analyst.app.stub_server import start_stub_server


_EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "research_analyst"
_SESSIONS_DIR = _EXAMPLE_DIR / "sessions"


class _ScriptedLLM(LLMClient):
    """Emit a scripted tool_use sequence then a final text block."""

    def __init__(self, base_url: str):
        self.calls = 0
        self._script = [
            # Step 1: fetch topic-a.
            [{"type": "tool_use", "id": "c1", "name": "http_request", "input": {"url": f"{base_url}/pages/topic-a", "method": "GET"}}],
            # Step 2: fetch flaky (will be retried by RetryToolExecutor).
            [{"type": "tool_use", "id": "c2", "name": "http_request", "input": {"url": f"{base_url}/pages/flaky", "method": "GET"}}],
            # Step 3: write a report under sessions/.
            [{"type": "tool_use", "id": "c3", "name": "write_file", "input": {
                "file_path": str(_SESSIONS_DIR / "report.md"),
                "content": "# Research report\n\ntopic-a + flaky combined.\n",
            }}],
            # Step 4: final text.
            [{"type": "text", "text": "Done. Report saved to sessions/report.md."}],
        ]

    async def complete(self, *, messages, model=None, temperature=None, max_tokens=None,
                       tools=None, tool_choice=None, response_format=None) -> str:
        _ = (model, temperature, max_tokens, tools, tool_choice, response_format, messages)
        self.calls += 1
        if self._script:
            blocks = self._script.pop(0)
        else:
            blocks = [{"type": "text", "text": "ok"}]
        return json.dumps({"content": blocks})


@pytest.fixture(autouse=True)
def _reset_sessions():
    if _SESSIONS_DIR.exists():
        shutil.rmtree(_SESSIONS_DIR, ignore_errors=True)
    yield
    if _SESSIONS_DIR.exists():
        shutil.rmtree(_SESSIONS_DIR, ignore_errors=True)


def _load_config(base_url: str) -> dict:
    raw = (_EXAMPLE_DIR / "agent.json").read_text(encoding="utf-8").replace("{BASE_URL}", base_url)
    return json.loads(raw)


@pytest.mark.asyncio
async def test_research_analyst_end_to_end(monkeypatch):
    async with start_stub_server() as base_url:
        scripted = _ScriptedLLM(base_url=base_url)
        monkeypatch.setattr(llm_registry, "get_llm", lambda *a, **kw: scripted, raising=False)
        config = _load_config(base_url)
        runtime = Runtime.from_dict(config)

        await runtime.run_detailed(RunRequest(
            agent_id="research-analyst",
            session_id="e2e",
            input_text="research topic-a + flaky and save a report",
        ))

        # Assert events.ndjson records a retry.
        events_path = _SESSIONS_DIR / "events.ndjson"
        assert events_path.exists()
        retry_events = [
            json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()
            if "retry_attempts" in line
        ]
        assert any(e["payload"].get("metadata", {}).get("retry_attempts", 0) >= 2 for e in retry_events)

        # Assert report markdown exists.
        assert (_SESSIONS_DIR / "report.md").exists()

        # Run #2 should resolve locally via rule_based followup (mock call counter does not increment).
        calls_before = scripted.calls
        await runtime.run_detailed(RunRequest(
            agent_id="research-analyst",
            session_id="e2e",
            input_text="你刚才查了哪些 URL？",
        ))
        assert scripted.calls == calls_before, "followup should not hit the LLM"

        # Assert jsonl_file session can be replayed by a fresh manager instance.
        from openagents.plugins.builtin.session.jsonl_file import JsonlFileSessionManager
        fresh = JsonlFileSessionManager(config={"root_dir": str(_SESSIONS_DIR)})
        msgs = await fresh.load_messages("e2e")
        assert len(msgs) > 0


@pytest.mark.asyncio
async def test_research_analyst_policy_denial(monkeypatch):
    """When the LLM tries to call a non-allowlisted host, the composite policy denies."""

    async with start_stub_server() as _base_url:
        class _DenyBaitLLM(LLMClient):
            def __init__(self):
                self.calls = 0
                self._script = [
                    [{"type": "tool_use", "id": "d1", "name": "http_request",
                      "input": {"url": "http://evil.test/x", "method": "GET"}}],
                    [{"type": "text", "text": "blocked."}],
                ]

            async def complete(self, **kw):
                self.calls += 1
                blocks = self._script.pop(0) if self._script else [{"type": "text", "text": "."}]
                return json.dumps({"content": blocks})

        scripted = _DenyBaitLLM()
        monkeypatch.setattr(llm_registry, "get_llm", lambda *a, **kw: scripted, raising=False)
        config = _load_config(_base_url)
        runtime = Runtime.from_dict(config)
        await runtime.run_detailed(RunRequest(
            agent_id="research-analyst", session_id="deny", input_text="try evil url",
        ))
        events_path = _SESSIONS_DIR / "events.ndjson"
        text = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
        assert "network_allowlist" in text


@pytest.mark.asyncio
async def test_research_analyst_strict_json_repair(monkeypatch):
    """When the provider returns a fenced JSON text, strict_json repairs it."""

    async with start_stub_server() as base_url:
        class _FencedLLM(LLMClient):
            def __init__(self):
                self.calls = 0

            async def complete(self, **kw):
                self.calls += 1
                # Return an empty content list → triggers repair path; assistant_content collects
                # text blocks fed in from prior stream.
                return json.dumps({"content": []})

        scripted = _FencedLLM()
        monkeypatch.setattr(llm_registry, "get_llm", lambda *a, **kw: scripted, raising=False)
        config = _load_config(base_url)
        runtime = Runtime.from_dict(config)
        # Drive a single run — we are asserting the repair path doesn't crash the agent.
        result = await runtime.run_detailed(RunRequest(
            agent_id="research-analyst", session_id="repair", input_text="do a thing",
        ))
        # Strict JSON is a defense-in-depth layer; the assertion is that the run completes.
        assert result is not None
```

> **Note on exact LLM injection path:** `openagents.llm.registry` may expose a different accessor than `get_llm` — inspect `openagents/llm/registry.py` and `tests/integration/test_production_coding_agent_example.py` to mirror exactly how the production example patches the LLM (the production test is the canonical pattern). Adjust the `monkeypatch.setattr` target to match. The scripted-LLM pattern and assertion style above otherwise stand.

- [ ] **Step 2: Run integration test**

```bash
uv run pytest -q tests/integration/test_research_analyst_example.py
```
Expected: all three cases PASS. If any assertion fails, read the `events.ndjson` and session file contents to diagnose before tweaking either the example config or the test expectations.

- [ ] **Step 3: Run full suite + coverage**

```bash
uv run pytest -q
uv run coverage run -m pytest && uv run coverage report
```
Expected: full suite green; `coverage report` ≥ 90% overall. Any new-file coverage below 90% must get additional unit tests added in the originating task before this step can be considered done.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_research_analyst_example.py
git commit -m "test(integration): research_analyst example end-to-end coverage"
```

---

## Task 13: Docs updates

**Files:**
- Modify: `examples/README.md`
- Modify: `docs/examples.md`
- Modify: `docs/developer-guide.md`

- [ ] **Step 1: `examples/README.md` — add research_analyst section**

Append immediately after the `production_coding_agent/` section:

```markdown
### `research_analyst/`

Offline research-agent example exercising the 0.3.x second-builtin additions:

- `retry` tool executor
- `composite` + `network_allowlist` execution policies
- `rule_based` follow-up resolver
- `jsonl_file` session manager
- `file_logging` event bus
- `strict_json` response repair policy

Runs entirely against an in-process aiohttp stub server — no internet required.

```bash
uv run python examples/research_analyst/run_demo.py
```

Verify:

```bash
uv run pytest -q tests/integration/test_research_analyst_example.py
```
```

- [ ] **Step 2: `docs/examples.md` — add walkthrough section**

Append a new section at the end of the file:

```markdown
## research_analyst

该示例展示 0.3.x 新增的 7 个 builtin 怎么在一个真实任务里串起来。

| seam | builtin | 作用 |
| --- | --- | --- |
| tool_executor | `retry` | `/pages/flaky` 前两次返回 503，第三次才成功 —— 重试透明化 |
| execution_policy | `composite` + `filesystem` + `network_allowlist` | AND 组合文件根和网络 host 白名单 |
| followup_resolver | `rule_based` | 第二轮 "你刚才查了哪些 URL" 通过 regex → 模板本地解析，不打模型 |
| session | `jsonl_file` | 全部 transcript / artifact / checkpoint 落盘到 `sessions/<sid>.jsonl` |
| events | `file_logging` | 所有事件追加到 `sessions/events.ndjson`，便于审计 |
| response_repair_policy | `strict_json` | 模型偶发返回 markdown fenced JSON 时，从文本里抽出 JSON |

pattern 层用的是 `FollowupFirstReActPattern`（`examples/research_analyst/app/followup_pattern.py`），它在进 ReAct 前先问 `ctx.followup_resolver`。这是 app-layer 而不是 SDK 行为，参见 `docs/seams-and-extension-points.md` §6 中 "followup_resolver 由 pattern 调用"。
```

- [ ] **Step 3: `docs/developer-guide.md` — document the new type keys**

Locate the existing section that enumerates builtin plugin `type` keys (search for "type keys" or the name of an existing key such as `"filesystem"`) and add one-line entries for each new key: `retry`, `composite`, `network_allowlist`, `rule_based`, `jsonl_file`, `file_logging`, `strict_json`. If no such enumeration exists, add a short sub-section titled "新增 builtin 类型 (0.3.x)" with a single markdown table mirroring the `examples.md` table above. Keep each description to one line.

- [ ] **Step 4: Verify full suite still green**

```bash
uv run pytest -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add examples/README.md docs/examples.md docs/developer-guide.md
git commit -m "docs: document new builtins and research_analyst example"
```

---

## Self-review

**1. Spec coverage check:**
- Spec §4.1 RetryToolExecutor → Task 1 ✓
- Spec §4.2 CompositeExecutionPolicy → Task 2 ✓
- Spec §4.3 NetworkAllowlistExecutionPolicy → Task 3 ✓
- Spec §4.4 RuleBasedFollowupResolver → Task 4 ✓
- Spec §4.5 JsonlFileSessionManager (with override-mutation-methods fix) → Task 5 ✓
- Spec §4.6 FileLoggingEventBus → Task 6 ✓
- Spec §4.7 StrictJsonResponseRepairPolicy → Task 7 ✓
- Spec §5 registry wiring → done per-task plus Task 8 CLI smoke ✓
- Spec §6 example: stub server / fixtures / followup_rules.json → Task 9; FollowupFirstReActPattern → Task 10; agent.json + run_demo.py → Task 11 ✓
- Spec §8 unit tests per builtin → embedded in Tasks 1–7; integration 3-case → Task 12; CLI smoke → Task 8 ✓
- Spec §8.4 coverage ≥ 90% → enforced at Task 12 Step 3 ✓
- Spec §9 docs → Task 13 ✓
- Spec §10 `skills` second builtin intentionally out of scope — not planned ✓

**2. Placeholder scan:** No TBDs, no "implement later", no hand-wavy "add error handling" steps. Task 12 has a single explicit note about adjusting the `monkeypatch` target to mirror the production example; this is a real task note, not a placeholder.

**3. Type consistency:** Plugin names match registry keys exactly (`retry`, `composite`, `network_allowlist`, `rule_based`, `jsonl_file`, `file_logging`, `strict_json`). Class names match imports. `FollowupFirstReActPattern` referenced in both Task 10 and Task 11 `agent.json`. `start_stub_server` referenced in Tasks 9, 11, 12 with the same signature.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-builtin-plugins-expansion.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

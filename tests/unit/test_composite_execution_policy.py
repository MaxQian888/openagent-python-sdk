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
    def __init__(self, tag: str = "allow"):
        super().__init__(config={}, capabilities=set())
        self._tag = tag

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        return PolicyDecision(allowed=True, reason="allow", metadata={"who": self._tag})


class _Deny(ExecutionPolicyPlugin):
    def __init__(self, tag: str = "deny"):
        super().__init__(config={}, capabilities=set())
        self._tag = tag

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        return PolicyDecision(allowed=False, reason=f"no:{self._tag}", metadata={"who": self._tag})


class _Raise(ExecutionPolicyPlugin):
    def __init__(self):
        super().__init__(config={}, capabilities=set())

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        raise RuntimeError("boom")


def _req() -> ToolExecutionRequest:
    return ToolExecutionRequest(tool_id="x", tool=object(), execution_spec=ToolExecutionSpec())


def _build(children: list, mode: str = "all") -> CompositeExecutionPolicy:
    """Build a CompositeExecutionPolicy and override its children list for test isolation.

    Uses a single throwaway real builtin ('filesystem' with empty config) at construction
    time so the loader path is exercised; then swaps in the scripted test children.
    """
    cp = CompositeExecutionPolicy(config={
        "policies": [{"type": "filesystem", "config": {}}],
        "mode": mode,
    })
    cp._children = children
    return cp


@pytest.mark.asyncio
async def test_all_mode_first_deny_wins():
    cp = _build([_Allow(), _Deny(tag="d1"), _Deny(tag="d2")], mode="all")
    decision = await cp.evaluate(_req())
    assert decision.allowed is False
    assert "d1" in decision.reason
    assert decision.metadata["decided_by"] == 1


@pytest.mark.asyncio
async def test_all_allow_passes():
    cp = _build([_Allow(), _Allow()])
    decision = await cp.evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["policy"] == "composite"
    assert len(decision.metadata["children"]) == 2


@pytest.mark.asyncio
async def test_any_mode_first_allow_wins():
    cp = _build([_Deny(tag="d"), _Allow()], mode="any")
    decision = await cp.evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["decided_by"] == 1


@pytest.mark.asyncio
async def test_empty_policies_allows():
    # Build with empty list by going through the constructor path.
    cp = CompositeExecutionPolicy(config={"policies": [], "mode": "all"})
    decision = await cp.evaluate(_req())
    assert decision.allowed is True
    assert decision.metadata["children"] == []


@pytest.mark.asyncio
async def test_child_exception_wrapped_as_deny():
    cp = _build([_Raise()])
    decision = await cp.evaluate(_req())
    assert decision.allowed is False
    assert "raised" in decision.reason
    assert decision.metadata["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_any_mode_all_deny_returns_last_reason():
    cp = _build([_Deny(tag="a"), _Deny(tag="b")], mode="any")
    decision = await cp.evaluate(_req())
    assert decision.allowed is False
    assert "b" in decision.reason


def test_registered_as_builtin():
    assert get_builtin_plugin_class("execution_policy", "composite") is CompositeExecutionPolicy

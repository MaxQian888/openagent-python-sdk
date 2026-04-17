from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from openagents.interfaces.followup import FollowupResolution
from examples.research_analyst.app.followup_pattern import FollowupFirstReActPattern


class _InnerReact:
    """Minimal stand-in for ReActPattern; records whether `execute` was invoked."""

    def __init__(self, out: str = "react-ran"):
        self.called = 0
        self._out = out
        self.context: Any = None

    async def execute(self) -> Any:
        self.called += 1
        return self._out

    async def react(self) -> dict[str, Any]:
        return {"type": "final", "content": "use execute"}


class _Resolver:
    def __init__(self, resolution: FollowupResolution | None):
        self._resolution = resolution

    async def resolve(self, *, context: Any) -> FollowupResolution | None:
        return self._resolution


def _ctx(resolver: _Resolver) -> Any:
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


@pytest.mark.asyncio
async def test_resolved_sets_state_marker():
    """When followup resolves, the pattern should note resolved_by in state so tests
    can verify the short-circuit without peering at the mock provider's call counter."""
    inner = _InnerReact()
    pattern = FollowupFirstReActPattern(config={}, inner=inner)
    ctx = _ctx(_Resolver(FollowupResolution(status="resolved", output="ok")))
    pattern.context = ctx
    await pattern.execute()
    assert ctx.state.get("resolved_by") == "followup_resolver"

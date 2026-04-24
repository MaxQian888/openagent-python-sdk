from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from openagents.interfaces.agent_router import DelegationDepthExceededError, HandoffSignal
from openagents.interfaces.runtime import RunResult, StopReason
from openagents.runtime.runtime import Runtime

_CONFIG = {
    "agents": [
        {
            "id": "orchestrator",
            "name": "Orchestrator",
            "memory": {"type": "buffer"},
            "pattern": {"type": "react"},
            "llm": {"provider": "mock"},
        },
        {
            "id": "specialist",
            "name": "Specialist",
            "memory": {"type": "buffer"},
            "pattern": {"type": "react"},
            "llm": {"provider": "mock"},
        },
    ],
    "multi_agent": {"enabled": True, "default_session_isolation": "isolated"},
}


def _make_child_result(output: str, run_id: str = "child-1") -> RunResult:
    return RunResult(run_id=run_id, final_output=output, stop_reason=StopReason.COMPLETED)


def _make_ctx(run_id="run-1", session_id="sess-1"):
    ctx = MagicMock()
    ctx.run_id = run_id
    ctx.session_id = session_id
    ctx.deps = None
    ctx.run_request = MagicMock(parent_run_id=None)
    return ctx


@pytest.mark.asyncio
async def test_delegate_returns_child_result():
    runtime = Runtime.from_dict(_CONFIG)
    router = runtime._runtime._agent_router
    assert router is not None

    child_result = _make_child_result("specialist done")
    router._run_fn = AsyncMock(return_value=child_result)
    ctx = _make_ctx()

    result = await router.delegate("specialist", "do specialist task", ctx)
    assert result.final_output == "specialist done"
    req = router._run_fn.call_args.kwargs["request"]
    assert req.agent_id == "specialist"
    assert req.parent_run_id == "run-1"
    assert req.session_id != "sess-1"  # isolated → new session


@pytest.mark.asyncio
async def test_transfer_raises_handoff_signal_with_child_result():
    runtime = Runtime.from_dict(_CONFIG)
    router = runtime._runtime._agent_router
    child_result = _make_child_result("transferred output", run_id="child-2")
    router._run_fn = AsyncMock(return_value=child_result)
    ctx = _make_ctx()

    with pytest.raises(HandoffSignal) as exc_info:
        await router.transfer("specialist", "escalate", ctx)
    assert exc_info.value.result.final_output == "transferred output"


@pytest.mark.asyncio
async def test_shared_isolation_passes_parent_session():
    runtime = Runtime.from_dict(_CONFIG)
    router = runtime._runtime._agent_router
    router._run_fn = AsyncMock(return_value=_make_child_result("x"))
    ctx = _make_ctx(session_id="shared-sess")

    await router.delegate("specialist", "hi", ctx, session_isolation="shared")
    req = router._run_fn.call_args.kwargs["request"]
    assert req.session_id == "shared-sess"


@pytest.mark.asyncio
async def test_forked_isolation_creates_distinct_session():
    runtime = Runtime.from_dict(_CONFIG)
    router = runtime._runtime._agent_router
    router._run_fn = AsyncMock(return_value=_make_child_result("x"))
    ctx = _make_ctx(session_id="parent-sess", run_id="parent-run")

    await router.delegate("specialist", "hi", ctx, session_isolation="forked")
    req = router._run_fn.call_args.kwargs["request"]
    assert "parent-sess" in req.session_id
    assert "parent-run" in req.session_id
    assert req.session_id != "parent-sess"


@pytest.mark.asyncio
async def test_delegation_depth_limit_enforced():
    cfg = dict(_CONFIG)
    cfg["multi_agent"] = {"enabled": True, "max_delegation_depth": 1}
    runtime = Runtime.from_dict(cfg)
    router = runtime._runtime._agent_router
    router._run_fn = AsyncMock()
    ctx = _make_ctx(run_id="deep-run")
    router._run_depths["deep-run"] = 2  # simulate already-deep chain

    with pytest.raises(DelegationDepthExceededError) as exc_info:
        await router.delegate("specialist", "hi", ctx)
    assert exc_info.value.depth == 2
    assert exc_info.value.limit == 1


@pytest.mark.asyncio
async def test_child_depth_recorded_for_grandchild_checks():
    runtime = Runtime.from_dict(_CONFIG)
    router = runtime._runtime._agent_router
    child_result = _make_child_result("done", run_id="child-run-abc")
    router._run_fn = AsyncMock(return_value=child_result)
    ctx = _make_ctx(run_id="root-run")

    await router.delegate("specialist", "go", ctx)
    assert router._run_depths.get("child-run-abc") == 1

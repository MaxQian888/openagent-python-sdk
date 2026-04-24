"""Shared scenario definitions for the multi_agent_support example.

What:
    Four scenario functions that both ``run_demo_mock.py`` and
    ``tests/integration/test_multi_agent_support_example.py`` call.
    Keeping them here as a single source of truth prevents the demo
    and the test from drifting.

Usage:
    ``refund = await run_refund_scenario(runtime, deps)`` etc. Each
    function returns either a structured result (scenarios 1, 2) or
    ``None`` (scenarios 3, 4, which assert exception behavior and
    return only on success).

Scenario map:
    1. ``run_refund_scenario``: transfer + nested shared delegate.
    2. ``run_tech_scenario``: transfer + two forked delegates.
    3. ``run_depth_scenario``: depth-limit enforcement.
    4. ``run_unknown_agent_scenario``: AgentNotFoundError.

Scenarios 1 and 2 run through the full runtime loop. Scenarios 3 and
4 invoke the synthetic tool directly against a hand-built
``RunContext`` — this is how the ``agent-router`` spec's own
scenarios are phrased ("WHEN a ctx has depth=3 ... THEN delegate
raises") and avoids having the runtime's ``except Exception`` wrap
the exception into a ``PatternError``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from openagents.interfaces.agent_router import (
    DELEGATION_DEPTH_KEY,
    AgentNotFoundError,
    DelegationDepthExceededError,
)
from openagents.interfaces.run_context import RunContext
from openagents.interfaces.runtime import RunRequest, StopReason
from openagents.runtime.runtime import Runtime

from .app.deps import SupportDeps, build_seeded_deps
from .app.plugins import DelegateToMissingTool, SelfDelegateLookupTool

# ---------------------------------------------------------------------------
# Scenario 1: refund flow (transfer + shared delegate)
# ---------------------------------------------------------------------------


async def run_refund_scenario(
    runtime: Runtime,
    deps: SupportDeps | None = None,
    *,
    session_id: str | None = None,
    customer_id: str = "cust-001",
) -> dict[str, Any]:
    """Concierge receives a refund request → transfers → specialist processes.

    Returns a dict with ``parent_result`` (the top-level ``RunResult``),
    ``tickets`` (the current ticket list snapshot), and ``trace`` (the
    accumulated delegation trace).
    """

    support_deps = deps or build_seeded_deps()
    sid = session_id or f"sess-support-refund-{uuid4().hex[:8]}"
    parent_result = await runtime.run_detailed(
        request=RunRequest(
            agent_id="concierge",
            session_id=sid,
            input_text=f"/tool route_to_refund {customer_id}",
            deps=support_deps,
        )
    )
    return {
        "parent_result": parent_result,
        "tickets": list(support_deps.ticket_store.list()),
        "trace": list(support_deps.trace),
        "deps": support_deps,
        "session_id": sid,
    }


# ---------------------------------------------------------------------------
# Scenario 2: tech flow (transfer + two forked delegates)
# ---------------------------------------------------------------------------


async def run_tech_scenario(
    runtime: Runtime,
    deps: SupportDeps | None = None,
    *,
    session_id: str | None = None,
    customer_id: str = "cust-002",
) -> dict[str, Any]:
    """Concierge → tech_support → two forked account_lookup branches → ticket."""

    support_deps = deps or build_seeded_deps()
    sid = session_id or f"sess-support-tech-{uuid4().hex[:8]}"
    parent_result = await runtime.run_detailed(
        request=RunRequest(
            agent_id="concierge",
            session_id=sid,
            input_text=f"/tool route_to_tech {customer_id}",
            deps=support_deps,
        )
    )
    return {
        "parent_result": parent_result,
        "tickets": list(support_deps.ticket_store.list()),
        "trace": list(support_deps.trace),
        "deps": support_deps,
        "session_id": sid,
    }


# ---------------------------------------------------------------------------
# Scenario 3: depth-limit enforcement
# ---------------------------------------------------------------------------


def _make_ctx_at_depth(
    runtime: Runtime,
    *,
    agent_id: str,
    depth: int,
    deps: SupportDeps | None = None,
    session_id: str = "sess-depth",
    run_id: str | None = None,
) -> RunContext[Any]:
    """Build a minimal RunContext for direct tool invocation.

    Used by scenarios 3 and 4 so the raw router exception propagates to
    the caller without being wrapped by ``DefaultRuntime.run()``.
    """

    req = RunRequest(
        agent_id=agent_id,
        session_id=session_id,
        input_text="",
        metadata={DELEGATION_DEPTH_KEY: depth} if depth > 0 else {},
    )
    return RunContext(
        agent_id=agent_id,
        session_id=session_id,
        run_id=run_id or f"run-{uuid4().hex[:8]}",
        input_text="",
        deps=deps or build_seeded_deps(),
        event_bus=runtime.event_bus,
        run_request=req,
        agent_router=runtime._runtime._agent_router,
    )


async def run_depth_scenario(runtime: Runtime) -> DelegationDepthExceededError:
    """Directly invoke ``SelfDelegateLookupTool`` at ``depth=max_delegation_depth``.

    The router's ``_check_depth`` raises ``DelegationDepthExceededError``
    before any child run is constructed, satisfying the ``agent-router``
    spec's "Depth limit enforced" scenario. Returns the caught
    exception so callers can assert on ``.depth`` and ``.limit``.
    """

    ctx = _make_ctx_at_depth(runtime, agent_id="account_lookup", depth=3)
    tool = SelfDelegateLookupTool()
    try:
        await tool.invoke({"query": "loop"}, ctx)
    except DelegationDepthExceededError as err:
        return err
    raise AssertionError("Expected DelegationDepthExceededError from SelfDelegateLookupTool at depth=3; none raised")


# ---------------------------------------------------------------------------
# Scenario 4: unknown-agent error path
# ---------------------------------------------------------------------------


async def run_unknown_agent_scenario(runtime: Runtime) -> AgentNotFoundError:
    """Directly invoke ``DelegateToMissingTool`` → expects ``AgentNotFoundError``."""

    ctx = _make_ctx_at_depth(runtime, agent_id="concierge", depth=0)
    tool = DelegateToMissingTool()
    try:
        await tool.invoke({"query": "anything"}, ctx)
    except AgentNotFoundError as err:
        return err
    raise AssertionError("Expected AgentNotFoundError from DelegateToMissingTool; none raised")


# ---------------------------------------------------------------------------
# Module-level smoke helpers
# ---------------------------------------------------------------------------


def assert_refund_outcome(result: dict[str, Any]) -> None:
    """Post-run assertions for scenario 1. Used by both the demo and the test."""

    parent = result["parent_result"]
    if parent.stop_reason != StopReason.COMPLETED:
        raise AssertionError(
            f"Refund scenario: expected stop_reason=COMPLETED, got {parent.stop_reason}. "
            f"error_details={parent.error_details}"
        )
    handoff = parent.metadata.get("handoff_from")
    if not handoff:
        raise AssertionError(f"Refund scenario: expected metadata['handoff_from'] to be set, got {parent.metadata!r}")
    tickets = result["tickets"]
    refund_tickets = [t for t in tickets if t.kind == "refund"]
    if len(refund_tickets) != 1:
        raise AssertionError(f"Refund scenario: expected exactly one refund ticket, got {len(refund_tickets)}")


def assert_tech_outcome(result: dict[str, Any]) -> None:
    """Post-run assertions for scenario 2."""

    parent = result["parent_result"]
    if parent.stop_reason != StopReason.COMPLETED:
        raise AssertionError(
            f"Tech scenario: expected stop_reason=COMPLETED, got {parent.stop_reason}. "
            f"error_details={parent.error_details}"
        )
    forked = [t for t in result["trace"] if t.isolation == "forked"]
    if len(forked) < 1:
        raise AssertionError(f"Tech scenario: expected ≥1 forked trace entry, got {len(forked)}")
    # The forked child session id MUST match the spec format "{parent}:fork:{run_id}".
    for entry in forked:
        if entry.child_session_id is None or ":fork:" not in entry.child_session_id:
            raise AssertionError(
                f"Tech scenario: forked trace entry has malformed child_session_id: "
                f"{entry.child_session_id!r} (expected '<parent>:fork:<run_id>')"
            )
    tech_tickets = [t for t in result["tickets"] if t.kind == "tech"]
    if len(tech_tickets) != 1:
        raise AssertionError(f"Tech scenario: expected exactly one tech ticket, got {len(tech_tickets)}")

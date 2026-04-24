"""ToolPlugin subclasses for the multi_agent_support example.

What:
    Three families of tools that together exercise the full
    ``agent-router`` spec surface:

    1. *Leaf lookup tools* — ``LookupCustomerTool`` / ``FindOrdersTool``:
       read ``ctx.deps.customer_store``. Assigned to ``account_lookup``.

    2. *Router-bound tools* — ``ConsultAccountLookupTool`` (delegate) and
       ``RouteToRefundTool`` / ``RouteToTechTool`` (transfer): call
       ``ctx.agent_router`` with a per-instance ``session_isolation``
       setting (``isolated`` / ``shared`` / ``forked``) so all three
       modes appear across the example. Each instance appends a
       ``DelegationTraceEntry`` to ``ctx.deps.trace`` before invoking
       the router.

    3. *Action tools* — ``ProcessRefundTool`` / ``TroubleshootTechTool``
       bundle the "consult + commit" steps that a single ReAct step can
       drive (ReAct short-circuits after one tool call). ``IssueRefundTool``
       / ``OpenTicketTool`` are the thin write-only siblings if the spec
       scenarios want a pure commit step.

    4. *Error-scenario synthetic tools* — ``SelfDelegateLookupTool``
       (scenario 3) and ``DelegateToMissingTool`` (scenario 4). Wired
       only by the scenario-specific config variants.

Usage:
    Registered via ``impl=`` entries in
    ``examples/multi_agent_support/agent_mock.json`` /
    ``agent_real.json``. Each ``ConsultAccountLookupTool`` instance gets
    its isolation via ``config={"isolation": "shared"}`` so one class
    covers all three callers.

Depends on:
    - ``multi_agent.enabled: true`` in ``AppConfig`` (for
      ``ctx.agent_router`` to be non-None).
    - ``SupportDeps`` attached to the top-level ``RunRequest.deps``; the
      router forwards ``ctx.deps`` to children when ``deps=None``.

Provider note (audit of ``openagents/llm/providers/mock.py`` during recon):
    The builtin ``MockLLMClient`` parses the prompt's ``INPUT:`` line and,
    when it starts with ``/tool <tool_id> <query>``, emits a tool_call
    with params ``{"query": query}``. ``ReActPattern`` short-circuits to
    ``final`` after any tool call (via ``_PENDING_TOOL_KEY`` in scratch),
    so each agent does exactly one tool invocation per run. The example
    is designed around this: to drive a child agent into a specific tool,
    the parent tool passes ``/tool <child_tool_id> <query>`` as the child
    ``input_text``. This also means per-agent scripted responses are not
    needed, so we do not ship a custom ``ScriptedMockProvider``.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin

from .deps import SupportDeps
from .protocol import (
    STATE_TICKET_DRAFT_KEY,
    DelegationTraceEntry,
    TicketDraft,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _require_deps(context: Any) -> SupportDeps:
    deps = getattr(context, "deps", None)
    if not isinstance(deps, SupportDeps):
        raise RuntimeError(
            "multi_agent_support tools require ctx.deps to be a SupportDeps. "
            "Attach one via RunRequest(deps=build_seeded_deps())."
        )
    return deps


def _require_router(context: Any) -> Any:
    router = getattr(context, "agent_router", None)
    if router is None:
        raise RuntimeError("agent_router is not configured. Set 'multi_agent.enabled: true' in AppConfig.")
    return router


def _record_trace(
    context: Any,
    *,
    via: Literal["delegate", "transfer"],
    child_agent: str,
    isolation: str,
    child_session_id: str | None = None,
    child_run_id: str | None = None,
) -> DelegationTraceEntry:
    deps = _require_deps(context)
    entry = DelegationTraceEntry(
        via=via,
        parent_agent=getattr(context, "agent_id", "?"),
        child_agent=child_agent,
        isolation=isolation,
        parent_session_id=getattr(context, "session_id", "?"),
        child_session_id=child_session_id,
        child_run_id=child_run_id,
    )
    deps.trace.append(entry)
    return entry


def _compute_child_session_id(ctx: Any, isolation: str) -> str | None:
    """Return the session id a delegate/transfer call will use, or None for isolated.

    Mirrors ``DefaultAgentRouter._resolve_session`` for ``shared`` and
    ``forked``; for ``isolated`` the router allocates a uuid-ish id internally
    and we record None so the trace entry does not claim a stale value.
    """

    if isolation == "shared":
        return getattr(ctx, "session_id", None)
    if isolation == "forked":
        return f"{getattr(ctx, 'session_id', '')}:fork:{getattr(ctx, 'run_id', '')}"
    return None


# ---------------------------------------------------------------------------
# Leaf lookup tools (assigned to account_lookup)
# ---------------------------------------------------------------------------


def _parse_customer_id(params: dict[str, Any]) -> str:
    raw = (params or {}).get("customer_id") or (params or {}).get("query") or ""
    customer_id = str(raw).strip()
    if not customer_id:
        raise ValueError("customer_id (or query) parameter is required")
    # If the payload still carries a /tool prefix (shouldn't, but guard), strip it.
    if customer_id.startswith("/tool "):
        customer_id = customer_id.split(maxsplit=2)[-1]
    return customer_id


class LookupCustomerTool(ToolPlugin):
    """Read-only customer profile lookup."""

    name = "lookup_customer"
    description = "Look up a customer profile by customer_id."
    durable_idempotent = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        deps = _require_deps(context)
        customer_id = _parse_customer_id(params)
        record = deps.customer_store.get(customer_id)
        return {"customer_id": customer_id, "record": record}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Target customer id."},
                "query": {"type": "string", "description": "Fallback: a raw customer_id string."},
            },
            "required": [],
        }


class FindOrdersTool(ToolPlugin):
    """Read-only recent-orders lookup."""

    name = "find_orders"
    description = "List recent orders for a customer_id."
    durable_idempotent = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        deps = _require_deps(context)
        customer_id = _parse_customer_id(params)
        return {
            "customer_id": customer_id,
            "orders": deps.customer_store.list_orders(customer_id),
        }

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": [],
        }


# ---------------------------------------------------------------------------
# Action tools (write to ticket store)
# ---------------------------------------------------------------------------


class IssueRefundTool(ToolPlugin):
    """Pure-commit refund tool: writes a refund TicketDraft to the store."""

    name = "issue_refund"
    description = "Persist a refund ticket for the given customer."
    durable_idempotent = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        deps = _require_deps(context)
        p = params or {}
        customer_id = str(p.get("customer_id") or "").strip() or "unknown"
        summary = str(p.get("summary") or "").strip() or "Refund requested by customer"
        resolution = str(p.get("resolution") or "").strip() or None
        draft = TicketDraft(kind="refund", customer_id=customer_id, summary=summary, resolution=resolution)
        ticket_id = deps.ticket_store.create(draft)
        if hasattr(context, "state") and isinstance(context.state, dict):
            context.state[STATE_TICKET_DRAFT_KEY] = draft.model_dump()
        return {"ticket_id": ticket_id, "ticket": draft.model_dump()}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "summary": {"type": "string"},
                "resolution": {"type": "string"},
            },
            "required": [],
        }


class OpenTicketTool(ToolPlugin):
    """Pure-commit tech tool: writes a tech TicketDraft."""

    name = "open_ticket"
    description = "Open a technical support ticket for the given customer."
    durable_idempotent = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        deps = _require_deps(context)
        p = params or {}
        customer_id = str(p.get("customer_id") or "").strip() or "unknown"
        summary = str(p.get("summary") or "").strip() or "Technical issue reported"
        resolution = str(p.get("resolution") or "").strip() or None
        draft = TicketDraft(kind="tech", customer_id=customer_id, summary=summary, resolution=resolution)
        ticket_id = deps.ticket_store.create(draft)
        if hasattr(context, "state") and isinstance(context.state, dict):
            context.state[STATE_TICKET_DRAFT_KEY] = draft.model_dump()
        return {"ticket_id": ticket_id, "ticket": draft.model_dump()}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "summary": {"type": "string"},
                "resolution": {"type": "string"},
            },
            "required": [],
        }


# ---------------------------------------------------------------------------
# Router-bound consult tool (delegate — shared/isolated/forked per instance)
# ---------------------------------------------------------------------------


class ConsultAccountLookupTool(ToolPlugin):
    """Delegate a lookup query to ``account_lookup`` with configurable isolation.

    Config:
        ``{"isolation": "shared" | "isolated" | "forked"}`` — default
        ``"isolated"``. Three separate tool entries (one per caller
        agent) use three different config values so the example exercises
        every mode mandated by the ``agent-router`` spec.
    """

    name = "consult_account_lookup"
    description = (
        "Consult the account_lookup specialist for a customer_id. Returns the specialist's summary as a string."
    )
    durable_idempotent = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        isolation = str(cfg.get("isolation", "isolated")).strip().lower()
        if isolation not in {"shared", "isolated", "forked"}:
            raise ValueError(f"Invalid isolation mode: {isolation!r}")
        self._isolation: Literal["shared", "isolated", "forked"] = isolation  # type: ignore[assignment]
        super().__init__(config=cfg, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        router = _require_router(context)
        query = str((params or {}).get("query", "")).strip() or "(empty query)"
        child_sid = _compute_child_session_id(context, self._isolation)
        result = await router.delegate(
            "account_lookup",
            query,
            context,
            session_isolation=self._isolation,
        )
        _record_trace(
            context,
            via="delegate",
            child_agent="account_lookup",
            isolation=self._isolation,
            child_session_id=child_sid,
            child_run_id=getattr(result, "run_id", None),
        )
        return {
            "child_run_id": getattr(result, "run_id", None),
            "child_session_id": child_sid,
            "isolation": self._isolation,
            "output": getattr(result, "final_output", None),
        }

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        }


# ---------------------------------------------------------------------------
# Router-bound transfer tools (handoff — always isolated child)
# ---------------------------------------------------------------------------


class _TransferTool(ToolPlugin):
    """Shared base for transfer tools. Each subclass sets ``_target`` and ``_child_input``."""

    _target: str = ""
    _child_input_prefix: str = ""
    durable_idempotent = True  # the side effect (child run) is observable but re-running is safe in the example

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        router = _require_router(context)
        query = str((params or {}).get("query", "")).strip() or "(empty query)"
        # Trace BEFORE transfer() raises HandoffSignal — otherwise the trace entry is lost.
        _record_trace(
            context,
            via="transfer",
            child_agent=self._target,
            isolation="isolated",
            child_session_id=None,
            child_run_id=None,
        )
        child_input = f"{self._child_input_prefix} {query}".strip() if self._child_input_prefix else query
        # transfer() always raises HandoffSignal; control does not return.
        await router.transfer(
            self._target,
            child_input,
            context,
            session_isolation="isolated",
        )
        return None  # pragma: no cover — unreachable after HandoffSignal

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        }


class RouteToRefundTool(_TransferTool):
    """Concierge → transfer to refund_specialist.

    Passes ``/tool process_refund <query>`` as the child's input so the
    refund specialist's ReAct step immediately dispatches to its
    one-shot refund orchestration tool.
    """

    name = "route_to_refund"
    description = "Hand the conversation to the refund specialist."
    _target = "refund_specialist"
    _child_input_prefix = "/tool process_refund"


class RouteToTechTool(_TransferTool):
    """Concierge → transfer to tech_support, priming its troubleshoot tool."""

    name = "route_to_tech"
    description = "Hand the conversation to the tech support specialist."
    _target = "tech_support"
    _child_input_prefix = "/tool troubleshoot_tech"


# ---------------------------------------------------------------------------
# Bundled-action tools (one ReAct step drives multi-step business logic)
# ---------------------------------------------------------------------------


class ProcessRefundTool(ToolPlugin):
    """Refund specialist's one-shot orchestration tool.

    Steps:
        1. Delegate account verification to ``account_lookup`` with
           ``session_isolation="shared"`` (the specialist shares the
           ongoing customer conversation).
        2. Issue a refund ticket via ``TicketStore.create``.

    Why bundled: ``ReActPattern`` short-circuits to final after one tool
    call, so a specialist doing "consult then commit" needs both steps
    in a single tool.
    """

    name = "process_refund"
    description = "Verify the customer via account_lookup and issue a refund ticket."
    durable_idempotent = False  # issues a ticket

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        deps = _require_deps(context)
        router = _require_router(context)
        query = str((params or {}).get("query", "")).strip() or "cust-001"
        customer_id = query.split()[0] if query else "cust-001"

        # Step 1: shared delegate — specialist sees the same session as the concierge did.
        child_sid = _compute_child_session_id(context, "shared")
        verify = await router.delegate(
            "account_lookup",
            customer_id,
            context,
            session_isolation="shared",
        )
        _record_trace(
            context,
            via="delegate",
            child_agent="account_lookup",
            isolation="shared",
            child_session_id=child_sid,
            child_run_id=getattr(verify, "run_id", None),
        )

        # Step 2: persist the refund ticket.
        record = deps.customer_store.get(customer_id)
        summary = (
            f"Refund request for {customer_id}"
            if record is None
            else f"Refund for {record.get('name', customer_id)} ({customer_id})"
        )
        draft = TicketDraft(
            kind="refund",
            customer_id=customer_id,
            summary=summary,
            resolution="approved",
        )
        ticket_id = deps.ticket_store.create(draft)
        if hasattr(context, "state") and isinstance(context.state, dict):
            context.state[STATE_TICKET_DRAFT_KEY] = draft.model_dump()

        return {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "verify_output": getattr(verify, "final_output", None),
            "ticket": draft.model_dump(),
        }

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        }


class TroubleshootTechTool(ToolPlugin):
    """Tech support's one-shot diagnostic tool.

    Steps:
        1. One ``session_isolation="forked"`` delegation to
           ``account_lookup`` (the primary diagnostic hypothesis) — the
           child sees a snapshot of the parent session at fork time and
           subsequent parent writes do not leak across.
        2. One ``session_isolation="isolated"`` lookup for a secondary
           hypothesis (demonstrates mixing modes inside one tool).
        3. Open a tech ticket with the combined findings.

    Why one fork (not two): ``DefaultAgentRouter._resolve_session``
    builds the forked child id as ``{parent_sid}:fork:{parent_run_id}``,
    so multiple forks from a single parent run would collide on the
    target session id. The spec's fork contract is fully exercised by a
    single forked delegation; the second hypothesis uses ``isolated``
    to keep the scenario medically realistic without tripping the
    collision.
    """

    name = "troubleshoot_tech"
    description = "Run a forked diagnostic + isolated fallback lookup and open a tech ticket."
    durable_idempotent = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        deps = _require_deps(context)
        router = _require_router(context)
        query = str((params or {}).get("query", "")).strip() or "cust-002"
        customer_id = query.split()[0] if query else "cust-002"

        findings: list[dict[str, Any]] = []
        for hypothesis, isolation in (
            ("network", "forked"),
            ("billing_cache", "isolated"),
        ):
            child_sid = _compute_child_session_id(context, isolation)
            branch = await router.delegate(
                "account_lookup",
                f"{customer_id} diag:{hypothesis}",
                context,
                session_isolation=isolation,
            )
            _record_trace(
                context,
                via="delegate",
                child_agent="account_lookup",
                isolation=isolation,
                child_session_id=child_sid,
                child_run_id=getattr(branch, "run_id", None),
            )
            findings.append(
                {
                    "hypothesis": hypothesis,
                    "isolation": isolation,
                    "child_run_id": getattr(branch, "run_id", None),
                    "child_session_id": child_sid,
                    "output": getattr(branch, "final_output", None),
                }
            )

        draft = TicketDraft(
            kind="tech",
            customer_id=customer_id,
            summary=f"Tech issue for {customer_id}",
            resolution=json.dumps([f["hypothesis"] for f in findings]),
        )
        ticket_id = deps.ticket_store.create(draft)
        if hasattr(context, "state") and isinstance(context.state, dict):
            context.state[STATE_TICKET_DRAFT_KEY] = draft.model_dump()

        return {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "findings": findings,
            "ticket": draft.model_dump(),
        }

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        }


# ---------------------------------------------------------------------------
# Synthetic error-scenario tools (wired only by scenario-specific configs)
# ---------------------------------------------------------------------------


class SelfDelegateLookupTool(ToolPlugin):
    """Scenario-3 tool: recurse via ``delegate(account_lookup, ...)`` until depth limit.

    Each invocation delegates back to ``account_lookup`` with a fresh
    ``/tool self_delegate_lookup ...`` input, so the child also calls
    this tool. Combined with ``max_delegation_depth=3``, the fourth
    call (parent depth 3) raises ``DelegationDepthExceededError``
    before any new child is constructed.
    """

    name = "self_delegate_lookup"
    description = "Self-recursive delegate used only by the depth-limit scenario."
    durable_idempotent = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        router = _require_router(context)
        # Each recursive step passes along the same /tool directive; this is
        # what primes the child ReAct to recurse.
        query = str((params or {}).get("query", "loop")).strip() or "loop"
        child_input = f"/tool self_delegate_lookup {query}-next"
        result = await router.delegate(
            "account_lookup",
            child_input,
            context,
            session_isolation="isolated",
        )
        _record_trace(
            context,
            via="delegate",
            child_agent="account_lookup",
            isolation="isolated",
            child_session_id=None,
            child_run_id=getattr(result, "run_id", None),
        )
        return {"child_run_id": getattr(result, "run_id", None)}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        }


class DelegateToMissingTool(ToolPlugin):
    """Scenario-4 tool: delegate to an agent id that is not in AppConfig.

    The router validates ``agent_id`` against ``Runtime._agent_exists``
    before any child run is constructed and raises
    ``AgentNotFoundError``.
    """

    name = "delegate_to_missing"
    description = "Synthetic tool that delegates to an unknown agent_id; raises AgentNotFoundError."
    durable_idempotent = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        router = _require_router(context)
        # The router raises AgentNotFoundError synchronously; no trace recorded.
        await router.delegate(
            "does_not_exist",
            str((params or {}).get("query", "")),
            context,
            session_isolation="isolated",
        )
        return None  # pragma: no cover — unreachable

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        }

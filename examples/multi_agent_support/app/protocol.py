"""Pydantic envelopes and state keys for the multi_agent_support example.

What:
    Models the app-defined middle protocol that rides on
    ``RunContext.state`` / ``RunContext.deps`` (never on kernel
    attributes). ``CustomerIntent`` is the concierge's classification
    output; ``TicketDraft`` is what action tools persist to
    ``TicketStore``; ``DelegationTraceEntry`` records every router call
    for post-run observability.

Usage:
    Imported by ``examples.multi_agent_support.app.plugins`` and by
    scenario / test modules that inspect deps after a run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STATE_INTENT_KEY = "intent"
STATE_TRACE_KEY = "trace"
STATE_TICKET_DRAFT_KEY = "ticket_draft"


class CustomerIntent(BaseModel):
    """The concierge's routing decision for an incoming user request."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["refund", "tech", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str


class TicketDraft(BaseModel):
    """A support ticket about to be (or already) persisted."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["refund", "tech"]
    customer_id: str
    summary: str
    resolution: str | None = None


class DelegationTraceEntry(BaseModel):
    """One entry in the cross-run delegation/transfer trace.

    Stored on ``SupportDeps.trace`` (not on ``ctx.state``) so tests /
    demos can inspect the full multi-agent flow after the top-level run
    completes.
    """

    model_config = ConfigDict(extra="forbid")

    via: Literal["delegate", "transfer"]
    parent_agent: str
    child_agent: str
    isolation: str
    parent_session_id: str
    child_session_id: str | None = None
    child_run_id: str | None = None

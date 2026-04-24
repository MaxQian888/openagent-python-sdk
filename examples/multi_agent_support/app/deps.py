"""Typed deps for the multi_agent_support example.

What:
    ``SupportDeps`` bundles the read-side (``CustomerStore``), the
    write-side (``TicketStore``), and the cross-run observability log
    (``trace: list[DelegationTraceEntry]``). A single ``SupportDeps``
    instance is attached to every parent ``RunRequest`` and inherited
    by children via ``router.delegate(..., deps=None)`` (the router
    falls back to ``ctx.deps`` when ``deps=None``).

Usage:
    ``deps = build_seeded_deps()`` — preloaded with two customers for
    the mock scenarios. Tests inspect ``deps.ticket_store.list()`` and
    ``deps.trace`` after a run completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .protocol import DelegationTraceEntry, TicketDraft


@dataclass
class CustomerStore:
    """Read-only customer and order lookup backed by in-memory dicts."""

    _customers: dict[str, dict[str, Any]] = field(default_factory=dict)
    _orders: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def seed(
        self,
        customers: dict[str, dict[str, Any]],
        orders: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._customers = dict(customers)
        self._orders = {cid: list(items) for cid, items in (orders or {}).items()}

    def get(self, customer_id: str) -> dict[str, Any] | None:
        record = self._customers.get(customer_id)
        return dict(record) if record is not None else None

    def list_orders(self, customer_id: str) -> list[dict[str, Any]]:
        return [dict(o) for o in self._orders.get(customer_id, [])]


@dataclass
class TicketStore:
    """Append-only ticket persistence keyed by generated ids."""

    _tickets: dict[str, TicketDraft] = field(default_factory=dict)

    def create(self, draft: TicketDraft) -> str:
        ticket_id = f"ticket-{uuid4().hex[:8]}"
        self._tickets[ticket_id] = draft
        return ticket_id

    def list(self) -> list[TicketDraft]:
        return list(self._tickets.values())

    def get(self, ticket_id: str) -> TicketDraft | None:
        return self._tickets.get(ticket_id)


@dataclass
class SupportDeps:
    """The typed deps bundle attached to every RunRequest in this example."""

    customer_store: CustomerStore
    ticket_store: TicketStore
    trace: list[DelegationTraceEntry] = field(default_factory=list)


def build_seeded_deps() -> SupportDeps:
    """Factory returning a fresh SupportDeps preloaded with two customers.

    ``cust-001`` has past orders (used by the refund flow).
    ``cust-002`` has no orders (used by the tech flow and the "customer
    lookup missing" branch).
    """

    store = CustomerStore()
    store.seed(
        customers={
            "cust-001": {"id": "cust-001", "name": "Alice", "tier": "gold", "email": "alice@example.com"},
            "cust-002": {"id": "cust-002", "name": "Bob", "tier": "silver", "email": "bob@example.com"},
        },
        orders={
            "cust-001": [
                {"order_id": "ord-1001", "amount_usd": 49.0, "product": "Pro Plan"},
                {"order_id": "ord-1002", "amount_usd": 12.0, "product": "Add-on Pack"},
            ],
        },
    )
    return SupportDeps(customer_store=store, ticket_store=TicketStore())

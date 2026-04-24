"""Unit tests for examples.multi_agent_support.app.deps."""

from __future__ import annotations

import pytest

from examples.multi_agent_support.app.deps import (
    CustomerStore,
    SupportDeps,
    TicketStore,
    build_seeded_deps,
)
from examples.multi_agent_support.app.protocol import TicketDraft


class TestCustomerStore:
    def test_get_hit_returns_copy(self) -> None:
        store = CustomerStore()
        store.seed({"c1": {"id": "c1", "name": "Alice"}})
        got = store.get("c1")
        assert got == {"id": "c1", "name": "Alice"}
        got["name"] = "Mallory"
        # The mutation MUST NOT leak back into the store.
        assert store.get("c1") == {"id": "c1", "name": "Alice"}

    def test_get_miss_returns_none(self) -> None:
        store = CustomerStore()
        store.seed({"c1": {"id": "c1"}})
        assert store.get("missing") is None

    def test_list_orders_for_seeded_customer(self) -> None:
        store = CustomerStore()
        store.seed(
            {"c1": {"id": "c1"}},
            orders={"c1": [{"order_id": "o1"}, {"order_id": "o2"}]},
        )
        orders = store.list_orders("c1")
        assert [o["order_id"] for o in orders] == ["o1", "o2"]

    def test_list_orders_for_customer_without_orders_returns_empty(self) -> None:
        store = CustomerStore()
        store.seed({"c1": {"id": "c1"}})
        assert store.list_orders("c1") == []

    def test_list_orders_returns_copy(self) -> None:
        store = CustomerStore()
        store.seed({"c1": {"id": "c1"}}, orders={"c1": [{"order_id": "o1"}]})
        orders = store.list_orders("c1")
        orders[0]["order_id"] = "mutated"
        assert store.list_orders("c1") == [{"order_id": "o1"}]


class TestTicketStore:
    def test_create_returns_unique_ids(self) -> None:
        store = TicketStore()
        a = store.create(TicketDraft(kind="refund", customer_id="c1", summary="x"))
        b = store.create(TicketDraft(kind="refund", customer_id="c1", summary="x"))
        assert a != b

    def test_list_reflects_writes(self) -> None:
        store = TicketStore()
        assert store.list() == []
        store.create(TicketDraft(kind="tech", customer_id="c2", summary="bug"))
        listed = store.list()
        assert len(listed) == 1
        assert listed[0].kind == "tech"

    def test_get_known_id_returns_draft(self) -> None:
        store = TicketStore()
        ticket_id = store.create(TicketDraft(kind="refund", customer_id="c1", summary="ok"))
        got = store.get(ticket_id)
        assert got is not None
        assert got.kind == "refund"

    def test_get_unknown_id_returns_none(self) -> None:
        store = TicketStore()
        assert store.get("nope") is None


class TestBuildSeededDeps:
    def test_returns_support_deps_with_two_customers(self) -> None:
        deps = build_seeded_deps()
        assert isinstance(deps, SupportDeps)
        assert deps.customer_store.get("cust-001") is not None
        assert deps.customer_store.get("cust-002") is not None
        assert deps.customer_store.get("cust-003") is None

    def test_cust_001_has_orders(self) -> None:
        deps = build_seeded_deps()
        orders = deps.customer_store.list_orders("cust-001")
        assert len(orders) == 2

    def test_cust_002_has_no_orders(self) -> None:
        deps = build_seeded_deps()
        assert deps.customer_store.list_orders("cust-002") == []

    def test_ticket_store_starts_empty(self) -> None:
        deps = build_seeded_deps()
        assert deps.ticket_store.list() == []

    def test_trace_starts_empty_list(self) -> None:
        deps = build_seeded_deps()
        assert deps.trace == []

    def test_is_idempotent_independent_stores(self) -> None:
        a = build_seeded_deps()
        b = build_seeded_deps()
        a.ticket_store.create(TicketDraft(kind="refund", customer_id="cust-001", summary="x"))
        assert len(a.ticket_store.list()) == 1
        # The second build MUST NOT see the write on the first.
        assert len(b.ticket_store.list()) == 0
        # And seed data is still present on both.
        assert a.customer_store.get("cust-001") is not None
        assert b.customer_store.get("cust-001") is not None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])

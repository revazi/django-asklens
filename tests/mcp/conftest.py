"""Shared fixtures for MCP adapter tests."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from tests.mcp._support import aware_datetime, valid_aggregate_plan
from tests.test_project.models import Customer, Order


@pytest.fixture(autouse=True)
def clear_default_registry() -> Iterator[None]:
    """Keep MCP adapter tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def user():
    """Return an authenticated user for request-like MCP contexts."""

    return get_user_model().objects.create_user(username="mcp-user", password="pw")


@pytest.fixture
def mcp_request(settings, user):
    """Return a request-like object with MCP-mapped permission strings."""

    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": lambda request: getattr(
            request,
            "asklens_permissions",
            (),
        ),
        "DUMMY_PLANS": {"Show orders by status": valid_aggregate_plan()},
    }
    return SimpleNamespace(user=user, asklens_permissions=frozenset())


@pytest.fixture
def registered_orders() -> None:
    """Register an order resource with a permission-gated sensitive field."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "customer.email": {
                "label": "Customer email",
                "sensitive": True,
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[Metric("order_count", op="count", field="id")],
    )


@pytest.fixture
def order_data() -> None:
    """Create deterministic order rows for MCP execution tests."""

    customer = Customer.objects.create(name="Alice", email="alice@example.com")
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at=aware_datetime(2026, 1, 5),
        total=Decimal("100.00"),
    )
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at=aware_datetime(2026, 1, 6),
        total=Decimal("50.00"),
    )
    Order.objects.create(
        customer=customer,
        status="pending",
        created_at=aware_datetime(2026, 1, 7),
        total=Decimal("75.00"),
    )

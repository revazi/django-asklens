"""Database routing preservation tests for the trusted execution facade."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import connections
from django.test.utils import CaptureQueriesContext

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import PublicAskLensError
from django_asklens.execution import execute_plan
from tests.test_project.models import Customer, Order

pytestmark = [
    pytest.mark.django_db(transaction=True, databases=["default", "asklens_read"]),
    pytest.mark.postgresql,
]


def _application_sql_queries(queries: list[dict[str, str]]) -> list[str]:
    """Return captured SQL statements that target application tables."""

    return [
        query["sql"]
        for query in queries
        if "test_project_order" in query["sql"].lower()
    ]


@pytest.fixture(autouse=True)
def disable_audit(settings) -> None:
    """Keep execution audit disabled to avoid audit-write query interference."""

    settings.DJANGO_ASKLENS = {"AUDIT_MODE": "disabled"}


@dataclass(frozen=True, slots=True)
class RequestUser:
    """Minimal authenticated user with deterministic permission strings."""

    permissions: frozenset[str]
    is_authenticated: bool = True

    def get_all_permissions(self) -> frozenset[str]:
        return self.permissions


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Minimal request-like object used by execution tests."""

    user: RequestUser
    visible_status: str = "paid"


def request_with(*permissions: str, visible_status: str = "paid") -> RequestContext:
    """Build a minimal request with deterministic permission values."""

    return RequestContext(
        user=RequestUser(frozenset(permissions)),
        visible_status=visible_status,
    )


def build_routing_registry() -> CatalogRegistry:
    """Return context-scoped registry using an explicit `.using('asklens_read')`."""

    registry = CatalogRegistry()
    registry.register(
        timezone="UTC",
        model=Order,
        name="orders_read",
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order ID",
            },
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
                "label": "Status",
            },
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
        requires_permission="shop.view_orders",
        scope_mode="context_scoped",
        scope_provider=lambda request: Order.objects.using("asklens_read").filter(
            status=request.visible_status
        ),
    )
    return registry


def build_invalid_routing_registry() -> CatalogRegistry:
    """Return context-scoped registry using an invalid application alias."""

    registry = CatalogRegistry()
    registry.register(
        timezone="UTC",
        model=Order,
        name="orders_invalid",
        fields={
            "id": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order ID",
            },
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
        requires_permission="shop.view_orders",
        scope_mode="context_scoped",
        scope_provider=lambda request: Order.objects.using("invalid_alias").all(),
    )
    return registry


@pytest.fixture
def sample_data(db) -> None:
    """Create order rows in shared DB aliases; asklens_read mirrors default."""

    customer = Customer.objects.create(name="alice", email="alice@example.com")
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        total=Decimal("100.00"),
    )
    Order.objects.create(
        customer=customer,
        status="pending",
        created_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
        total=Decimal("50.00"),
    )


def test_list_query_preserves_read_alias(sample_data) -> None:
    """A context-scoped scope queryset keeps its alias into execution."""

    plan = {
        "resource": "orders_read",
        "intent": "list",
        "select": ["id", "status"],
        "limit": 10,
    }

    with CaptureQueriesContext(connections["asklens_read"]) as captured_read:
        with CaptureQueriesContext(connections["default"]) as captured_default:
            result = execute_plan(
                plan,
                request=request_with("shop.view_orders", visible_status="paid"),
                registry=build_routing_registry(),
            )

    # One query should execute against application table(s) on asklens_read.
    assert _application_sql_queries(captured_read.captured_queries)
    # No application-data query should run on default despite the same test fixture.
    assert not _application_sql_queries(captured_default.captured_queries)

    assert result.row_count == 1
    assert result.rows[0]["status"] == "paid"


def test_aggregate_query_preserves_read_alias(sample_data) -> None:
    """Aggregate execution should also preserve the scope queryset alias."""

    plan = {
        "resource": "orders_read",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "limit": 10,
    }

    with CaptureQueriesContext(connections["asklens_read"]) as captured_read:
        with CaptureQueriesContext(connections["default"]) as captured_default:
            result = execute_plan(
                plan,
                request=request_with("shop.view_orders", visible_status="paid"),
                registry=build_routing_registry(),
            )

    # One application query should route through the requested alias.
    assert _application_sql_queries(captured_read.captured_queries)
    # No application-data query should fall back to default.
    assert not _application_sql_queries(captured_default.captured_queries)

    assert result.row_count == 1
    assert result.rows[0]["status"] == "paid"
    assert result.rows[0]["order_count"] == 1


def test_invalid_database_alias_fails_closed_without_fallback_to_default() -> None:
    """An invalid alias must fail closed and not run app-query on default."""

    with (
        CaptureQueriesContext(connections["asklens_read"]) as captured_read,
        CaptureQueriesContext(connections["default"]) as captured_default,
        pytest.raises(PublicAskLensError) as caught,
    ):
        execute_plan(
            {
                "resource": "orders_invalid",
                "intent": "list",
                "select": ["id"],
                "limit": 10,
            },
            request=request_with("shop.view_orders"),
            registry=build_invalid_routing_registry(),
        )

    assert caught.value.code == "asklens.execute.failed"
    # Fail-closed: no app query should run on either connection.
    assert not _application_sql_queries(captured_read.captured_queries)
    assert not _application_sql_queries(captured_default.captured_queries)

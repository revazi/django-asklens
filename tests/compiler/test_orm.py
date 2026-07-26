"""Tests for compiling validated QueryPlans to Django ORM queries."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.compiler.orm import _compile_prepared_query
from django_asklens.execution import execute_plan, run_query_plan
from django_asklens.execution.runner import (
    _build_execution_context,
    _prepare_query_plan,
)
from django_asklens.planning import PlanLimits, parse_and_validate_query_plan
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for deterministic fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


def month_start(year: int, month: int) -> datetime:
    """Return the UTC start of a month for date-trunc expectations."""

    return datetime(year, month, 1, 0, 0, tzinfo=UTC)


def execute_test_plan(plan, *, registry: CatalogRegistry):
    """Execute through the public facade with an anonymous request context."""

    return execute_plan(
        plan,
        request=SimpleNamespace(user=None),
        registry=registry,
    )


@pytest.fixture
def order_data() -> None:
    """Create deterministic Order fixtures."""

    alice = Customer.objects.create(name="Alice", email="alice@example.com")
    bob = Customer.objects.create(name="Bob", email="bob@example.com")

    Order.objects.create(
        customer=alice,
        status="paid",
        created_at=aware_datetime(2026, 1, 5),
        total=Decimal("100.00"),
    )
    Order.objects.create(
        customer=bob,
        status="paid",
        created_at=aware_datetime(2026, 1, 20),
        total=Decimal("50.00"),
    )
    Order.objects.create(
        customer=bob,
        status="pending",
        created_at=aware_datetime(2026, 2, 3),
        total=Decimal("75.00"),
    )
    Order.objects.create(
        customer=alice,
        status="failed",
        created_at=aware_datetime(2026, 2, 10),
        total=Decimal("25.00"),
    )


def build_registry(*, paid_only: bool = False) -> CatalogRegistry:
    """Return a registry configured for Order query tests."""

    def scope_provider(_request: object):
        if paid_only:
            return Order.objects.filter(status="paid")
        return Order.objects.all()

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
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
            "created_at": {
                "binding": "created_at",
                "type": "datetime",
                "nullable": False,
                "label": "Created date",
            },
            "customer.name": {
                "binding": "customer__name",
                "type": "string",
                "nullable": False,
                "label": "Customer name",
            },
            "total": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
                "label": "Order total",
                "metric": True,
            },
        },
        metrics=[
            Metric("order_count", op="count", field="id", label="Number of orders"),
            Metric("revenue", op="sum", field="total", label="Revenue"),
            Metric(
                "avg_order_value", op="avg", field="total", label="Average order value"
            ),
            Metric("min_order_total", op="min", field="total", label="Minimum order"),
            Metric("max_order_total", op="max", field="total", label="Maximum order"),
        ],
        scope_mode="context_scoped",
        scope_provider=scope_provider,
    )
    return registry


def validate_payload(payload: dict[str, Any], *, registry: CatalogRegistry):
    """Parse and validate a plan payload for compiler tests."""

    return parse_and_validate_query_plan(
        payload,
        registry=registry,
        limits=PlanLimits(max_rows=100, max_joins=2, max_metrics=5, max_group_by=3),
    )


def test_compile_list_query_returns_selected_public_keys(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "list",
            "filters": [{"field": "status", "op": "eq", "value": "paid"}],
            "select": ["customer.name", "status", "total"],
            "order_by": [{"field": "total", "direction": "desc"}],
            "limit": 10,
            "visualization": {"type": "table"},
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert [column.key for column in result.columns] == [
        "customer.name",
        "status",
        "total",
    ]
    assert result.rows == (
        {"customer.name": "Alice", "status": "paid", "total": Decimal("100.00")},
        {"customer.name": "Bob", "status": "paid", "total": Decimal("50.00")},
    )


def test_semantic_keys_bind_privately_across_query_positions(
    order_data: None,
) -> None:
    """Plans remain semantic across select, filter, group, metric, and ordering."""

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        scope_mode="global",
        default_date_field="placed_at",
        default_order=(("order.number", "asc"),),
        fields={
            "order.number": {
                "binding": "id",
                "type": "integer",
                "nullable": False,
                "label": "Order number",
            },
            "customer_contact": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "label": "Customer contact",
            },
            "lifecycle": {
                "binding": "status",
                "type": "string",
                "nullable": False,
                "label": "Lifecycle",
            },
            "placed_at": {
                "binding": "created_at",
                "type": "datetime",
                "nullable": False,
                "label": "Placed at",
            },
            "amount": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
                "label": "Amount",
                "metric": True,
            },
        },
        metrics=[Metric("revenue", op="sum", field="amount")],
    )

    list_result = execute_test_plan(
        {
            "resource": "orders",
            "intent": "list",
            "filters": [{"field": "lifecycle", "op": "eq", "value": "paid"}],
            "select": ["order.number", "customer_contact", "lifecycle"],
            "limit": 10,
        },
        registry=registry,
    )
    aggregate_result = execute_test_plan(
        {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "lifecycle"}],
            "metrics": [{"name": "revenue", "op": "sum", "field": "amount"}],
            "order_by": [{"metric": "revenue", "direction": "desc"}],
            "limit": 10,
        },
        registry=registry,
    )

    assert list_result.rows == (
        {
            "order.number": 1,
            "customer_contact": "alice@example.com",
            "lifecycle": "paid",
        },
        {
            "order.number": 2,
            "customer_contact": "bob@example.com",
            "lifecycle": "paid",
        },
    )
    assert aggregate_result.rows == (
        {"lifecycle": "paid", "revenue": Decimal("150")},
        {"lifecycle": "pending", "revenue": Decimal("75")},
        {"lifecycle": "failed", "revenue": Decimal("25")},
    )


def test_changing_private_binding_does_not_change_public_plan(
    order_data: None,
) -> None:
    """The same semantic plan executes after a server-owned binding change."""

    def registry_for(binding: str) -> CatalogRegistry:
        registry = CatalogRegistry()
        registry.register(
            model=Order,
            name="orders",
            scope_mode="global",
            fields={
                "display_value": {
                    "binding": binding,
                    "type": "string",
                    "nullable": False,
                }
            },
        )
        return registry

    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["display_value"],
        "order_by": [{"field": "display_value"}],
        "limit": 10,
    }

    status_result = execute_test_plan(plan, registry=registry_for("status"))
    customer_result = execute_test_plan(
        plan,
        registry=registry_for("customer__name"),
    )

    assert [column.key for column in status_result.columns] == ["display_value"]
    assert [column.key for column in customer_result.columns] == ["display_value"]
    assert {row["display_value"] for row in status_result.rows} == {
        "failed",
        "paid",
        "pending",
    }
    assert {row["display_value"] for row in customer_result.rows} == {
        "Alice",
        "Bob",
    }


def test_filters_cover_in_contains_date_range_and_relative_dates(
    order_data: None,
) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "list",
            "filters": [
                {"field": "status", "op": "in", "value": ["paid", "pending"]},
                {"field": "customer.name", "op": "icontains", "value": "bo"},
                {
                    "field": "created_at",
                    "op": "date_range",
                    "value": ["2026-01-01T00:00:00Z", "2026-02-28T23:59:59Z"],
                },
                {"field": "created_at", "op": "last_n_days", "value": 45},
            ],
            "select": ["customer.name", "status"],
            "order_by": [{"field": "status"}],
            "limit": 10,
            "visualization": {"type": "table"},
        },
        registry=registry,
    )

    with pytest.warns(DeprecationWarning, match="execute_plan"):
        result = run_query_plan(
            plan,
            registry=registry,
            request=SimpleNamespace(user=None),
            now=aware_datetime(2026, 3, 1),
        )

    assert result.rows == (
        {"customer.name": "Bob", "status": "paid"},
        {"customer.name": "Bob", "status": "pending"},
    )


def test_group_by_status_with_count_sum_and_order_by_metric(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [
                {"name": "order_count", "op": "count", "field": "id"},
                {"name": "revenue", "op": "sum", "field": "total"},
            ],
            "order_by": [{"metric": "revenue", "direction": "desc"}],
            "limit": 10,
            "visualization": {"type": "bar", "x": "status", "y": "revenue"},
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert [column.key for column in result.columns] == [
        "status",
        "order_count",
        "revenue",
    ]
    assert result.rows == (
        {"status": "paid", "order_count": 2, "revenue": Decimal("150")},
        {"status": "pending", "order_count": 1, "revenue": Decimal("75")},
        {"status": "failed", "order_count": 1, "revenue": Decimal("25")},
    )


def test_group_by_month_and_average_metric(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "created_at", "date_trunc": "month"}],
            "metrics": [{"name": "avg_order_value", "op": "avg", "field": "total"}],
            "order_by": [{"field": "created_at"}],
            "limit": 10,
            "visualization": {
                "type": "line",
                "x": "created_at",
                "y": "avg_order_value",
            },
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert result.rows == (
        {
            "created_at": month_start(2026, 1),
            "avg_order_value": Decimal("75"),
        },
        {
            "created_at": month_start(2026, 2),
            "avg_order_value": Decimal("50"),
        },
    )


def test_min_and_max_metrics(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "aggregate",
            "metrics": [
                {"name": "min_order_total", "op": "min", "field": "total"},
                {"name": "max_order_total", "op": "max", "field": "total"},
            ],
            "limit": 1,
            "visualization": {"type": "metric", "y": "max_order_total"},
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert result.rows == (
        {
            "min_order_total": Decimal("25"),
            "max_order_total": Decimal("100"),
        },
    )


def test_metric_query_without_group_by_returns_single_row(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "aggregate",
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "limit": 1,
            "visualization": {"type": "metric", "y": "order_count"},
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert result.rows == ({"order_count": 4},)


def test_limit_is_applied_to_result_rows(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "revenue", "op": "sum", "field": "total"}],
            "order_by": [{"metric": "revenue", "direction": "desc"}],
            "limit": 1,
            "visualization": {"type": "bar", "x": "status", "y": "revenue"},
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert result.row_count == 1
    assert result.rows == ({"status": "paid", "revenue": Decimal("150")},)


def test_compiler_starts_from_context_scope_provider(order_data: None) -> None:
    registry = build_registry(paid_only=True)
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "aggregate",
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "limit": 1,
            "visualization": {"type": "metric", "y": "order_count"},
        },
        registry=registry,
    )

    result = execute_test_plan(plan, registry=registry)

    assert result.rows == ({"order_count": 2},)


def test_compile_query_metadata_without_executing_result(order_data: None) -> None:
    registry = build_registry()
    plan = validate_payload(
        {
            "resource": "orders",
            "intent": "list",
            "select": ["id", "status"],
            "order_by": [{"field": "id"}],
            "limit": 2,
            "visualization": {"type": "table"},
        },
        registry=registry,
    )

    context = _build_execution_context(
        request=SimpleNamespace(user=None),
        registry=registry,
        now=None,
        require_request=False,
    )
    prepared = _prepare_query_plan(plan, context=context)
    compiled = _compile_prepared_query(prepared)

    assert [column.key for column in compiled.columns] == ["id", "status"]
    assert compiled.key_map == {
        "_asklens_select_0": "id",
        "_asklens_select_1": "status",
    }

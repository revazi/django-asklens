"""Golden evaluation cases for common MVP AskLens questions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.execution import run_query_plan
from django_asklens.llms import DummyProvider
from django_asklens.planning import PlanLimits
from django_asklens.planning.planner import plan_question
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for deterministic fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """A deterministic question, plan, and rendered-result expectation."""

    question: str
    plan: dict[str, Any]
    expected_intent: Literal["list", "aggregate"]
    expected_visualization_type: str
    expected_data: list[dict[str, Any]]


GOLDEN_CASES = (
    GoldenCase(
        question="Show orders by status as a bar chart",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "order_by": [{"metric": "order_count", "direction": "desc"}],
            "limit": 10,
            "visualization": {"type": "bar", "x": "status", "y": "order_count"},
        },
        expected_intent="aggregate",
        expected_visualization_type="bar",
        expected_data=[
            {"status": "paid", "order_count": 3},
            {"status": "pending", "order_count": 2},
            {"status": "failed", "order_count": 1},
        ],
    ),
    GoldenCase(
        question="How many orders were placed?",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
            "limit": 1,
            "visualization": {"type": "metric", "y": "order_count"},
        },
        expected_intent="aggregate",
        expected_visualization_type="metric",
        expected_data=[{"order_count": 6}],
    ),
    GoldenCase(
        question="Show revenue by month as a line chart",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "created_at", "date_trunc": "month"}],
            "metrics": [{"name": "revenue", "op": "sum", "field": "total"}],
            "order_by": [{"field": "created_at", "direction": "asc"}],
            "limit": 12,
            "visualization": {"type": "line", "x": "created_at", "y": "revenue"},
        },
        expected_intent="aggregate",
        expected_visualization_type="line",
        expected_data=[
            {"created_at": "2026-01-01T00:00:00+00:00", "revenue": 150.0},
            {"created_at": "2026-02-01T00:00:00+00:00", "revenue": 100.0},
            {"created_at": "2026-03-01T00:00:00+00:00", "revenue": 350.0},
        ],
    ),
    GoldenCase(
        question="List failed orders",
        plan={
            "resource": "orders",
            "intent": "list",
            "filters": [{"field": "status", "op": "eq", "value": "failed"}],
            "select": ["customer.name", "status", "total"],
            "limit": 10,
            "visualization": {"type": "table"},
        },
        expected_intent="list",
        expected_visualization_type="table",
        expected_data=[
            {"customer.name": "Bob", "status": "failed", "total": 200.0},
        ],
    ),
    GoldenCase(
        question="Show average order value by status",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"name": "avg_order_value", "op": "avg", "field": "total"}],
            "order_by": [{"metric": "avg_order_value", "direction": "desc"}],
            "limit": 10,
            "visualization": {
                "type": "bar",
                "x": "status",
                "y": "avg_order_value",
            },
        },
        expected_intent="aggregate",
        expected_visualization_type="bar",
        expected_data=[
            {"status": "failed", "avg_order_value": 200.0},
            {"status": "paid", "avg_order_value": 100.0},
            {"status": "pending", "avg_order_value": 50.0},
        ],
    ),
)


@pytest.fixture
def order_data() -> None:
    """Create deterministic data for golden cases."""

    alice = Customer.objects.create(name="Alice", email="alice@example.com")
    bob = Customer.objects.create(name="Bob", email="bob@example.com")

    Order.objects.bulk_create(
        [
            Order(
                customer=alice,
                status="paid",
                created_at=aware_datetime(2026, 1, 5),
                total=Decimal("100.00"),
            ),
            Order(
                customer=bob,
                status="paid",
                created_at=aware_datetime(2026, 1, 20),
                total=Decimal("50.00"),
            ),
            Order(
                customer=alice,
                status="paid",
                created_at=aware_datetime(2026, 3, 1),
                total=Decimal("150.00"),
            ),
            Order(
                customer=bob,
                status="pending",
                created_at=aware_datetime(2026, 2, 3),
                total=Decimal("75.00"),
            ),
            Order(
                customer=alice,
                status="pending",
                created_at=aware_datetime(2026, 2, 10),
                total=Decimal("25.00"),
            ),
            Order(
                customer=bob,
                status="failed",
                created_at=aware_datetime(2026, 3, 5),
                total=Decimal("200.00"),
            ),
        ]
    )


@pytest.fixture
def registry() -> CatalogRegistry:
    """Return a registry configured for evaluation cases."""

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "customer.name": {"label": "Customer name"},
            "customer.email": {"label": "Customer email", "sensitive": True},
            "total": {"label": "Order total", "metric": True},
        },
        metrics=[
            Metric("order_count", op="count", field="id", label="Number of orders"),
            Metric("revenue", op="sum", field="total", label="Revenue"),
            Metric(
                "avg_order_value", op="avg", field="total", label="Average order value"
            ),
        ],
    )
    return registry


@pytest.mark.parametrize(
    "case",
    GOLDEN_CASES,
    ids=[case.question for case in GOLDEN_CASES],
)
def test_golden_evaluation_case(
    case: GoldenCase,
    order_data: None,
    registry: CatalogRegistry,
) -> None:
    provider = DummyProvider(plans={case.question: case.plan})

    planner_result = plan_question(
        case.question,
        provider=provider,
        registry=registry,
        limits=PlanLimits(max_rows=100, max_joins=2, max_metrics=5, max_group_by=3),
    )
    result = run_query_plan(planner_result.plan, registry=registry)
    payload = result.to_dict()

    assert planner_result.question == case.question
    assert planner_result.plan.resource == "orders"
    assert planner_result.plan.intent == case.expected_intent
    assert payload["visualization"]["type"] == case.expected_visualization_type
    assert payload["data"] == case.expected_data


def test_golden_planner_prompt_excludes_sensitive_catalog_fields(
    registry: CatalogRegistry,
) -> None:
    provider = DummyProvider(plans={GOLDEN_CASES[0].question: GOLDEN_CASES[0].plan})

    planner_result = plan_question(
        GOLDEN_CASES[0].question,
        provider=provider,
        registry=registry,
    )

    assert planner_result.plan.group_by[0].field == "status"
    assert "customer.email" not in str(registry.to_dict())

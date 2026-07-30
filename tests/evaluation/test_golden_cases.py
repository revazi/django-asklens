"""Golden evaluation cases for common MVP AskLens questions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.execution import execute_plan
from django_asklens.llms import DummyProvider
from django_asklens.planning import PlanLimits
from django_asklens.planning.planner import plan_question
from django_asklens.results import normalize_presentation
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for deterministic fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """A deterministic question, plan, and serialized-result expectation."""

    question: str
    plan: dict[str, Any]
    presentation: dict[str, Any]
    expected_intent: Literal["list", "aggregate"]
    expected_presentation_kind: str
    expected_data: list[dict[str, Any]]


GOLDEN_CASES = (
    GoldenCase(
        question="Show orders by status as a bar chart",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"metric": "order_count"}],
            "order_by": [{"metric": "order_count", "direction": "desc"}],
            "limit": 10,
        },
        presentation={"kind": "bar", "x": "status", "y": "order_count"},
        expected_intent="aggregate",
        expected_presentation_kind="bar",
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
            "metrics": [{"metric": "order_count"}],
            "limit": 1,
        },
        presentation={"kind": "metric", "y": "order_count"},
        expected_intent="aggregate",
        expected_presentation_kind="metric",
        expected_data=[{"order_count": 6}],
    ),
    GoldenCase(
        question="Show revenue by month as a line chart",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "created_at", "date_trunc": "month"}],
            "metrics": [{"metric": "revenue"}],
            "order_by": [{"field": "created_at", "direction": "asc"}],
            "limit": 12,
        },
        presentation={"kind": "line", "x": "created_at", "y": "revenue"},
        expected_intent="aggregate",
        expected_presentation_kind="line",
        expected_data=[
            {"created_at": "2026-01-01T00:00:00+00:00", "revenue": "150"},
            {"created_at": "2026-02-01T00:00:00+00:00", "revenue": "100"},
            {"created_at": "2026-03-01T00:00:00+00:00", "revenue": "350"},
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
        },
        presentation={"kind": "table"},
        expected_intent="list",
        expected_presentation_kind="table",
        expected_data=[
            {"customer.name": "Bob", "status": "failed", "total": "200.00"},
        ],
    ),
    GoldenCase(
        question="Show average order value by status",
        plan={
            "resource": "orders",
            "intent": "aggregate",
            "group_by": [{"field": "status"}],
            "metrics": [{"metric": "avg_order_value"}],
            "order_by": [{"metric": "avg_order_value", "direction": "desc"}],
            "limit": 10,
        },
        presentation={"kind": "bar", "x": "status", "y": "avg_order_value"},
        expected_intent="aggregate",
        expected_presentation_kind="bar",
        expected_data=[
            {"status": "failed", "avg_order_value": "200"},
            {"status": "paid", "avg_order_value": "100"},
            {"status": "pending", "avg_order_value": "50"},
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
        timezone="UTC",
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
        scope_mode="global",
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
            "customer.email": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "label": "Customer email",
                "sensitive": True,
            },
            "total": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
                "label": "Order total",
            },
        },
        metrics=[
            Metric(
                "order_count",
                op="count",
                binding="id",
                result_type="integer",
                label="Number of orders",
            ),
            Metric(
                "revenue",
                op="sum",
                binding="total",
                result_type="decimal",
                label="Revenue",
            ),
            Metric(
                "avg_order_value",
                op="avg",
                binding="total",
                result_type="decimal",
                label="Average order value",
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
    provider = DummyProvider(
        plans={
            case.question: {
                "query_plan": case.plan,
                "presentation": case.presentation,
            }
        }
    )

    planner_result = plan_question(
        case.question,
        provider=provider,
        registry=registry,
        limits=PlanLimits(max_rows=100, max_joins=2, max_metrics=5, max_group_by=3),
    )
    result = execute_plan(
        planner_result.plan,
        request=SimpleNamespace(user=None),
        registry=registry,
    )
    payload = result.to_dict()
    presentation = normalize_presentation(
        planner_result.presentation.model_dump(mode="json", exclude_none=True)
        if planner_result.presentation is not None
        else None,
        columns=result.columns,
    )

    assert planner_result.question == case.question
    assert planner_result.plan.resource == "orders"
    assert planner_result.plan.intent == case.expected_intent
    assert "presentation" not in payload
    assert presentation["kind"] == case.expected_presentation_kind
    assert payload["data"] == case.expected_data


def test_golden_planner_prompt_excludes_sensitive_catalog_fields(
    registry: CatalogRegistry,
) -> None:
    provider = DummyProvider(
        plans={
            GOLDEN_CASES[0].question: {
                "query_plan": GOLDEN_CASES[0].plan,
                "presentation": GOLDEN_CASES[0].presentation,
            }
        }
    )

    planner_result = plan_question(
        GOLDEN_CASES[0].question,
        provider=provider,
        registry=registry,
    )

    assert planner_result.plan.group_by[0].field == "status"
    assert "customer.email" not in str(registry.to_dict())

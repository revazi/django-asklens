"""Structural QueryPlan budget boundary and zero-query tests."""

import json
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import (
    BudgetExceededError,
    PlanValidationError,
    PublicAskLensError,
)
from django_asklens.execution import execute_plan
from django_asklens.planning import PlanLimits, parse_and_validate_query_plan
from django_asklens.planning.validation import get_plan_limits
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db


def build_registry() -> CatalogRegistry:
    """Return a resource with enough fields, metrics, and edges for budgets."""

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        scope_mode="global",
        fields={
            "id": {"binding": "id", "type": "integer", "nullable": False},
            "status": {"binding": "status", "type": "string", "nullable": False},
            "created_at": {
                "binding": "created_at",
                "type": "datetime",
                "nullable": False,
            },
            "total": {"binding": "total", "type": "decimal", "nullable": False},
            "customer.name": {
                "binding": "customer__name",
                "type": "string",
                "nullable": False,
            },
            "customer.email": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
            },
            "account.name": {
                "binding": "account__name",
                "type": "string",
                "nullable": True,
            },
            "account.slug": {
                "binding": "account__slug",
                "type": "string",
                "nullable": True,
            },
            "account.accountmembership.role": {
                "binding": "account__accountmembership__role",
                "type": "string",
                "nullable": True,
            },
            "account.accountmembership.user.username": {
                "binding": "account__accountmembership__user__username",
                "type": "string",
                "nullable": True,
            },
        },
        metrics=[
            Metric("order_count", op="count", field="id"),
            Metric("revenue", op="sum", field="total"),
            Metric("max_total", op="max", field="total"),
        ],
    )
    return registry


def default_limit_values() -> dict[str, int]:
    """Return permissive limits for focused boundary tests."""

    return {
        "max_rows": 500,
        "max_joins": 3,
        "max_metrics": 5,
        "max_group_by": 3,
        "max_plan_bytes": 65_536,
        "max_filters": 20,
        "max_selected_fields": 25,
        "max_order_by": 5,
        "max_relationship_edges": 8,
        "max_in_values": 100,
        "max_filter_values": 200,
        "default_limit": 100,
    }


def limits_with(**updates: int) -> PlanLimits:
    """Return immutable limits with explicit focused overrides."""

    values = {**default_limit_values(), **updates}
    return PlanLimits(**values)


def list_plan(**updates: object) -> dict[str, Any]:
    """Return a valid list plan with optional updates."""

    payload: dict[str, Any] = {
        "resource": "orders",
        "intent": "list",
        "filters": [],
        "select": ["id", "status"],
        "order_by": [],
        "limit": 10,
    }
    payload.update(updates)
    return payload


def aggregate_plan(**updates: object) -> dict[str, Any]:
    """Return a valid aggregate plan with optional updates."""

    payload: dict[str, Any] = {
        "resource": "orders",
        "intent": "aggregate",
        "filters": [],
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "order_by": [],
        "limit": 10,
    }
    payload.update(updates)
    return payload


def validate(payload: dict[str, Any] | str, *, limits: PlanLimits) -> None:
    """Validate one payload against the budget registry."""

    parse_and_validate_query_plan(payload, registry=build_registry(), limits=limits)


def assert_count_boundary(
    payload: dict[str, Any],
    *,
    limit_name: str,
    count: int,
) -> None:
    """Prove one count is below, at, and above its configured boundary."""

    validate(payload, limits=limits_with(**{limit_name: count + 1}))
    validate(payload, limits=limits_with(**{limit_name: count}))
    with pytest.raises(BudgetExceededError):
        validate(payload, limits=limits_with(**{limit_name: count - 1}))


def test_plan_payload_bytes_below_at_and_above_boundary() -> None:
    """UTF-8 plan bytes are bounded before structural parsing."""

    raw_plan = json.dumps(list_plan(), separators=(",", ":"), ensure_ascii=False)
    byte_count = len(raw_plan.encode("utf-8"))

    validate(raw_plan, limits=limits_with(max_plan_bytes=byte_count + 1))
    validate(raw_plan, limits=limits_with(max_plan_bytes=byte_count))
    with pytest.raises(BudgetExceededError):
        validate(raw_plan, limits=limits_with(max_plan_bytes=byte_count - 1))


def test_filter_count_below_at_and_above_boundary() -> None:
    filters = [
        {"field": "status", "op": "neq", "value": "failed"},
        {"field": "id", "op": "gte", "value": 1},
    ]
    assert_count_boundary(
        list_plan(filters=filters), limit_name="max_filters", count=len(filters)
    )


def test_selected_field_count_below_at_and_above_boundary() -> None:
    select = ["id", "status", "created_at"]
    assert_count_boundary(
        list_plan(select=select),
        limit_name="max_selected_fields",
        count=len(select),
    )


def test_order_term_count_below_at_and_above_boundary() -> None:
    order_by = [
        {"field": "id", "direction": "asc"},
        {"field": "status", "direction": "desc"},
    ]
    assert_count_boundary(
        list_plan(order_by=order_by),
        limit_name="max_order_by",
        count=len(order_by),
    )


def test_group_term_count_below_at_and_above_boundary() -> None:
    group_by = [{"field": "status"}, {"field": "created_at"}]
    assert_count_boundary(
        aggregate_plan(group_by=group_by),
        limit_name="max_group_by",
        count=len(group_by),
    )


def test_metric_count_below_at_and_above_boundary() -> None:
    metrics = [
        {"name": "order_count", "op": "count", "field": "id"},
        {"name": "revenue", "op": "sum", "field": "total"},
    ]
    assert_count_boundary(
        aggregate_plan(metrics=metrics),
        limit_name="max_metrics",
        count=len(metrics),
    )


def test_in_value_count_below_at_and_above_boundary() -> None:
    values = ["paid", "pending", "failed"]
    assert_count_boundary(
        list_plan(filters=[{"field": "status", "op": "in", "value": values}]),
        limit_name="max_in_values",
        count=len(values),
    )


def test_total_filter_scalar_count_below_at_and_above_boundary() -> None:
    filters = [
        {"field": "status", "op": "in", "value": ["paid", "pending"]},
        {
            "field": "created_at",
            "op": "date_range",
            "value": ["2026-01-01", "2026-01-31"],
        },
        {"field": "id", "op": "gte", "value": 1},
    ]
    assert_count_boundary(
        list_plan(filters=filters),
        limit_name="max_filter_values",
        count=5,
    )


def test_result_limit_below_at_and_above_boundary() -> None:
    validate(list_plan(limit=1), limits=limits_with(max_rows=2))
    validate(list_plan(limit=2), limits=limits_with(max_rows=2))
    with pytest.raises(BudgetExceededError):
        validate(list_plan(limit=3), limits=limits_with(max_rows=2))


def test_relationship_hops_below_at_and_above_boundary() -> None:
    limits = limits_with(max_joins=2)

    validate(list_plan(select=["id"]), limits=limits)
    validate(list_plan(select=["account.accountmembership.role"]), limits=limits)
    with pytest.raises(BudgetExceededError):
        validate(
            list_plan(select=["account.accountmembership.user.username"]),
            limits=limits,
        )


def test_unique_relationship_edges_below_at_and_above_boundary() -> None:
    limits = limits_with(max_relationship_edges=2)

    validate(list_plan(select=["customer.email"]), limits=limits)
    validate(
        list_plan(select=["customer.email", "account.name"]),
        limits=limits,
    )
    with pytest.raises(BudgetExceededError):
        validate(
            list_plan(
                select=[
                    "customer.email",
                    "account.name",
                    "account.accountmembership.role",
                ]
            ),
            limits=limits,
        )


@pytest.mark.parametrize(
    ("payload", "settings_override"),
    [
        (
            list_plan(filters=[{"field": "id", "op": "gte", "value": 1}]),
            {"MAX_FILTERS": 0},
        ),
        (list_plan(select=["id", "status"]), {"MAX_SELECTED_FIELDS": 1}),
        (
            list_plan(
                order_by=[
                    {"field": "id", "direction": "asc"},
                    {"field": "status", "direction": "asc"},
                ]
            ),
            {"MAX_ORDER_BY": 1},
        ),
        (
            aggregate_plan(group_by=[{"field": "id"}, {"field": "status"}]),
            {"MAX_GROUP_BY": 1},
        ),
        (
            aggregate_plan(
                metrics=[
                    {"name": "order_count", "op": "count", "field": "id"},
                    {"name": "revenue", "op": "sum", "field": "total"},
                ]
            ),
            {"MAX_METRICS": 1},
        ),
        (
            list_plan(
                filters=[{"field": "status", "op": "in", "value": ["paid", "pending"]}]
            ),
            {"MAX_IN_VALUES": 1},
        ),
        (
            list_plan(
                filters=[{"field": "status", "op": "in", "value": ["paid", "pending"]}]
            ),
            {"MAX_FILTER_VALUES": 1},
        ),
        (list_plan(select=["customer.email"]), {"MAX_JOINS": 0}),
        (
            list_plan(select=["customer.email", "account.name"]),
            {"MAX_RELATIONSHIP_EDGES": 1},
        ),
        (list_plan(limit=2), {"MAX_ROWS": 1, "DEFAULT_LIMIT": 1}),
    ],
    ids=[
        "filters",
        "selected-fields",
        "order-terms",
        "group-terms",
        "metrics",
        "in-values",
        "filter-values",
        "relationship-hops",
        "relationship-edges",
        "result-rows",
    ],
)
def test_above_budget_execution_rejects_with_zero_sql(
    payload: dict[str, Any],
    settings_override: dict[str, int],
    settings,
    django_assert_num_queries,
) -> None:
    """Every over-budget plan rejects before scope or application-data SQL."""

    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        **settings_override,
    }

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="execution limit") as caught,
    ):
        execute_plan(
            payload, request=SimpleNamespace(user=None), registry=build_registry()
        )

    assert caught.value.code == "asklens.budget.exceeded"


def test_above_payload_byte_budget_execution_rejects_with_zero_sql(
    settings,
    django_assert_num_queries,
) -> None:
    """Oversized raw JSON rejects through the facade before parsing or SQL."""

    raw_plan = json.dumps(list_plan())
    settings.DJANGO_ASKLENS = {
        "AUDIT_MODE": "disabled",
        "MAX_PLAN_BYTES": len(raw_plan.encode("utf-8")) - 1,
    }

    with (
        django_assert_num_queries(0),
        pytest.raises(PublicAskLensError, match="execution limit") as caught,
    ):
        execute_plan(
            raw_plan, request=SimpleNamespace(user=None), registry=build_registry()
        )

    assert caught.value.code == "asklens.budget.exceeded"


@pytest.mark.parametrize(
    "payload",
    [
        list_plan(select=["id", "id"]),
        list_plan(
            filters=[
                {"field": "status", "op": "eq", "value": "paid"},
                {"field": "status", "op": "eq", "value": "paid"},
            ]
        ),
        aggregate_plan(group_by=[{"field": "status"}, {"field": "status"}]),
        list_plan(
            order_by=[
                {"field": "id", "direction": "asc"},
                {"field": "id", "direction": "desc"},
            ]
        ),
        list_plan(filters=[{"field": "status", "op": "in", "value": ["paid", "paid"]}]),
    ],
    ids=["select", "filter", "group", "order", "in-value"],
)
def test_meaningless_duplicates_are_rejected(payload: dict[str, Any]) -> None:
    """Repeated structural references count but never add ambiguous behavior."""

    with pytest.raises(PlanValidationError, match="Duplicate"):
        validate(payload, limits=limits_with())


def test_omitted_limit_uses_current_configured_default() -> None:
    """Default result limit is a current implementation setting, not a token."""

    payload = list_plan()
    payload.pop("limit")

    plan = parse_and_validate_query_plan(
        payload,
        registry=build_registry(),
        limits=limits_with(default_limit=7),
    )

    assert plan.limit == 7


def test_default_limit_is_safely_capped_by_max_rows() -> None:
    """A legacy MAX_ROWS-only override cannot create an invalid default plan."""

    limits = get_plan_limits({"MAX_ROWS": 5, "DEFAULT_LIMIT": 10})

    assert limits.max_rows == 5
    assert limits.default_limit == 5


def test_plan_limits_are_immutable_and_complete() -> None:
    """The internal limit shape includes every accepted structural dimension."""

    limits = limits_with()

    assert asdict(limits) == default_limit_values()

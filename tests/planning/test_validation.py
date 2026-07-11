"""Tests for QueryPlan semantic validation against the catalog."""

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.exceptions import (
    PermissionDeniedError,
    PlanValidationError,
    UnknownFieldError,
    UnknownMetricError,
    UnknownResourceError,
)
from django_asklens.planning import (
    PlanLimits,
    parse_and_validate_query_plan,
    parse_query_plan,
    validate_query_plan,
)
from tests.planning.test_schemas import valid_aggregate_plan_payload
from tests.test_project.models import BillingLine, Order


def build_registry() -> CatalogRegistry:
    """Return a catalog registry with one Order resource."""

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
            "customer.email": {
                "label": "Customer email",
                "sensitive": True,
                "requires_permission": "shop.view_pii",
            },
            "total": {
                "label": "Order total",
                "metric": True,
                "requires_permission": "shop.view_financials",
            },
            "internal_notes": {"label": "Internal notes", "llm_visible": False},
            "customer.name": {"label": "Customer name", "filter_only": True},
        },
        metrics=[
            Metric("order_count", op="count", field="id", label="Number of orders"),
            Metric("revenue", op="sum", field="total", label="Revenue"),
            Metric("email_count", op="count", field="customer.email"),
        ],
    )
    return registry


def parse_valid_plan(**updates: object):
    """Return a parsed valid plan with optional payload updates."""

    payload = valid_aggregate_plan_payload()
    payload.update(updates)
    return parse_query_plan(payload)


def build_billing_registry() -> CatalogRegistry:
    """Return a registry with a choice-backed billing status field."""

    registry = CatalogRegistry()
    registry.register(
        model=BillingLine,
        name="billing_lines",
        label="Billing lines",
        fields={
            "billing_document.status": {"label": "Billing status"},
            "product_name": {"label": "Product"},
            "total_amount_cents": {"label": "Total amount in cents"},
        },
        metrics=[
            Metric(
                "gross_revenue",
                op="sum",
                field="total_amount_cents",
                label="Gross revenue",
            )
        ],
    )
    return registry


def valid_billing_revenue_payload(**updates: object) -> dict[str, object]:
    """Return a valid billing aggregate payload with optional updates."""

    payload: dict[str, object] = {
        "resource": "billing_lines",
        "intent": "aggregate",
        "filters": [],
        "group_by": [{"field": "product_name"}],
        "metrics": [
            {"name": "gross_revenue", "op": "sum", "field": "total_amount_cents"}
        ],
        "order_by": [{"metric": "gross_revenue", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "product_name", "y": "gross_revenue"},
    }
    payload.update(updates)
    return payload


def test_valid_query_plan_validates_against_catalog() -> None:
    plan = parse_valid_plan(resource="Orders")

    validated = validate_query_plan(plan, registry=build_registry())

    assert validated.resource == "orders"


def test_parse_and_validate_query_plan_combines_untrusted_payload_pipeline() -> None:
    payload = valid_aggregate_plan_payload()
    payload["resource"] = "Orders"

    validated = parse_and_validate_query_plan(payload, registry=build_registry())

    assert validated.resource == "orders"


def test_choice_filter_labels_are_canonicalized_to_stored_values() -> None:
    """Choice labels from providers should match stored Django choice values."""

    validated = parse_and_validate_query_plan(
        valid_billing_revenue_payload(
            filters=[{"field": "billing_document.status", "op": "eq", "value": "Paid"}],
        ),
        registry=build_billing_registry(),
    )

    [filter_spec] = validated.filters
    assert filter_spec.value == "PAID"


def test_choice_filter_value_case_and_in_lists_are_canonicalized() -> None:
    """Choice values should accept common provider case/label variants."""

    validated = parse_and_validate_query_plan(
        valid_billing_revenue_payload(
            filters=[
                {
                    "field": "billing_document.status",
                    "op": "in",
                    "value": ["paid", "Past due"],
                }
            ],
        ),
        registry=build_billing_registry(),
    )

    [filter_spec] = validated.filters
    assert filter_spec.value == ["PAID", "PAST_DUE"]


def test_unknown_resource_fails() -> None:
    plan = parse_valid_plan(resource="payments")

    with pytest.raises(UnknownResourceError, match="payments"):
        validate_query_plan(plan, registry=build_registry())


def test_resource_permission_fails_without_matching_permission() -> None:
    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        fields={"id": {"label": "Order ID"}, "status": {"label": "Status"}},
        metrics=[Metric("order_count", op="count", field="id")],
        requires_permission="shop.view_orders",
    )
    plan = parse_valid_plan(
        filters=[],
        group_by=[{"field": "status"}],
        metrics=[{"name": "order_count", "op": "count", "field": "id"}],
        visualization={"type": "bar", "x": "status", "y": "order_count"},
    )

    with pytest.raises(PermissionDeniedError, match="shop.view_orders"):
        validate_query_plan(plan, registry=registry)

    validate_query_plan(
        plan,
        registry=registry,
        permissions={"facility:1:shop.view_orders"},
    )


def test_unknown_field_fails() -> None:
    plan = parse_valid_plan(filters=[{"field": "missing", "op": "eq", "value": 1}])

    with pytest.raises(UnknownFieldError, match="missing"):
        validate_query_plan(plan, registry=build_registry())


def test_raw_sql_like_field_name_fails_as_unknown_field() -> None:
    plan = parse_valid_plan(
        select=("id; DROP TABLE orders",),
        intent="list",
        filters=[],
        group_by=[],
        metrics=[],
        order_by=[],
        visualization={"type": "table"},
    )

    with pytest.raises(UnknownFieldError, match="DROP TABLE"):
        validate_query_plan(plan, registry=build_registry())


def test_unknown_metric_fails() -> None:
    plan = parse_valid_plan(metrics=[{"name": "profit", "op": "sum", "field": "total"}])

    with pytest.raises(UnknownMetricError, match="profit"):
        validate_query_plan(plan, registry=build_registry())


def test_metric_plan_must_match_registered_metric() -> None:
    plan = parse_valid_plan(
        metrics=[{"name": "revenue", "op": "avg", "field": "total"}]
    )

    with pytest.raises(PlanValidationError, match="does not match"):
        validate_query_plan(plan, registry=build_registry())


def test_sensitive_field_fails_without_explicit_permission() -> None:
    plan = parse_valid_plan(
        filters=[{"field": "customer.email", "op": "icontains", "value": "a"}]
    )

    with pytest.raises(PermissionDeniedError, match="sensitive"):
        validate_query_plan(plan, registry=build_registry())

    validate_query_plan(
        plan,
        registry=build_registry(),
        permissions={"shop.view_pii"},
    )


def test_permission_gated_metric_field_fails_without_permission() -> None:
    plan = parse_valid_plan(
        metrics=[{"name": "revenue", "op": "sum", "field": "total"}],
        order_by=[{"metric": "revenue", "direction": "desc"}],
        visualization={"type": "bar", "x": "status", "y": "revenue"},
    )

    with pytest.raises(PermissionDeniedError, match="shop.view_financials"):
        validate_query_plan(plan, registry=build_registry())

    validate_query_plan(
        plan,
        registry=build_registry(),
        permissions={"shop.view_financials"},
    )
    validate_query_plan(
        plan,
        registry=build_registry(),
        permissions={"facility:1:shop.view_financials"},
    )


def test_hidden_field_fails_unless_explicitly_allowed() -> None:
    plan = parse_valid_plan(
        select=("internal_notes",),
        intent="list",
        filters=[],
        group_by=[],
        metrics=[],
        order_by=[],
        visualization={"type": "table"},
    )

    with pytest.raises(PermissionDeniedError, match="hidden"):
        validate_query_plan(plan, registry=build_registry())

    validate_query_plan(plan, registry=build_registry(), allow_hidden_fields=True)


def test_filter_only_field_cannot_be_selected() -> None:
    plan = parse_valid_plan(
        select=("customer.name",),
        intent="list",
        filters=[],
        group_by=[],
        metrics=[],
        order_by=[],
        visualization={"type": "table"},
    )

    with pytest.raises(PlanValidationError, match="only be used in filters"):
        validate_query_plan(plan, registry=build_registry())


def test_limit_above_settings_max_fails() -> None:
    plan = parse_valid_plan(limit=51)

    with pytest.raises(PlanValidationError, match="MAX_ROWS"):
        validate_query_plan(plan, registry=build_registry())


def test_join_depth_above_limit_fails() -> None:
    plan = parse_valid_plan(
        filters=[{"field": "customer.email", "op": "icontains", "value": "a"}]
    )

    with pytest.raises(PlanValidationError, match="MAX_JOINS"):
        validate_query_plan(
            plan,
            registry=build_registry(),
            limits=PlanLimits(max_rows=100, max_joins=0, max_metrics=5, max_group_by=3),
            allow_sensitive_fields=True,
        )


def test_too_many_metrics_and_groupings_fail() -> None:
    plan = parse_valid_plan(
        group_by=[{"field": "status"}, {"field": "created_at", "date_trunc": "month"}],
        metrics=[
            {"name": "order_count", "op": "count", "field": "id"},
            {"name": "revenue", "op": "sum", "field": "total"},
        ],
        visualization={"type": "bar", "x": "status", "y": "order_count"},
    )

    with pytest.raises(PlanValidationError, match="metrics"):
        validate_query_plan(
            plan,
            registry=build_registry(),
            limits=PlanLimits(max_rows=100, max_joins=2, max_metrics=1, max_group_by=3),
        )

    with pytest.raises(PlanValidationError, match="group_by"):
        validate_query_plan(
            plan,
            registry=build_registry(),
            limits=PlanLimits(max_rows=100, max_joins=2, max_metrics=5, max_group_by=1),
        )


def test_date_trunc_requires_date_field() -> None:
    plan = parse_valid_plan(group_by=[{"field": "status", "date_trunc": "month"}])

    with pytest.raises(PlanValidationError, match="date/datetime"):
        validate_query_plan(plan, registry=build_registry())


def test_intent_specific_shape_is_validated() -> None:
    aggregate_without_metrics = parse_valid_plan(metrics=[])

    with pytest.raises(PlanValidationError, match="at least one metric"):
        validate_query_plan(aggregate_without_metrics, registry=build_registry())

    aggregate_with_select = parse_valid_plan(select=["id"])

    with pytest.raises(PlanValidationError, match="must not include select"):
        validate_query_plan(aggregate_with_select, registry=build_registry())

    list_with_metric = parse_valid_plan(intent="list", select=["id"])

    with pytest.raises(PlanValidationError, match="must not request metrics"):
        validate_query_plan(list_with_metric, registry=build_registry())


def test_order_by_must_reference_selected_or_metric_result() -> None:
    list_plan = parse_valid_plan(
        intent="list",
        select=["id"],
        filters=[],
        group_by=[],
        metrics=[],
        order_by=[{"field": "status"}],
        visualization={"type": "table"},
    )

    with pytest.raises(PlanValidationError, match="selected or grouped"):
        validate_query_plan(list_plan, registry=build_registry())

    aggregate_plan = parse_valid_plan(order_by=[{"metric": "revenue"}])

    with pytest.raises(PlanValidationError, match="requested in metrics"):
        validate_query_plan(aggregate_plan, registry=build_registry())


def test_visualization_refs_must_exist_in_result_keys() -> None:
    plan = parse_valid_plan(
        visualization={"type": "bar", "x": "missing", "y": "order_count"}
    )

    with pytest.raises(PlanValidationError, match="Visualization x"):
        validate_query_plan(plan, registry=build_registry())

    metric_plan = parse_valid_plan(visualization={"type": "metric", "y": "status"})

    with pytest.raises(PlanValidationError, match="Metric visualization"):
        validate_query_plan(metric_plan, registry=build_registry())


def test_table_visualization_axes_are_ignored() -> None:
    plan = parse_valid_plan(
        visualization={"type": "table", "x": "status", "y": "order_count"}
    )

    validated = validate_query_plan(plan, registry=build_registry())

    assert validated.visualization.x is None
    assert validated.visualization.y is None


def test_single_metric_visualization_y_is_inferred() -> None:
    plan = parse_valid_plan(visualization={"type": "metric"})

    validated = validate_query_plan(plan, registry=build_registry())

    assert validated.visualization.y == "order_count"


def test_metric_visualization_without_y_still_fails_when_ambiguous() -> None:
    plan = parse_valid_plan(
        metrics=[
            {"name": "order_count", "op": "count", "field": "id"},
            {"name": "revenue", "op": "sum", "field": "total"},
        ],
        visualization={"type": "metric"},
    )

    with pytest.raises(PlanValidationError, match="Metric visualization"):
        validate_query_plan(
            plan,
            registry=build_registry(),
            permissions={"shop.view_financials"},
        )


def test_date_trunc_visualization_alias_is_canonicalized() -> None:
    """Providers often invent date bucket aliases; normalize safe exact aliases."""

    plan = parse_valid_plan(
        group_by=[{"field": "created_at", "date_trunc": "month"}],
        visualization={"type": "line", "x": "created_at_month", "y": "order_count"},
    )

    validated = validate_query_plan(plan, registry=build_registry())

    assert validated.visualization.x == "created_at"


def test_date_trunc_visualization_alias_must_match_grouping() -> None:
    """Only aliases for the actual date-truncated group_by field are accepted."""

    plan = parse_valid_plan(
        group_by=[{"field": "created_at", "date_trunc": "month"}],
        visualization={"type": "line", "x": "paid_at_month", "y": "order_count"},
    )

    with pytest.raises(PlanValidationError, match="Visualization x"):
        validate_query_plan(plan, registry=build_registry())

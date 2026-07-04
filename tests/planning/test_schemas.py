"""Tests for QueryPlan schema parsing."""

import pytest

from django_asklens.exceptions import PlanValidationError
from django_asklens.planning import (
    SUPPORTED_FILTER_OPERATORS,
    SUPPORTED_VISUALIZATION_TYPES,
    QueryPlan,
    get_query_plan_json_schema,
    parse_query_plan,
)


def valid_aggregate_plan_payload() -> dict[str, object]:
    """Return a minimal valid aggregate plan payload."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "filters": [{"field": "created_at", "op": "last_n_days", "value": 30}],
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "select": [],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 50,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def test_supported_constants_and_json_schema_are_available() -> None:
    schema = get_query_plan_json_schema()

    assert "last_n_days" in SUPPORTED_FILTER_OPERATORS
    assert "bar" in SUPPORTED_VISUALIZATION_TYPES
    assert schema["title"] == "QueryPlan"
    assert "resource" in schema["properties"]


def test_valid_query_plan_parses_to_immutable_typed_model() -> None:
    plan = parse_query_plan(valid_aggregate_plan_payload())

    assert isinstance(plan, QueryPlan)
    assert plan.resource == "orders"
    assert plan.intent == "aggregate"
    assert plan.filters[0].op == "last_n_days"
    assert plan.visualization.type == "bar"

    with pytest.raises(TypeError):
        plan.filters[0] = plan.filters[0]


def test_invalid_json_fails_safely() -> None:
    with pytest.raises(PlanValidationError, match="valid JSON"):
        parse_query_plan("{")


def test_raw_sql_payload_extra_key_fails_closed() -> None:
    payload = valid_aggregate_plan_payload()
    payload["raw_sql"] = "select * from orders"

    with pytest.raises(PlanValidationError, match="raw_sql"):
        parse_query_plan(payload)


def test_mutation_intent_fails_schema_validation() -> None:
    payload = valid_aggregate_plan_payload()
    payload["intent"] = "delete"

    with pytest.raises(PlanValidationError, match="intent"):
        parse_query_plan(payload)


def test_unsupported_filter_operator_fails_schema_validation() -> None:
    payload = valid_aggregate_plan_payload()
    payload["filters"] = [{"field": "status", "op": "regex", "value": ".*"}]

    with pytest.raises(PlanValidationError, match="filters"):
        parse_query_plan(payload)


def test_filter_operator_values_are_strictly_validated() -> None:
    payload = valid_aggregate_plan_payload()
    payload["filters"] = [{"field": "status", "op": "in", "value": "paid"}]

    with pytest.raises(PlanValidationError, match="non-empty list"):
        parse_query_plan(payload)

    payload["filters"] = [{"field": "created_at", "op": "last_n_days", "value": 0}]

    with pytest.raises(PlanValidationError, match="positive integer"):
        parse_query_plan(payload)

    payload["filters"] = [{"field": "status", "op": "eq", "value": ["paid"]}]

    with pytest.raises(PlanValidationError, match="scalar"):
        parse_query_plan(payload)

    payload["filters"] = [
        {"field": "created_at", "op": "date_range", "value": ["2026-01-01", None]}
    ]

    with pytest.raises(PlanValidationError, match="non-empty string"):
        parse_query_plan(payload)


def test_visualization_axes_are_strict_for_type() -> None:
    payload = valid_aggregate_plan_payload()
    payload["visualization"] = {"type": "table", "x": "status"}

    with pytest.raises(PlanValidationError, match="must not define"):
        parse_query_plan(payload)

    payload["visualization"] = {"type": "metric", "x": "status", "y": "order_count"}

    with pytest.raises(PlanValidationError, match="must not define x"):
        parse_query_plan(payload)

"""Tests for QueryPlan schema parsing."""

import pytest

from django_asklens.exceptions import PlanValidationError
from django_asklens.planning import (
    SUPPORTED_FILTER_OPERATORS,
    SUPPORTED_PRESENTATION_KINDS,
    PresentationSpec,
    QueryPlan,
    get_query_plan_json_schema,
    parse_presentation,
    parse_query_plan,
)


def valid_aggregate_plan_payload() -> dict[str, object]:
    """Return a minimal valid aggregate plan payload."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "filters": [{"field": "created_at", "op": "last_n_days", "value": 30}],
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "select": [],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 50,
    }


def test_supported_constants_and_json_schema_are_available() -> None:
    schema = get_query_plan_json_schema()

    assert "last_n_days" in SUPPORTED_FILTER_OPERATORS
    assert "bar" in SUPPORTED_PRESENTATION_KINDS
    assert schema["title"] == "QueryPlan"
    assert "resource" in schema["properties"]
    filter_schema = schema["$defs"]["FilterSpec"]
    assert set(filter_schema["required"]) == {"field", "op", "value"}
    assert "null" not in str(filter_schema["properties"]["value"])


def test_valid_query_plan_parses_to_immutable_typed_model() -> None:
    plan = parse_query_plan(valid_aggregate_plan_payload())

    assert isinstance(plan, QueryPlan)
    assert plan.resource == "orders"
    assert plan.intent == "aggregate"
    assert plan.filters[0].op == "last_n_days"
    assert "visualization" not in QueryPlan.model_fields

    with pytest.raises(TypeError):
        plan.filters[0] = plan.filters[0]


@pytest.mark.parametrize("invalid_limit", [True, 10.0, "10"])
def test_query_plan_limit_requires_a_json_integer(invalid_limit: object) -> None:
    payload = valid_aggregate_plan_payload()
    payload["limit"] = invalid_limit

    with pytest.raises(PlanValidationError, match="limit"):
        parse_query_plan(payload)


def test_metric_requests_contain_only_the_registered_semantic_name() -> None:
    schema = get_query_plan_json_schema()
    metric_schema = schema["$defs"]["MetricSpec"]

    assert metric_schema["required"] == ["metric"]
    assert set(metric_schema["properties"]) == {"metric"}

    payload = valid_aggregate_plan_payload()
    payload["metrics"] = [
        {
            "metric": "order_count",
            "op": "count",
            "field": "id",
            "distinct": True,
        }
    ]
    with pytest.raises(PlanValidationError, match="metrics"):
        parse_query_plan(payload)


def test_invalid_json_fails_safely() -> None:
    with pytest.raises(PlanValidationError, match="valid JSON"):
        parse_query_plan("{")


def test_invalid_utf8_bytes_fail_with_typed_parse_error() -> None:
    """Malformed byte payloads never leak a raw UnicodeDecodeError."""

    with pytest.raises(PlanValidationError, match="valid UTF-8 JSON"):
        parse_query_plan(b"\xff")


def test_raw_sql_payload_extra_key_fails_closed() -> None:
    payload = valid_aggregate_plan_payload()
    payload["raw_sql"] = "select * from orders"

    with pytest.raises(PlanValidationError, match="raw_sql"):
        parse_query_plan(payload)


def test_client_cannot_choose_resource_timezone() -> None:
    payload = valid_aggregate_plan_payload()
    payload["timezone"] = "America/New_York"

    with pytest.raises(PlanValidationError, match="timezone"):
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
    payload["filters"] = [{"field": "status", "op": "eq"}]

    with pytest.raises(PlanValidationError, match="value"):
        parse_query_plan(payload)

    payload["filters"] = [{"field": "status", "op": "in", "value": "paid"}]

    with pytest.raises(PlanValidationError, match="non-empty list"):
        parse_query_plan(payload)

    payload["filters"] = [{"field": "created_at", "op": "last_n_days", "value": 0}]

    with pytest.raises(PlanValidationError, match="positive integer"):
        parse_query_plan(payload)

    payload["filters"] = [{"field": "status", "op": "eq", "value": ["paid"]}]

    with pytest.raises(PlanValidationError, match="scalar"):
        parse_query_plan(payload)

    for operator in ("eq", "neq"):
        payload["filters"] = [{"field": "status", "op": operator, "value": None}]
        with pytest.raises(PlanValidationError, match="filters"):
            parse_query_plan(payload)

    payload["filters"] = [
        {"field": "created_at", "op": "date_range", "value": ["2026-01-01", None]}
    ]

    with pytest.raises(PlanValidationError, match="filters"):
        parse_query_plan(payload)


def test_legacy_visualization_is_rejected_with_migration_pointer() -> None:
    payload = valid_aggregate_plan_payload()
    payload["visualization"] = {"type": "bar", "x": "status", "y": "order_count"}

    with pytest.raises(PlanValidationError, match="separate presentation") as caught:
        parse_query_plan(payload)

    assert caught.value.pointer == "/visualization"


def test_presentation_is_separate_and_strict() -> None:
    presentation = parse_presentation(
        {"kind": "bar", "x": "status", "y": "order_count"}
    )

    assert isinstance(presentation, PresentationSpec)
    assert presentation.kind == "bar"
    assert presentation.x == "status"

    with pytest.raises(PlanValidationError, match="must not define axes") as caught:
        parse_presentation({"kind": "table", "x": "status"})

    assert caught.value.pointer == "/presentation"

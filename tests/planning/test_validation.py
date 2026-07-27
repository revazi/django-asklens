"""Tests for QueryPlan semantic validation against the catalog."""

from uuid import UUID

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
from tests.test_project.models import (
    BillingLine,
    CanonicalValueFixture,
    Facility,
    Order,
)


def build_registry() -> CatalogRegistry:
    """Return a catalog registry with one Order resource."""

    registry = CatalogRegistry()
    registry.register(
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
            "customer.email": {
                "binding": "customer__email",
                "type": "string",
                "nullable": False,
                "label": "Customer email",
                "sensitive": True,
                "requires_permission": "shop.view_pii",
            },
            "total": {
                "binding": "total",
                "type": "decimal",
                "nullable": False,
                "label": "Order total",
                "requires_permission": "shop.view_financials",
            },
            "internal_notes": {
                "binding": "internal_notes",
                "type": "string",
                "nullable": False,
                "label": "Internal notes",
                "llm_visible": False,
            },
            "customer.name": {
                "binding": "customer__name",
                "type": "string",
                "nullable": False,
                "label": "Customer name",
                "filter_only": True,
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
                requires_permission="shop.view_financials",
            ),
            Metric(
                "email_count",
                op="count",
                binding="customer__email",
                result_type="integer",
                requires_permission="shop.view_pii",
            ),
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
        scope_mode="global",
        fields={
            "billing_document.status": {
                "binding": "billing_document__status",
                "type": "enum",
                "nullable": False,
                "label": "Billing status",
                "enum": {
                    "type": "string",
                    "values": [
                        {
                            "value": "PAID",
                            "label": "Paid",
                            "aliases": ["Paid", "paid"],
                        },
                        {
                            "value": "PAST_DUE",
                            "label": "Past due",
                            "aliases": ["Past due", "past_due"],
                        },
                    ],
                },
            },
            "product_name": {
                "binding": "product_name",
                "type": "string",
                "nullable": False,
                "label": "Product",
            },
            "total_amount_cents": {
                "binding": "total_amount_cents",
                "type": "integer",
                "nullable": False,
                "label": "Total amount in cents",
            },
        },
        metrics=[
            Metric(
                "gross_revenue",
                op="sum",
                binding="total_amount_cents",
                result_type="integer",
                label="Gross revenue",
            )
        ],
    )
    return registry


def build_canonical_registry() -> CatalogRegistry:
    """Return one resource covering every canonical field type."""

    registry = CatalogRegistry()
    registry.register(
        model=CanonicalValueFixture,
        name="canonical_values",
        scope_mode="global",
        fields={
            "text": {
                "binding": "text_value",
                "type": "string",
                "nullable": False,
            },
            "flag": {
                "binding": "boolean_value",
                "type": "boolean",
                "nullable": False,
            },
            "count": {
                "binding": "integer_value",
                "type": "integer",
                "nullable": False,
            },
            "amount": {
                "binding": "decimal_value",
                "type": "decimal",
                "nullable": False,
            },
            "ratio": {
                "binding": "float_value",
                "type": "float",
                "nullable": False,
            },
            "day": {
                "binding": "date_value",
                "type": "date",
                "nullable": False,
            },
            "instant": {
                "binding": "datetime_value",
                "type": "datetime",
                "nullable": False,
            },
            "clock": {
                "binding": "time_value",
                "type": "time",
                "nullable": False,
            },
            "identifier": {
                "binding": "uuid_value",
                "type": "uuid",
                "nullable": False,
            },
            "state": {
                "binding": "enum_text_value",
                "type": "enum",
                "nullable": False,
                "enum": {
                    "type": "string",
                    "values": [
                        {
                            "value": "draft",
                            "label": "Draft",
                            "aliases": ["DRAFT", "pending"],
                        },
                        {
                            "value": "active",
                            "label": "Active",
                            "aliases": ["ACTIVE"],
                        },
                    ],
                },
            },
            "state_code": {
                "binding": "enum_integer_value",
                "type": "enum",
                "nullable": False,
                "enum": {
                    "type": "integer",
                    "values": [
                        {"value": 1, "label": "Draft", "aliases": ["draft"]},
                        {"value": 2, "label": "Active", "aliases": ["current"]},
                    ],
                },
            },
        },
    )
    return registry


def canonical_list_payload(*, field: str, op: str, value: object) -> dict[str, object]:
    """Return a list plan with one canonical-value filter."""

    return {
        "resource": "canonical_values",
        "intent": "list",
        "filters": [{"field": field, "op": op, "value": value}],
        "select": [field],
        "limit": 10,
    }


def valid_billing_revenue_payload(**updates: object) -> dict[str, object]:
    """Return a valid billing aggregate payload with optional updates."""

    payload: dict[str, object] = {
        "resource": "billing_lines",
        "intent": "aggregate",
        "filters": [],
        "group_by": [{"field": "product_name"}],
        "metrics": [{"metric": "gross_revenue"}],
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


CANONICAL_OPERATOR_MATRIX = {
    "text": {"eq", "neq", "contains", "icontains", "in", "isnull"},
    "flag": {"eq", "neq", "in", "isnull"},
    "count": {"eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"},
    "amount": {"eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"},
    "ratio": {"eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"},
    "day": {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "isnull",
        "date_range",
        "last_n_days",
        "last_n_months",
    },
    "instant": {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "isnull",
        "date_range",
        "last_n_days",
        "last_n_months",
    },
    "clock": {"eq", "neq", "gt", "gte", "lt", "lte", "in", "isnull"},
    "identifier": {"eq", "neq", "in", "isnull"},
    "state": {"eq", "neq", "in", "isnull"},
    "state_code": {"eq", "neq", "in", "isnull"},
}
ALL_FILTER_OPERATORS = {
    "eq",
    "neq",
    "contains",
    "icontains",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "isnull",
    "date_range",
    "last_n_days",
    "last_n_months",
}
CANONICAL_SAMPLES = {
    "text": "alpha",
    "flag": True,
    "count": 2,
    "amount": "12.3400",
    "ratio": 1.5,
    "day": "2026-01-15",
    "instant": "2026-01-15T12:00:00Z",
    "clock": "12:30:00",
    "identifier": "9D4D8F5A-9E2B-4AA7-92A7-75C74DA6F648",
    "state": "draft",
    "state_code": 1,
}


def operator_value(field: str, operator: str) -> object:
    """Return a structurally valid test value for one field/operator pair."""

    if operator == "isnull":
        return False
    if operator in {"contains", "icontains"}:
        return "alpha"
    if operator == "in":
        return [CANONICAL_SAMPLES[field]]
    if operator == "date_range":
        if field == "day":
            return ["2026-01-01", "2026-01-31"]
        return ["2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"]
    if operator in {"last_n_days", "last_n_months"}:
        return 2
    return CANONICAL_SAMPLES[field]


@pytest.mark.parametrize(
    ("field", "operator", "is_supported"),
    [
        (field, operator, operator in supported)
        for field, supported in CANONICAL_OPERATOR_MATRIX.items()
        for operator in sorted(ALL_FILTER_OPERATORS)
    ],
)
def test_canonical_operator_matrix_is_enforced(
    field: str,
    operator: str,
    is_supported: bool,
) -> None:
    """Every retained operator has an explicit canonical field-type policy."""

    payload = canonical_list_payload(
        field=field,
        op=operator,
        value=operator_value(field, operator),
    )
    if is_supported:
        parse_and_validate_query_plan(payload, registry=build_canonical_registry())
        return

    with pytest.raises(PlanValidationError, match="is not supported for canonical"):
        parse_and_validate_query_plan(payload, registry=build_canonical_registry())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("text", 1, "must be a string"),
        ("flag", 1, "must be a boolean"),
        ("count", True, "must be an integer"),
        ("count", 1.5, "must be an integer"),
        ("amount", 1.25, "must be a decimal string"),
        ("amount", "NaN", "finite decimal string"),
        ("ratio", "1.25", "must be a JSON number"),
        ("ratio", float("inf"), "finite JSON number"),
        ("ratio", 10**1000, "finite JSON number"),
        ("identifier", "not-a-uuid", "valid UUID string"),
        ("state", "missing", "registered enum value or alias"),
        ("state_code", "2", "registered enum value or alias"),
    ],
)
def test_canonical_filter_values_reject_wrong_or_unsafe_types(
    field: str,
    value: object,
    message: str,
) -> None:
    """Django coercion must not define public filter value semantics."""

    with pytest.raises(PlanValidationError, match=message):
        parse_and_validate_query_plan(
            canonical_list_payload(field=field, op="eq", value=value),
            registry=build_canonical_registry(),
        )


def test_canonical_filter_values_normalize_float_uuid_and_enum_aliases() -> None:
    """Safe aliases normalize without changing the public field or operation."""

    identifier = "9D4D8F5A-9E2B-4AA7-92A7-75C74DA6F648"
    validated_float = parse_and_validate_query_plan(
        canonical_list_payload(field="ratio", op="eq", value=1),
        registry=build_canonical_registry(),
    )
    validated_uuid = parse_and_validate_query_plan(
        canonical_list_payload(field="identifier", op="eq", value=identifier),
        registry=build_canonical_registry(),
    )
    validated_enum = parse_and_validate_query_plan(
        canonical_list_payload(field="state", op="in", value=["pending", "ACTIVE"]),
        registry=build_canonical_registry(),
    )
    validated_integer_enum = parse_and_validate_query_plan(
        canonical_list_payload(field="state_code", op="eq", value="current"),
        registry=build_canonical_registry(),
    )

    assert validated_float.filters[0].value == 1.0
    assert validated_uuid.filters[0].value == str(UUID(identifier))
    assert validated_enum.filters[0].value == ["draft", "active"]
    assert validated_integer_enum.filters[0].value == 2


def test_enum_alias_normalization_cannot_create_duplicate_in_values() -> None:
    """Alias normalization cannot bypass the existing structural value budget."""

    with pytest.raises(PlanValidationError, match="Duplicate in filter value"):
        parse_and_validate_query_plan(
            canonical_list_payload(
                field="state",
                op="in",
                value=["draft", "pending"],
            ),
            registry=build_canonical_registry(),
        )


def test_django_choices_are_not_automatic_enum_aliases() -> None:
    """Choice labels remain ordinary strings unless an enum is registered."""

    registry = CatalogRegistry()
    registry.register(
        model=BillingLine,
        name="billing_lines",
        scope_mode="global",
        fields={
            "status": {
                "binding": "billing_document__status",
                "type": "string",
                "nullable": False,
            }
        },
    )

    validated = parse_and_validate_query_plan(
        {
            "resource": "billing_lines",
            "intent": "list",
            "filters": [{"field": "status", "op": "eq", "value": "Paid"}],
            "select": ["status"],
        },
        registry=registry,
    )

    assert validated.filters[0].value == "Paid"


def test_unknown_resource_fails() -> None:
    plan = parse_valid_plan(resource="payments")

    with pytest.raises(UnknownResourceError, match="payments"):
        validate_query_plan(plan, registry=build_registry())


def test_resource_permission_fails_without_matching_permission() -> None:
    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
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
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
        requires_permission="shop.view_orders",
    )
    plan = parse_valid_plan(
        filters=[],
        group_by=[{"field": "status"}],
        metrics=[{"metric": "order_count"}],
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
    plan = parse_valid_plan(metrics=[{"metric": "profit"}])

    with pytest.raises(UnknownMetricError, match="profit"):
        validate_query_plan(plan, registry=build_registry())


def test_metric_plan_cannot_redefine_registered_metric() -> None:
    payload = valid_aggregate_plan_payload()
    payload["metrics"] = [{"metric": "revenue", "op": "avg", "field": "total"}]

    with pytest.raises(PlanValidationError, match="metrics"):
        parse_query_plan(payload)


def build_facility_fanout_registry() -> CatalogRegistry:
    """Return metrics over two independent reverse relationship paths."""

    registry = CatalogRegistry()
    registry.register(
        model=Facility,
        name="facilities",
        scope_mode="global",
        fields={
            "name": {
                "binding": "name",
                "type": "string",
                "nullable": False,
            },
            "member.gender": {
                "binding": "members__gender",
                "type": "string",
                "nullable": True,
            },
        },
        metrics=[
            Metric(
                "member_count",
                op="count",
                binding="members__member_id",
                result_type="integer",
                cardinality_policy="count_rows",
            ),
            Metric(
                "staff_count",
                op="count",
                binding="staff_assignments__id",
                result_type="integer",
                cardinality_policy="count_rows",
            ),
            Metric(
                "facility_count",
                op="count",
                binding="id",
                result_type="integer",
            ),
        ],
    )
    return registry


def test_aggregate_rejects_independent_to_many_metric_paths() -> None:
    plan = parse_query_plan(
        {
            "resource": "facilities",
            "intent": "aggregate",
            "metrics": [
                {"metric": "member_count"},
                {"metric": "staff_count"},
            ],
        }
    )

    with pytest.raises(PlanValidationError, match="independent to-many"):
        validate_query_plan(plan, registry=build_facility_fanout_registry())


def test_to_one_metric_rejects_plan_level_to_many_traversal() -> None:
    plan = parse_query_plan(
        {
            "resource": "facilities",
            "intent": "aggregate",
            "group_by": [{"field": "member.gender"}],
            "metrics": [{"metric": "facility_count"}],
        }
    )

    with pytest.raises(PlanValidationError, match="to-many field traversal"):
        validate_query_plan(plan, registry=build_facility_fanout_registry())


def test_private_metric_relationships_count_toward_budgets() -> None:
    plan = parse_query_plan(
        {
            "resource": "facilities",
            "intent": "aggregate",
            "metrics": [{"metric": "member_count"}],
        }
    )

    with pytest.raises(PlanValidationError, match="relationship edges"):
        validate_query_plan(
            plan,
            registry=build_facility_fanout_registry(),
            limits=PlanLimits(
                max_rows=100,
                max_joins=2,
                max_metrics=5,
                max_group_by=3,
                max_relationship_edges=0,
            ),
        )


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
        metrics=[{"metric": "revenue"}],
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
            {"metric": "order_count"},
            {"metric": "revenue"},
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
            {"metric": "order_count"},
            {"metric": "revenue"},
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

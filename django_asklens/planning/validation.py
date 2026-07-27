"""Semantic validation for parsed QueryPlan objects."""

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Never
from uuid import UUID

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.catalog.resources import (
    OPERATORS_BY_FIELD_TYPE,
    EnumDefinition,
    FieldSpec,
    Metric,
    SemanticResource,
    permission_set_allows,
)
from django_asklens.exceptions import (
    BudgetExceededError,
    PermissionDeniedError,
    PlanParseError,
    PlanValidationError,
    UnknownFieldError,
    UnknownMetricError,
)
from django_asklens.planning.schemas import (
    FilterSpec,
    GroupBySpec,
    MetricSpec,
    OrderBySpec,
    QueryPlan,
    parse_query_plan,
)
from django_asklens.planning.temporal import (
    normalize_date_string,
    normalize_datetime_string,
    normalize_time_string,
    parse_date_string,
    parse_datetime_string,
)
from django_asklens.settings import get_asklens_settings

type FieldUsage = Literal["filter", "select", "group_by", "order_by"]

RESULT_USAGES = {"select", "group_by", "order_by"}
DATE_FIELD_TYPES = {"date", "datetime"}


@dataclass(frozen=True, slots=True)
class PlanLimits:
    """Limits enforced before a QueryPlan can be compiled."""

    max_rows: int
    max_joins: int
    max_metrics: int
    max_group_by: int
    max_plan_bytes: int = 65_536
    max_filters: int = 20
    max_selected_fields: int = 25
    max_order_by: int = 5
    max_relationship_edges: int = 8
    max_in_values: int = 100
    max_filter_values: int = 200
    default_limit: int = 100


def validate_query_plan(
    plan: QueryPlan,
    *,
    registry: CatalogRegistry = default_registry,
    limits: PlanLimits | None = None,
    allow_sensitive_fields: bool = False,
    allow_hidden_fields: bool = False,
    permissions: Iterable[str] | None = None,
) -> QueryPlan:
    """Validate a parsed QueryPlan against catalog metadata and safety limits."""

    resolved_limits = limits or get_plan_limits()
    validate_plan_payload_size(
        plan.model_dump(mode="json", exclude_unset=True),
        max_bytes=resolved_limits.max_plan_bytes,
    )
    return _validate_query_plan(
        plan,
        registry=registry,
        limits=resolved_limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permissions,
    )


def _validate_query_plan(
    plan: QueryPlan,
    *,
    registry: CatalogRegistry,
    limits: PlanLimits,
    allow_sensitive_fields: bool,
    allow_hidden_fields: bool,
    permissions: Iterable[str] | None,
) -> QueryPlan:
    """Validate one parsed plan after its serialized size has been bounded."""

    permission_set = frozenset(permissions or ())
    resource = registry.get(plan.resource)
    validate_resource_permission(resource, permissions=permission_set)
    normalized_plan = plan.model_copy(
        update={
            "resource": resource.name,
            "limit": (
                plan.limit if "limit" in plan.model_fields_set else limits.default_limit
            ),
        }
    )
    validate_plan_shape(normalized_plan)
    validate_plan_limits(normalized_plan, resource=resource, limits=limits)

    normalized_plan = normalize_visualization_date_trunc_aliases(normalized_plan)
    normalized_plan = normalize_visualization_defaults(normalized_plan)
    validate_no_meaningless_duplicates(normalized_plan)
    validate_plan_fields(
        normalized_plan,
        resource=resource,
        limits=limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permission_set,
    )
    normalized_plan = normalize_filter_values(normalized_plan, resource=resource)
    validate_no_meaningless_duplicates(normalized_plan)
    return normalized_plan


def parse_and_validate_query_plan(
    raw_plan: str | bytes | Mapping[str, Any],
    *,
    registry: CatalogRegistry = default_registry,
    limits: PlanLimits | None = None,
    allow_sensitive_fields: bool = False,
    allow_hidden_fields: bool = False,
    permissions: Iterable[str] | None = None,
) -> QueryPlan:
    """Parse untrusted input and validate it against the semantic catalog."""

    resolved_limits = limits or get_plan_limits()
    validate_plan_payload_size(raw_plan, max_bytes=resolved_limits.max_plan_bytes)
    return _validate_query_plan(
        parse_query_plan(raw_plan),
        registry=registry,
        limits=resolved_limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permissions,
    )


def get_plan_limits(settings_overrides: Mapping[str, Any] | None = None) -> PlanLimits:
    """Return query-plan limits from Django settings plus optional overrides."""

    configured = get_asklens_settings()
    if settings_overrides is not None:
        configured = {**configured, **settings_overrides}

    max_rows = get_positive_int(configured, "MAX_ROWS")
    limits = PlanLimits(
        max_rows=max_rows,
        max_joins=get_non_negative_int(configured, "MAX_JOINS"),
        max_metrics=get_non_negative_int(configured, "MAX_METRICS"),
        max_group_by=get_non_negative_int(configured, "MAX_GROUP_BY"),
        max_plan_bytes=get_positive_int(configured, "MAX_PLAN_BYTES"),
        max_filters=get_non_negative_int(configured, "MAX_FILTERS"),
        max_selected_fields=get_non_negative_int(configured, "MAX_SELECTED_FIELDS"),
        max_order_by=get_non_negative_int(configured, "MAX_ORDER_BY"),
        max_relationship_edges=get_non_negative_int(
            configured, "MAX_RELATIONSHIP_EDGES"
        ),
        max_in_values=get_non_negative_int(configured, "MAX_IN_VALUES"),
        max_filter_values=get_non_negative_int(configured, "MAX_FILTER_VALUES"),
        default_limit=min(
            get_positive_int(configured, "DEFAULT_LIMIT"),
            max_rows,
        ),
    )
    return limits


def validate_plan_payload_size(
    raw_plan: str | bytes | Mapping[str, Any],
    *,
    max_bytes: int,
) -> None:
    """Reject a serialized plan above its UTF-8 byte budget before parsing."""

    if isinstance(raw_plan, bytes):
        byte_count = len(raw_plan)
    elif isinstance(raw_plan, str):
        try:
            byte_count = len(raw_plan.encode("utf-8"))
        except UnicodeEncodeError as exc:
            msg = "QueryPlan text must be valid UTF-8."
            raise PlanParseError(msg) from exc
    else:
        try:
            serialized = json.dumps(
                dict(raw_plan),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            byte_count = len(serialized.encode("utf-8"))
        except UnicodeEncodeError as exc:
            msg = "QueryPlan text values must be valid UTF-8."
            raise PlanParseError(msg) from exc
        except (TypeError, ValueError, OverflowError) as exc:
            msg = "QueryPlan mappings must contain only JSON-serializable values."
            raise PlanParseError(msg) from exc

    if byte_count > max_bytes:
        msg = f"QueryPlan payload exceeds MAX_PLAN_BYTES {max_bytes}."
        raise BudgetExceededError(msg)


def validate_resource_permission(
    resource: SemanticResource,
    *,
    permissions: frozenset[str],
) -> None:
    """Validate that the current permissions may query a resource."""

    if permission_set_allows(permissions, resource.requires_permission):
        return
    msg = (
        f"Resource {resource.name!r} requires permission "
        f"{resource.requires_permission!r}."
    )
    raise PermissionDeniedError(msg)


def normalize_filter_values(
    plan: QueryPlan,
    *,
    resource: SemanticResource,
) -> QueryPlan:
    """Normalize validated scalar values using only explicit semantic metadata."""

    filters = tuple(
        normalize_filter_value(filter_spec, field=resource.fields[filter_spec.field])
        for filter_spec in plan.filters
    )
    if filters == plan.filters:
        return plan
    return plan.model_copy(update={"filters": filters})


def normalize_filter_value(filter_spec: FilterSpec, *, field: FieldSpec) -> FilterSpec:
    """Return one filter with canonical float, UUID, decimal, or enum values."""

    if filter_spec.op in {"isnull", "last_n_days", "last_n_months"}:
        return filter_spec
    if filter_spec.op == "date_range":
        return normalize_date_range_filter(filter_spec, field=field)
    if filter_spec.op == "in":
        if not isinstance(filter_spec.value, list):  # Defensive after shape parsing.
            msg = "in filters require a non-empty list value."
            raise PlanValidationError(msg)
        normalized_value: object = [
            normalize_canonical_scalar(value, field=field)
            for value in filter_spec.value
        ]
    else:
        normalized_value = normalize_canonical_scalar(filter_spec.value, field=field)
    if normalized_value == filter_spec.value:
        return filter_spec
    return filter_spec.model_copy(update={"value": normalized_value})


def normalize_canonical_scalar(value: object, *, field: FieldSpec) -> object:
    """Validate and normalize one scalar for a canonical semantic field type."""

    if field.type == "string":
        if not isinstance(value, str):
            raise_invalid_filter_value(field, "must be a string")
        return value
    if field.type == "boolean":
        if not isinstance(value, bool):
            raise_invalid_filter_value(field, "must be a boolean")
        return value
    if field.type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise_invalid_filter_value(field, "must be an integer")
        return value
    if field.type == "decimal":
        if not isinstance(value, str):
            raise_invalid_filter_value(field, "must be a decimal string")
        try:
            parsed_decimal = Decimal(value)
        except InvalidOperation:
            raise_invalid_filter_value(field, "must be a valid decimal string")
        if not parsed_decimal.is_finite():
            raise_invalid_filter_value(field, "must be a finite decimal string")
        return value
    if field.type == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise_invalid_filter_value(field, "must be a JSON number")
        try:
            normalized_float = float(value)
        except OverflowError:
            raise_invalid_filter_value(field, "must be a finite JSON number")
        if not math.isfinite(normalized_float):
            raise_invalid_filter_value(field, "must be a finite JSON number")
        return normalized_float
    if field.type == "date":
        return normalize_date_string(value)
    if field.type == "datetime":
        return normalize_datetime_string(value)
    if field.type == "time":
        return normalize_time_string(value)
    if field.type == "uuid":
        if not isinstance(value, str):
            raise_invalid_filter_value(field, "must be a valid UUID string")
        try:
            return str(UUID(value))
        except ValueError:
            raise_invalid_filter_value(field, "must be a valid UUID string")
    if field.type == "enum":
        return normalize_enum_scalar(value, field=field)

    raise_invalid_filter_value(field, "uses an unsupported canonical type")


def normalize_date_range_filter(
    filter_spec: FilterSpec,
    *,
    field: FieldSpec,
) -> FilterSpec:
    """Validate and normalize one type-specific temporal range."""

    if not isinstance(filter_spec.value, list) or len(filter_spec.value) != 2:
        msg = "date_range filters require two values."
        raise PlanValidationError(msg)
    start_value, end_value = filter_spec.value
    if field.type == "date":
        normalized_start = normalize_date_string(start_value)
        normalized_end = normalize_date_string(end_value)
        if parse_date_string(normalized_start) > parse_date_string(normalized_end):
            raise_invalid_filter_value(field, "requires an ordered inclusive range")
    elif field.type == "datetime":
        normalized_start = normalize_datetime_string(start_value)
        normalized_end = normalize_datetime_string(end_value)
        if parse_datetime_string(normalized_start) >= parse_datetime_string(
            normalized_end
        ):
            raise_invalid_filter_value(field, "requires an ordered half-open range")
    else:  # Defensive after the operator/type matrix.
        raise_invalid_filter_value(field, "does not support date_range")
    return filter_spec.model_copy(update={"value": [normalized_start, normalized_end]})


def normalize_enum_scalar(value: object, *, field: FieldSpec) -> str | int:
    """Resolve one accepted explicit enum value or alias to its canonical value."""

    enum = field.enum
    if not isinstance(enum, EnumDefinition):  # Defensive against invalid mutation.
        raise_invalid_filter_value(field, "has no trusted enum definition")
    lookup = {
        (type(token), token): enum_value.value
        for enum_value in enum.values
        for token in (enum_value.value, *enum_value.aliases)
    }
    try:
        return lookup[(type(value), value)]
    except (KeyError, TypeError):
        raise_invalid_filter_value(field, "must be a registered enum value or alias")


def raise_invalid_filter_value(field: FieldSpec, detail: str) -> Never:
    """Raise a stable semantic error without relying on Django coercion."""

    msg = f"Filter value for field {field.name!r} {detail}."
    raise PlanValidationError(msg)


def normalize_visualization_defaults(plan: QueryPlan) -> QueryPlan:
    """Infer safe visualization defaults from unambiguous plan result keys."""

    if plan.visualization.type == "table":
        if plan.visualization.x is None and plan.visualization.y is None:
            return plan
        return plan.model_copy(
            update={
                "visualization": plan.visualization.model_copy(
                    update={"x": None, "y": None}
                )
            }
        )

    if plan.visualization.type == "metric" and plan.visualization.y is None:
        if len(plan.metrics) != 1:
            return plan
        return plan.model_copy(
            update={
                "visualization": plan.visualization.model_copy(
                    update={"y": plan.metrics[0].metric}
                )
            }
        )

    return plan


def normalize_visualization_date_trunc_aliases(plan: QueryPlan) -> QueryPlan:
    """Normalize safe date-bucket visualization aliases to real result keys.

    Query results use the original grouped field name as the public result key,
    even when ``date_trunc`` is applied. Some providers naturally emit aliases
    such as ``start_date_month``. Accept only aliases that exactly match a
    date-truncated group_by field and canonicalize them before normal semantic
    validation.
    """

    alias_map = build_date_trunc_alias_map(plan)
    if not alias_map:
        return plan

    updates = {}
    if plan.visualization.x in alias_map:
        updates["x"] = alias_map[plan.visualization.x]
    if plan.visualization.y in alias_map:
        updates["y"] = alias_map[plan.visualization.y]
    if not updates:
        return plan

    return plan.model_copy(
        update={"visualization": plan.visualization.model_copy(update=updates)}
    )


def build_date_trunc_alias_map(plan: QueryPlan) -> dict[str, str]:
    """Return accepted visualization aliases for date-truncated groupings."""

    aliases: dict[str, str] = {}
    for group in plan.group_by:
        if group.date_trunc is None:
            continue
        for alias in date_trunc_aliases(group.field, group.date_trunc):
            aliases[alias] = group.field
    return aliases


def date_trunc_aliases(field_name: str, date_trunc: str) -> set[str]:
    """Return conservative aliases for one date-truncated grouping field."""

    normalized_field = re.sub(r"[^A-Za-z0-9]+", "_", field_name).strip("_")
    return {
        f"{field_name}_{date_trunc}",
        f"{normalized_field}_{date_trunc}",
    }


def validate_plan_shape(plan: QueryPlan) -> None:
    """Validate intent-specific QueryPlan structure."""

    if plan.intent == "list":
        if not plan.select:
            msg = "List query plans must select at least one field."
            raise PlanValidationError(msg)
        if plan.metrics:
            msg = "List query plans must not request metrics."
            raise PlanValidationError(msg)
        if plan.group_by:
            msg = "List query plans must not include group_by."
            raise PlanValidationError(msg)
        return

    if plan.intent == "aggregate":
        if plan.select:
            msg = "Aggregate query plans must not include select."
            raise PlanValidationError(msg)
        if not plan.metrics:
            msg = "Aggregate query plans must request at least one metric."
            raise PlanValidationError(msg)
        return

    msg = f"Unsupported query intent {plan.intent!r}."
    raise PlanValidationError(msg)


def validate_plan_limits(
    plan: QueryPlan,
    *,
    resource: SemanticResource,
    limits: PlanLimits,
) -> None:
    """Validate every accepted structural dimension before compilation."""

    count_limits = (
        (len(plan.filters), limits.max_filters, "filters"),
        (len(plan.select), limits.max_selected_fields, "selected fields"),
        (len(plan.order_by), limits.max_order_by, "order_by terms"),
        (len(plan.metrics), limits.max_metrics, "metrics"),
        (len(plan.group_by), limits.max_group_by, "group_by fields"),
    )
    for actual, maximum, label in count_limits:
        if actual > maximum:
            msg = f"QueryPlan requests more than {maximum} {label}."
            raise BudgetExceededError(msg)

    if plan.limit > limits.max_rows:
        msg = f"QueryPlan limit {plan.limit} exceeds MAX_ROWS {limits.max_rows}."
        raise BudgetExceededError(msg)

    for filter_spec in plan.filters:
        if filter_spec.op == "in" and isinstance(filter_spec.value, list):
            if len(filter_spec.value) > limits.max_in_values:
                msg = (
                    "QueryPlan in filter requests more than "
                    f"{limits.max_in_values} values."
                )
                raise BudgetExceededError(msg)

    filter_value_count = sum(filter_scalar_count(item) for item in plan.filters)
    if filter_value_count > limits.max_filter_values:
        msg = (
            "QueryPlan filters request more than "
            f"{limits.max_filter_values} scalar values."
        )
        raise BudgetExceededError(msg)

    relationship_edges = collect_relationship_edges(plan, resource=resource)
    if len(relationship_edges) > limits.max_relationship_edges:
        msg = (
            "QueryPlan traverses more than "
            f"{limits.max_relationship_edges} unique relationship edges."
        )
        raise BudgetExceededError(msg)

    validate_no_meaningless_duplicates(plan)


def filter_scalar_count(filter_spec: FilterSpec) -> int:
    """Count scalar filter values per occurrence."""

    if isinstance(filter_spec.value, list):
        return len(filter_spec.value)
    return 1


def iter_plan_field_references(plan: QueryPlan) -> Iterable[str]:
    """Yield every field reference occurrence across the complete plan."""

    yield from plan.select
    yield from (item.field for item in plan.filters)
    yield from (item.field for item in plan.group_by)
    yield from (item.field for item in plan.order_by if item.field is not None)


def collect_relationship_edges(
    plan: QueryPlan,
    *,
    resource: SemanticResource,
) -> set[str]:
    """Return unique trusted relationship prefixes traversed by the plan."""

    edges: set[str] = set()
    for field_name in iter_plan_field_references(plan):
        field = resource.fields.get(field_name)
        if field is None:
            continue
        edges.update(field.relationship_edges)
    for metric_spec in plan.metrics:
        metric = resource.metrics.get(metric_spec.metric)
        if metric is not None:
            edges.update(metric.relationship_edges)
    return edges


def validate_no_meaningless_duplicates(plan: QueryPlan) -> None:
    """Reject repeated references that add no well-defined query meaning."""

    reject_duplicate_keys(plan.select, label="select field")
    reject_duplicate_keys(
        (item.field for item in plan.group_by),
        label="group_by field",
    )
    reject_duplicate_keys(
        (
            ("field", item.field) if item.field is not None else ("metric", item.metric)
            for item in plan.order_by
        ),
        label="order_by target",
    )
    reject_duplicate_keys(
        ((item.field, item.op, json_value_key(item.value)) for item in plan.filters),
        label="filter",
    )
    for item in plan.filters:
        if item.op == "in" and isinstance(item.value, list):
            reject_duplicate_keys(
                (json_value_key(value) for value in item.value),
                label="in filter value",
            )


def json_value_key(value: object) -> tuple[str, str]:
    """Return a type-aware stable key for one JSON value."""

    return (
        type(value).__name__,
        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
    )


def reject_duplicate_keys(keys: Iterable[object], *, label: str) -> None:
    """Raise when an iterable contains a repeated hashable key."""

    seen: set[object] = set()
    for key in keys:
        if key in seen:
            msg = f"Duplicate {label} requested."
            raise PlanValidationError(msg)
        seen.add(key)


def validate_plan_fields(
    plan: QueryPlan,
    *,
    resource: SemanticResource,
    limits: PlanLimits,
    allow_sensitive_fields: bool,
    allow_hidden_fields: bool,
    permissions: frozenset[str],
) -> None:
    """Validate all plan field, metric, ordering, and visualization references."""

    for field_name in plan.select:
        validate_field_usage(
            resource,
            field_name,
            usage="select",
            limits=limits,
            allow_sensitive_fields=allow_sensitive_fields,
            allow_hidden_fields=allow_hidden_fields,
            permissions=permissions,
        )

    for filter_spec in plan.filters:
        field = validate_field_usage(
            resource,
            filter_spec.field,
            usage="filter",
            limits=limits,
            allow_sensitive_fields=allow_sensitive_fields,
            allow_hidden_fields=allow_hidden_fields,
            permissions=permissions,
        )
        validate_filter_operator(filter_spec, field=field)

    for group_by in plan.group_by:
        validate_group_by(
            resource,
            group_by,
            limits=limits,
            allow_sensitive_fields=allow_sensitive_fields,
            allow_hidden_fields=allow_hidden_fields,
            permissions=permissions,
        )

    metric_names = validate_metrics(
        resource,
        plan.metrics,
        limits=limits,
        permissions=permissions,
    )
    validate_aggregate_relationship_policy(plan, resource=resource)
    visible_field_keys = set(plan.select) | {group.field for group in plan.group_by}
    validate_order_by(
        resource,
        plan.order_by,
        visible_field_keys=visible_field_keys,
        metric_names=metric_names,
        limits=limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permissions,
    )
    validate_visualization_refs(
        plan,
        available_keys=visible_field_keys | metric_names,
        metric_names=metric_names,
    )


def validate_filter_operator(filter_spec: FilterSpec, *, field: FieldSpec) -> None:
    """Reject operators outside the explicit canonical field-type matrix."""

    supported = OPERATORS_BY_FIELD_TYPE.get(field.type, ())
    if filter_spec.op in supported:
        return
    msg = (
        f"Operator {filter_spec.op!r} is not supported for canonical "
        f"type {field.type!r}."
    )
    raise PlanValidationError(msg)


def validate_group_by(
    resource: SemanticResource,
    group_by: GroupBySpec,
    *,
    limits: PlanLimits,
    allow_sensitive_fields: bool,
    allow_hidden_fields: bool,
    permissions: frozenset[str],
) -> None:
    """Validate one group_by reference."""

    field = validate_field_usage(
        resource,
        group_by.field,
        usage="group_by",
        limits=limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permissions,
    )
    if group_by.date_trunc is not None and field.type not in DATE_FIELD_TYPES:
        msg = f"date_trunc requires a date/datetime field: {group_by.field!r}."
        raise PlanValidationError(msg)


def validate_metrics(
    resource: SemanticResource,
    metrics: tuple[MetricSpec, ...],
    *,
    limits: PlanLimits,
    permissions: frozenset[str],
) -> set[str]:
    """Validate requested metrics against registered catalog metrics."""

    seen: set[str] = set()
    for metric_spec in metrics:
        if metric_spec.metric in seen:
            msg = f"Duplicate metric requested: {metric_spec.metric!r}."
            raise PlanValidationError(msg)
        seen.add(metric_spec.metric)

        registered_metric = resource.metrics.get(metric_spec.metric)
        if registered_metric is None:
            msg = (
                f"Unknown metric {metric_spec.metric!r} for resource {resource.name!r}."
            )
            raise UnknownMetricError(msg)
        validate_metric_usage(
            registered_metric,
            limits=limits,
            permissions=permissions,
        )
    return seen


def validate_metric_usage(
    metric: Metric,
    *,
    limits: PlanLimits,
    permissions: frozenset[str],
) -> None:
    """Validate one trusted registered metric for the current request."""

    if metric.relation_depth > limits.max_joins:
        msg = (
            f"Metric {metric.name!r} exceeds MAX_JOINS "
            f"({metric.relation_depth} > {limits.max_joins})."
        )
        raise PlanValidationError(msg)
    if not permission_set_allows(permissions, metric.requires_permission):
        msg = (
            f"Metric {metric.name!r} requires permission "
            f"{metric.requires_permission!r}."
        )
        raise PermissionDeniedError(msg)


def validate_aggregate_relationship_policy(
    plan: QueryPlan,
    *,
    resource: SemanticResource,
) -> None:
    """Reject plan-level fanout that could silently alter registered metrics."""

    if plan.intent != "aggregate":
        return

    field_edges: set[str] = set()
    for field_name in iter_plan_field_references(plan):
        field = resource.fields.get(field_name)
        if field is not None:
            field_edges.update(field.to_many_relationship_edges)

    registered_metrics = [resource.metrics[item.metric] for item in plan.metrics]
    metric_edges = {
        edge
        for metric in registered_metrics
        for edge in metric.to_many_relationship_edges
    }
    all_edges = field_edges | metric_edges
    if len(all_edges) > 1:
        msg = "Aggregate plans cannot combine independent to-many relationship paths."
        raise PlanValidationError(msg)

    if not field_edges:
        return
    for metric in registered_metrics:
        if metric.cardinality_policy == "to_one_only":
            msg = (
                f"Metric {metric.name!r} cannot be combined with a to-many "
                "field traversal."
            )
            raise PlanValidationError(msg)
        if set(metric.to_many_relationship_edges) != field_edges:
            msg = (
                f"Metric {metric.name!r} does not use the same declared "
                "to-many grain as the aggregate fields."
            )
            raise PlanValidationError(msg)


def validate_order_by(
    resource: SemanticResource,
    order_by: tuple[OrderBySpec, ...],
    *,
    visible_field_keys: set[str],
    metric_names: set[str],
    limits: PlanLimits,
    allow_sensitive_fields: bool,
    allow_hidden_fields: bool,
    permissions: frozenset[str],
) -> None:
    """Validate order_by references."""

    for order_spec in order_by:
        if order_spec.field is not None:
            validate_field_usage(
                resource,
                order_spec.field,
                usage="order_by",
                limits=limits,
                allow_sensitive_fields=allow_sensitive_fields,
                allow_hidden_fields=allow_hidden_fields,
                permissions=permissions,
            )
            if order_spec.field not in visible_field_keys:
                msg = (
                    f"order_by field {order_spec.field!r} must be selected or grouped."
                )
                raise PlanValidationError(msg)
        if order_spec.metric is not None and order_spec.metric not in metric_names:
            msg = f"order_by metric {order_spec.metric!r} must be requested in metrics."
            raise PlanValidationError(msg)


def validate_visualization_refs(
    plan: QueryPlan,
    *,
    available_keys: set[str],
    metric_names: set[str],
) -> None:
    """Validate visualization references against plan result keys."""

    visualization = plan.visualization
    if visualization.x is not None and visualization.x not in available_keys:
        msg = f"Visualization x references unknown result key {visualization.x!r}."
        raise PlanValidationError(msg)
    if visualization.y is not None and visualization.y not in available_keys:
        msg = f"Visualization y references unknown result key {visualization.y!r}."
        raise PlanValidationError(msg)
    if visualization.type == "metric" and visualization.y not in metric_names:
        msg = "Metric visualization y must reference a requested metric."
        raise PlanValidationError(msg)


def validate_field_usage(
    resource: SemanticResource,
    field_name: str,
    *,
    usage: FieldUsage,
    limits: PlanLimits,
    allow_sensitive_fields: bool,
    allow_hidden_fields: bool,
    permissions: frozenset[str],
) -> FieldSpec:
    """Validate that a field can be used in a specific plan location."""

    field = resource.fields.get(field_name)
    if field is None:
        msg = f"Unknown field {field_name!r} for resource {resource.name!r}."
        raise UnknownFieldError(msg)
    if field.relation_depth > limits.max_joins:
        msg = f"Field {field_name!r} exceeds MAX_JOINS {limits.max_joins}."
        raise BudgetExceededError(msg)
    if field.filter_only and usage != "filter":
        msg = f"Field {field_name!r} can only be used in filters."
        raise PlanValidationError(msg)

    sensitive_allowed = is_sensitive_field_allowed(
        field,
        allow_sensitive_fields=allow_sensitive_fields,
        permissions=permissions,
    )
    if field.sensitive and not sensitive_allowed:
        msg = f"Field {field_name!r} is sensitive and requires explicit permission."
        raise PermissionDeniedError(msg)
    if field.requires_permission is not None and not permission_set_allows(
        permissions,
        field.requires_permission,
    ):
        msg = f"Field {field_name!r} requires permission {field.requires_permission!r}."
        raise PermissionDeniedError(msg)

    hidden_allowed = allow_hidden_fields or (field.sensitive and sensitive_allowed)
    if not field.llm_visible and not hidden_allowed:
        msg = f"Field {field_name!r} is hidden from plan generation."
        raise PermissionDeniedError(msg)
    if usage in RESULT_USAGES and not field.result_visible:
        msg = f"Field {field_name!r} is not allowed in results."
        raise PermissionDeniedError(msg)
    return field


def is_sensitive_field_allowed(
    field: FieldSpec,
    *,
    allow_sensitive_fields: bool,
    permissions: frozenset[str],
) -> bool:
    """Return whether a sensitive field may be used."""

    if allow_sensitive_fields:
        return True
    if field.requires_permission is None:
        return False
    return permission_set_allows(permissions, field.requires_permission)


def get_positive_int(settings: Mapping[str, Any], key: str) -> int:
    """Read a positive integer setting."""

    value = settings[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        msg = f"DJANGO_ASKLENS[{key!r}] must be a positive integer."
        raise PlanValidationError(msg)
    return value


def get_non_negative_int(settings: Mapping[str, Any], key: str) -> int:
    """Read a non-negative integer setting."""

    value = settings[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        msg = f"DJANGO_ASKLENS[{key!r}] must be a non-negative integer."
        raise PlanValidationError(msg)
    return value

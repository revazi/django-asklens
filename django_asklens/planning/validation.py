"""Semantic validation for parsed QueryPlan objects."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.catalog.resources import (
    FieldSpec,
    SemanticResource,
    permission_set_allows,
)
from django_asklens.exceptions import (
    PermissionDeniedError,
    PlanValidationError,
    UnknownFieldError,
    UnknownMetricError,
)
from django_asklens.planning.schemas import (
    GroupBySpec,
    MetricSpec,
    OrderBySpec,
    QueryPlan,
    parse_query_plan,
)
from django_asklens.settings import get_asklens_settings

type FieldUsage = Literal["filter", "select", "group_by", "metric", "order_by"]

RESULT_USAGES = {"select", "group_by", "metric", "order_by"}
DATE_FIELD_TYPES = {"date", "datetime"}


@dataclass(frozen=True, slots=True)
class PlanLimits:
    """Limits enforced before a QueryPlan can be compiled."""

    max_rows: int
    max_joins: int
    max_metrics: int
    max_group_by: int


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
    permission_set = frozenset(permissions or ())
    resource = registry.get(plan.resource)
    normalized_plan = plan.model_copy(update={"resource": resource.name})

    validate_plan_shape(normalized_plan)
    validate_plan_limits(normalized_plan, limits=resolved_limits)
    validate_plan_fields(
        normalized_plan,
        resource=resource,
        limits=resolved_limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permission_set,
    )
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

    return validate_query_plan(
        parse_query_plan(raw_plan),
        registry=registry,
        limits=limits,
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permissions,
    )


def get_plan_limits(settings_overrides: Mapping[str, Any] | None = None) -> PlanLimits:
    """Return query-plan limits from Django settings plus optional overrides."""

    configured = get_asklens_settings()
    if settings_overrides is not None:
        configured = {**configured, **settings_overrides}

    return PlanLimits(
        max_rows=get_positive_int(configured, "MAX_ROWS"),
        max_joins=get_non_negative_int(configured, "MAX_JOINS"),
        max_metrics=get_positive_int(configured, "MAX_METRICS"),
        max_group_by=get_positive_int(configured, "MAX_GROUP_BY"),
    )


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


def validate_plan_limits(plan: QueryPlan, *, limits: PlanLimits) -> None:
    """Validate count/row limits before compilation."""

    if plan.limit > limits.max_rows:
        msg = f"QueryPlan limit {plan.limit} exceeds MAX_ROWS {limits.max_rows}."
        raise PlanValidationError(msg)
    if len(plan.metrics) > limits.max_metrics:
        msg = f"QueryPlan requests more than {limits.max_metrics} metrics."
        raise PlanValidationError(msg)
    if len(plan.group_by) > limits.max_group_by:
        msg = f"QueryPlan requests more than {limits.max_group_by} group_by fields."
        raise PlanValidationError(msg)


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
        validate_field_usage(
            resource,
            filter_spec.field,
            usage="filter",
            limits=limits,
            allow_sensitive_fields=allow_sensitive_fields,
            allow_hidden_fields=allow_hidden_fields,
            permissions=permissions,
        )

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
        allow_sensitive_fields=allow_sensitive_fields,
        allow_hidden_fields=allow_hidden_fields,
        permissions=permissions,
    )
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
    allow_sensitive_fields: bool,
    allow_hidden_fields: bool,
    permissions: frozenset[str],
) -> set[str]:
    """Validate requested metrics against registered catalog metrics."""

    seen: set[str] = set()
    for metric_spec in metrics:
        if metric_spec.name in seen:
            msg = f"Duplicate metric requested: {metric_spec.name!r}."
            raise PlanValidationError(msg)
        seen.add(metric_spec.name)

        registered_metric = resource.metrics.get(metric_spec.name)
        if registered_metric is None:
            msg = f"Unknown metric {metric_spec.name!r} for resource {resource.name!r}."
            raise UnknownMetricError(msg)
        if (
            metric_spec.op != registered_metric.op
            or metric_spec.field != registered_metric.field
        ):
            msg = (
                f"Metric {metric_spec.name!r} does not match the registered "
                "catalog metric."
            )
            raise PlanValidationError(msg)

        validate_field_usage(
            resource,
            metric_spec.field,
            usage="metric",
            limits=limits,
            allow_sensitive_fields=allow_sensitive_fields,
            allow_hidden_fields=allow_hidden_fields,
            permissions=permissions,
        )
    return seen


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
        raise PlanValidationError(msg)
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

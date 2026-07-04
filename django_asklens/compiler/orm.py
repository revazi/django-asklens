"""Compile validated QueryPlans into Django ORM querysets."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import IntegerField, QuerySet, Value

from django_asklens.catalog.registry import CatalogRegistry, default_registry
from django_asklens.catalog.resources import FieldSpec, Metric, SemanticResource
from django_asklens.compiler.aggregations import build_aggregates
from django_asklens.compiler.dates import build_date_trunc_expression, to_orm_path
from django_asklens.compiler.filters import apply_filters
from django_asklens.exceptions import UnsupportedQueryError
from django_asklens.planning.schemas import GroupBySpec, QueryPlan


@dataclass(frozen=True, slots=True)
class ResultColumn:
    """Column metadata for compiled query results."""

    key: str
    label: str
    type: str


@dataclass(frozen=True, slots=True)
class CompiledQuery:
    """A QueryPlan compiled to an ORM queryset plus result metadata."""

    queryset: QuerySet
    columns: tuple[ResultColumn, ...]
    key_map: Mapping[str, str]
    visualization: dict[str, Any]


def compile_query_plan(
    plan: QueryPlan,
    *,
    registry: CatalogRegistry = default_registry,
    request: Any = None,
    now: datetime | None = None,
) -> CompiledQuery:
    """Compile a validated QueryPlan into an ORM queryset."""

    resource = registry.get(plan.resource)
    queryset = apply_filters(resource.get_base_queryset(request), plan.filters, now=now)

    if plan.intent == "list":
        return compile_list_query(plan=plan, resource=resource, queryset=queryset)
    if plan.intent == "aggregate":
        return compile_aggregate_query(plan=plan, resource=resource, queryset=queryset)

    msg = f"Unsupported query intent {plan.intent!r}."
    raise UnsupportedQueryError(msg)


def compile_list_query(
    *,
    plan: QueryPlan,
    resource: SemanticResource,
    queryset: QuerySet,
) -> CompiledQuery:
    """Compile a list-style plan."""

    orm_fields = tuple(to_orm_path(field_name) for field_name in plan.select)
    key_map = {
        orm_field: field_name
        for orm_field, field_name in zip(orm_fields, plan.select, strict=True)
    }
    compiled = queryset.values(*orm_fields)
    compiled = apply_order_by(
        compiled,
        plan,
        field_aliases={field: to_orm_path(field) for field in plan.select},
    )
    compiled = compiled[: plan.limit]

    return CompiledQuery(
        queryset=compiled,
        columns=tuple(
            field_column(resource.fields[field_name]) for field_name in plan.select
        ),
        key_map=key_map,
        visualization=plan.visualization.model_dump(exclude_none=True),
    )


def compile_aggregate_query(
    *,
    plan: QueryPlan,
    resource: SemanticResource,
    queryset: QuerySet,
) -> CompiledQuery:
    """Compile an aggregate-style plan."""

    group_aliases = build_group_aliases(plan.group_by)
    group_expressions = {
        alias: build_date_trunc_expression(group.field, group.date_trunc)
        for alias, group in group_aliases.items()
    }
    metric_expressions = build_aggregates(plan.metrics)

    if group_expressions:
        compiled = queryset.values(**group_expressions).annotate(**metric_expressions)
        field_aliases = group_aliases_to_public(group_aliases)
    else:
        compiled = (
            queryset.annotate(
                _asklens_group_all=Value(1, output_field=IntegerField()),
            )
            .values("_asklens_group_all")
            .annotate(**metric_expressions)
            .values(*(metric.name for metric in plan.metrics))
        )
        field_aliases = {}

    compiled = apply_order_by(compiled, plan, field_aliases=field_aliases)
    compiled = compiled[: plan.limit]

    key_map = {alias: group.field for alias, group in group_aliases.items()}
    key_map.update({metric.name: metric.name for metric in plan.metrics})

    return CompiledQuery(
        queryset=compiled,
        columns=build_aggregate_columns(resource, plan.group_by, plan.metrics),
        key_map=key_map,
        visualization=plan.visualization.model_dump(exclude_none=True),
    )


def build_group_aliases(group_by: tuple[GroupBySpec, ...]) -> dict[str, GroupBySpec]:
    """Return internal ORM aliases for group_by expressions."""

    return {f"_asklens_group_{index}": group for index, group in enumerate(group_by)}


def group_aliases_to_public(group_aliases: Mapping[str, GroupBySpec]) -> dict[str, str]:
    """Return mapping from public group field names to internal ORM aliases."""

    return {group.field: alias for alias, group in group_aliases.items()}


def apply_order_by(
    queryset: QuerySet,
    plan: QueryPlan,
    *,
    field_aliases: Mapping[str, str],
) -> QuerySet:
    """Apply order_by clauses to a compiled queryset."""

    order_by: list[str] = []
    for order_spec in plan.order_by:
        if order_spec.field is not None:
            target = field_aliases[order_spec.field]
        elif order_spec.metric is not None:
            target = order_spec.metric
        else:
            continue
        if order_spec.direction == "desc":
            target = f"-{target}"
        order_by.append(target)

    if not order_by:
        return queryset
    return queryset.order_by(*order_by)


def build_aggregate_columns(
    resource: SemanticResource,
    group_by: tuple[GroupBySpec, ...],
    metrics: tuple,
) -> tuple[ResultColumn, ...]:
    """Build column metadata for an aggregate result."""

    group_columns = tuple(
        field_column(resource.fields[group.field]) for group in group_by
    )
    metric_columns = tuple(
        metric_column(resource.metrics[metric.name]) for metric in metrics
    )
    return group_columns + metric_columns


def field_column(field: FieldSpec) -> ResultColumn:
    """Return result column metadata for a field."""

    return ResultColumn(key=field.name, label=field.label, type=field.type)


def metric_column(metric: Metric) -> ResultColumn:
    """Return result column metadata for a metric."""

    return ResultColumn(
        key=metric.name,
        label=metric.label or metric.name.replace("_", " ").title(),
        type="number",
    )

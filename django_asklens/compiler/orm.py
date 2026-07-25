"""Privately compile prepared AskLens plans into Django ORM querysets."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Never

from django.db.models import IntegerField, QuerySet, Value

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
class _PreparedQueryPlan:
    """Short-lived query state bound to one trusted execution context."""

    plan: QueryPlan
    resource: SemanticResource
    queryset: QuerySet
    now: datetime
    context_binding: object = field(repr=False, compare=False)

    def __reduce__(self) -> Never:
        """Prevent prepared state from becoming a reusable serialized token."""

        msg = "AskLens prepared query state is short-lived and not serializable."
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class _CompiledQuery:
    """Private context-bound ORM query and result metadata awaiting evaluation."""

    queryset: QuerySet
    columns: tuple[ResultColumn, ...]
    key_map: Mapping[str, str]
    visualization: dict[str, Any]
    context_binding: object = field(repr=False, compare=False)

    def __reduce__(self) -> Never:
        """Prevent compiled state from becoming a reusable serialized token."""

        msg = "AskLens compiled query state is short-lived and not serializable."
        raise TypeError(msg)


def _compile_prepared_query(prepared: _PreparedQueryPlan) -> _CompiledQuery:
    """Compile only state prepared by the trusted execution path."""

    if not isinstance(prepared, _PreparedQueryPlan):
        msg = "AskLens compiler requires an internal prepared query plan."
        raise TypeError(msg)

    plan = prepared.plan
    queryset = apply_filters(prepared.queryset, plan.filters, now=prepared.now)

    if plan.intent == "list":
        return _compile_list_query(prepared=prepared, queryset=queryset)
    if plan.intent == "aggregate":
        return _compile_aggregate_query(prepared=prepared, queryset=queryset)

    msg = f"Unsupported query intent {plan.intent!r}."
    raise UnsupportedQueryError(msg)


def _compile_list_query(
    *,
    prepared: _PreparedQueryPlan,
    queryset: QuerySet,
) -> _CompiledQuery:
    """Compile a prepared list-style plan."""

    plan = prepared.plan
    resource = prepared.resource
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

    return _CompiledQuery(
        queryset=compiled,
        columns=tuple(
            field_column(resource.fields[field_name]) for field_name in plan.select
        ),
        key_map=key_map,
        visualization=plan.visualization.model_dump(exclude_none=True),
        context_binding=prepared.context_binding,
    )


def _compile_aggregate_query(
    *,
    prepared: _PreparedQueryPlan,
    queryset: QuerySet,
) -> _CompiledQuery:
    """Compile a prepared aggregate-style plan."""

    plan = prepared.plan
    resource = prepared.resource
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

    return _CompiledQuery(
        queryset=compiled,
        columns=build_aggregate_columns(resource, plan.group_by, plan.metrics),
        key_map=key_map,
        visualization=plan.visualization.model_dump(exclude_none=True),
        context_binding=prepared.context_binding,
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

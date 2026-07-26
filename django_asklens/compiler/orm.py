"""Privately compile prepared AskLens plans into Django ORM querysets."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Never

from django.db.models import F, IntegerField, QuerySet, Value

from django_asklens.catalog.resources import FieldSpec, Metric, SemanticResource
from django_asklens.compiler.aggregations import build_aggregates
from django_asklens.compiler.dates import build_date_trunc_expression
from django_asklens.compiler.filters import apply_filters
from django_asklens.exceptions import UnsupportedQueryError
from django_asklens.planning.schemas import GroupBySpec, QueryPlan

type LimitScope = Literal["rows", "groups"]
type OrderingTerm = tuple[str, Literal["asc", "desc"]]


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
    limit: int
    limit_scope: LimitScope
    detects_truncation: bool
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
    queryset = apply_filters(
        prepared.queryset,
        plan.filters,
        resource=prepared.resource,
        now=prepared.now,
    )

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
    select_aliases = {
        f"_asklens_select_{index}": F(resource.fields[field_name].binding)
        for index, field_name in enumerate(plan.select)
    }
    key_map = {
        alias: field_name
        for alias, field_name in zip(select_aliases, plan.select, strict=True)
    }
    compiled = queryset.values(**select_aliases)
    ordering = build_list_ordering(plan, resource=resource)
    compiled = apply_ordering(compiled, ordering)
    compiled = compiled[: plan.limit + 1]

    return _CompiledQuery(
        queryset=compiled,
        columns=tuple(
            field_column(resource.fields[field_name]) for field_name in plan.select
        ),
        key_map=key_map,
        visualization=plan.visualization.model_dump(exclude_none=True),
        limit=plan.limit,
        limit_scope="rows",
        detects_truncation=True,
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
        alias: build_date_trunc_expression(
            resource.fields[group.field].binding,
            group.date_trunc,
        )
        for alias, group in group_aliases.items()
    }
    metric_expressions = build_aggregates(plan.metrics, resource=resource)

    if group_expressions:
        compiled = queryset.values(**group_expressions).annotate(**metric_expressions)
        field_aliases = group_aliases_to_public(group_aliases)
        ordering = build_grouped_ordering(
            plan,
            field_aliases=field_aliases,
        )
        compiled = apply_ordering(compiled, ordering)
        compiled = compiled[: plan.limit + 1]
        effective_limit = plan.limit
        detects_truncation = True
    else:
        compiled = (
            queryset.annotate(
                _asklens_group_all=Value(1, output_field=IntegerField()),
            )
            .values("_asklens_group_all")
            .annotate(**metric_expressions)
            .values(*(metric.name for metric in plan.metrics))
        )
        compiled = compiled[:1]
        effective_limit = 1
        detects_truncation = False

    key_map = {alias: group.field for alias, group in group_aliases.items()}
    key_map.update({metric.name: metric.name for metric in plan.metrics})

    return _CompiledQuery(
        queryset=compiled,
        columns=build_aggregate_columns(resource, plan.group_by, plan.metrics),
        key_map=key_map,
        visualization=plan.visualization.model_dump(exclude_none=True),
        limit=effective_limit,
        limit_scope="groups",
        detects_truncation=detects_truncation,
        context_binding=prepared.context_binding,
    )


def build_group_aliases(group_by: tuple[GroupBySpec, ...]) -> dict[str, GroupBySpec]:
    """Return internal ORM aliases for group_by expressions."""

    return {f"_asklens_group_{index}": group for index, group in enumerate(group_by)}


def group_aliases_to_public(group_aliases: Mapping[str, GroupBySpec]) -> dict[str, str]:
    """Return mapping from public group field names to internal ORM aliases."""

    return {group.field: alias for alias, group in group_aliases.items()}


def build_list_ordering(
    plan: QueryPlan,
    *,
    resource: SemanticResource,
) -> tuple[OrderingTerm, ...]:
    """Return caller/default list ordering with a private identity tie-breaker."""

    ordering: list[OrderingTerm] = []
    if plan.order_by:
        ordering.extend(
            (resource.fields[item.field].binding, item.direction)
            for item in plan.order_by
            if item.field is not None
        )
    else:
        ordering.extend(
            (resource.fields[field_name].binding, direction)
            for field_name, direction in resource.default_order
        )

    identity_target = resource.row_identity
    if identity_target not in {target for target, _direction in ordering}:
        ordering.append((identity_target, "asc"))
    return tuple(ordering)


def build_grouped_ordering(
    plan: QueryPlan,
    *,
    field_aliases: Mapping[str, str],
) -> tuple[OrderingTerm, ...]:
    """Return grouped ordering with every missing group key as a tie-breaker."""

    ordering: list[OrderingTerm] = []
    for item in plan.order_by:
        if item.field is not None:
            ordering.append((field_aliases[item.field], item.direction))
        elif item.metric is not None:
            ordering.append((item.metric, item.direction))

    seen = {target for target, _direction in ordering}
    for group in plan.group_by:
        target = field_aliases[group.field]
        if target not in seen:
            ordering.append((target, "asc"))
            seen.add(target)
    return tuple(ordering)


def apply_ordering(
    queryset: QuerySet,
    ordering: Sequence[OrderingTerm],
) -> QuerySet:
    """Apply backend-normalized ordering with null values always last."""

    expressions = [
        F(target).desc(nulls_last=True)
        if direction == "desc"
        else F(target).asc(nulls_last=True)
        for target, direction in ordering
    ]
    if not expressions:
        return queryset
    return queryset.order_by(*expressions)


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

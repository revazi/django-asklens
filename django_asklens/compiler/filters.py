"""Filter compilation for Django ORM querysets."""

from datetime import datetime, timedelta

from django.db.models import Q

from django_asklens.catalog.resources import FieldSpec, SemanticResource
from django_asklens.compiler.dates import (
    parse_temporal_value,
    relative_datetime_bounds,
)
from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.schemas import FilterSpec

LOOKUP_BY_OPERATOR = {
    "eq": "exact",
    "contains": "contains",
    "icontains": "icontains",
    "gt": "gt",
    "gte": "gte",
    "lt": "lt",
    "lte": "lte",
    "in": "in",
    "isnull": "isnull",
}


def apply_filters(
    queryset,
    filters: tuple[FilterSpec, ...],
    *,
    resource: SemanticResource,
    now: datetime | None = None,
):
    """Apply validated QueryPlan filters through private field bindings."""

    for filter_spec in filters:
        queryset = apply_filter(
            queryset,
            filter_spec,
            resource=resource,
            now=now,
        )
    return queryset


def apply_filter(
    queryset,
    filter_spec: FilterSpec,
    *,
    resource: SemanticResource,
    now: datetime | None = None,
):
    """Apply one validated filter through a private field binding."""

    q_object = build_filter_q(filter_spec, resource=resource, now=now)
    if filter_spec.op == "neq":
        orm_path = resource.fields[filter_spec.field].binding
        return queryset.filter(**{f"{orm_path}__isnull": False}).exclude(q_object)
    return queryset.filter(q_object)


def build_filter_q(
    filter_spec: FilterSpec,
    *,
    resource: SemanticResource,
    now: datetime | None = None,
) -> Q:
    """Build a safe ORM Q object through a private field binding."""

    field = resource.fields[filter_spec.field]
    orm_path = field.binding
    operator = filter_spec.op

    if operator == "date_range":
        return build_date_range_q(
            orm_path,
            filter_spec.value,
            field_type=field.type,
        )
    if operator in {"last_n_days", "last_n_months"}:
        if not isinstance(filter_spec.value, int):
            msg = f"{operator} filters require an integer value."
            raise PlanValidationError(msg)
        start, end = relative_datetime_bounds(
            operator=operator,
            amount=filter_spec.value,
            now=now,
            resource_timezone=resource.timezone_info,
        )
        if field.type == "date":
            local_start = start.astimezone(resource.timezone_info).date()
            local_end = (
                (end - timedelta(microseconds=1))
                .astimezone(resource.timezone_info)
                .date()
            )
            return Q(**{f"{orm_path}__gte": local_start}) & Q(
                **{f"{orm_path}__lte": local_end}
            )
        return Q(**{f"{orm_path}__gte": start}) & Q(**{f"{orm_path}__lt": end})

    value = compile_filter_value(filter_spec.value, field=field)
    if operator == "neq":
        return Q(**{f"{orm_path}__exact": value})

    lookup = LOOKUP_BY_OPERATOR.get(operator)
    if lookup is None:
        msg = f"Unsupported filter operator {operator!r}."
        raise PlanValidationError(msg)
    return Q(**{f"{orm_path}__{lookup}": value})


def compile_filter_value(value: object, *, field: FieldSpec) -> object:
    """Convert canonical temporal strings to explicit Python ORM values."""

    if field.type not in {"date", "datetime", "time"}:
        return value
    if isinstance(value, list):
        return [parse_temporal_value(item, field_type=field.type) for item in value]
    return parse_temporal_value(value, field_type=field.type)


def build_date_range_q(
    orm_path: str,
    value: object,
    *,
    field_type: str,
) -> Q:
    """Build an inclusive date or half-open datetime range predicate."""

    if not isinstance(value, list) or len(value) != 2:
        msg = "date_range filters require two values."
        raise PlanValidationError(msg)
    start = parse_temporal_value(value[0], field_type=field_type)
    end = parse_temporal_value(value[1], field_type=field_type)
    if field_type == "date":
        return Q(**{f"{orm_path}__gte": start}) & Q(**{f"{orm_path}__lte": end})
    return Q(**{f"{orm_path}__gte": start}) & Q(**{f"{orm_path}__lt": end})

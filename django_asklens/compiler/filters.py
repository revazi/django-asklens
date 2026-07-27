"""Filter compilation for Django ORM querysets."""

from datetime import datetime

from django.db.models import Q

from django_asklens.catalog.resources import SemanticResource
from django_asklens.compiler.dates import parse_temporal_value, relative_datetime
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

    orm_path = resource.fields[filter_spec.field].binding
    operator = filter_spec.op

    if operator == "neq":
        return Q(**{f"{orm_path}__exact": filter_spec.value})
    if operator == "date_range":
        return Q(**{f"{orm_path}__range": parse_date_range(filter_spec.value)})
    if operator in {"last_n_days", "last_n_months"}:
        if not isinstance(filter_spec.value, int):
            msg = f"{operator} filters require an integer value."
            raise PlanValidationError(msg)
        lower_bound = relative_datetime(
            operator=operator, amount=filter_spec.value, now=now
        )
        return Q(**{f"{orm_path}__gte": lower_bound})

    lookup = LOOKUP_BY_OPERATOR.get(operator)
    if lookup is None:
        msg = f"Unsupported filter operator {operator!r}."
        raise PlanValidationError(msg)
    return Q(**{f"{orm_path}__{lookup}": filter_spec.value})


def parse_date_range(value: object) -> tuple[object, object]:
    """Parse a validated date_range value into ORM-ready values."""

    if not isinstance(value, list) or len(value) != 2:
        msg = "date_range filters require two values."
        raise PlanValidationError(msg)
    start, end = value
    return parse_temporal_value(start), parse_temporal_value(end)

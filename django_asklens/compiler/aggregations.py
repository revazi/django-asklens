"""Aggregation helpers for Django ORM query compilation."""

from django.db.models import Avg, Count, Max, Min, Sum
from django.db.models.aggregates import Aggregate

from django_asklens.compiler.dates import to_orm_path
from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.schemas import MetricSpec

AGGREGATE_BY_OPERATOR = {
    "count": Count,
    "sum": Sum,
    "avg": Avg,
    "min": Min,
    "max": Max,
}


def build_aggregates(metrics: tuple[MetricSpec, ...]) -> dict[str, Aggregate]:
    """Build ORM aggregate expressions keyed by metric name."""

    return {metric.name: build_aggregate(metric) for metric in metrics}


def build_aggregate(metric: MetricSpec) -> Aggregate:
    """Build one ORM aggregate expression for a validated metric."""

    aggregate_class = AGGREGATE_BY_OPERATOR.get(metric.op)
    if aggregate_class is None:
        msg = f"Unsupported metric operator {metric.op!r}."
        raise PlanValidationError(msg)
    return aggregate_class(to_orm_path(metric.field))

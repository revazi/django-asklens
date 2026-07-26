"""Aggregation helpers for Django ORM query compilation."""

from django.db.models import Avg, Count, Max, Min, Sum
from django.db.models.aggregates import Aggregate

from django_asklens.catalog.resources import SemanticResource
from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.schemas import MetricSpec

AGGREGATE_BY_OPERATOR = {
    "count": Count,
    "sum": Sum,
    "avg": Avg,
    "min": Min,
    "max": Max,
}


def build_aggregates(
    metrics: tuple[MetricSpec, ...],
    *,
    resource: SemanticResource,
) -> dict[str, Aggregate]:
    """Build ORM aggregate expressions from private field bindings."""

    return {
        metric.name: build_aggregate(metric, resource=resource) for metric in metrics
    }


def build_aggregate(
    metric: MetricSpec,
    *,
    resource: SemanticResource,
) -> Aggregate:
    """Build one ORM aggregate expression from a private field binding."""

    aggregate_class = AGGREGATE_BY_OPERATOR.get(metric.op)
    if aggregate_class is None:
        msg = f"Unsupported metric operator {metric.op!r}."
        raise PlanValidationError(msg)
    return aggregate_class(resource.fields[metric.field].binding)

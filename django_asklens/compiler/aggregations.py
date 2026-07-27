"""Aggregation helpers for Django ORM query compilation."""

from collections.abc import Mapping

from django.db.models import Avg, Count, Max, Min, Sum
from django.db.models.aggregates import Aggregate

from django_asklens.catalog.resources import Metric, SemanticResource
from django_asklens.exceptions import PlanValidationError
from django_asklens.planning.schemas import MetricSpec

AGGREGATE_BY_OPERATOR = {
    "count": Count,
    "sum": Sum,
    "avg": Avg,
    "min": Min,
    "max": Max,
}


def build_metric_aliases(
    metrics: tuple[MetricSpec, ...],
) -> dict[str, MetricSpec]:
    """Return private ORM aliases for public semantic metric names."""

    return {f"_asklens_metric_{index}": metric for index, metric in enumerate(metrics)}


def build_aggregates(
    metric_aliases: Mapping[str, MetricSpec],
    *,
    resource: SemanticResource,
) -> dict[str, Aggregate]:
    """Build private ORM aggregate aliases from trusted metric registrations."""

    return {
        alias: build_aggregate(resource.metrics[metric.metric])
        for alias, metric in metric_aliases.items()
    }


def build_aggregate(metric: Metric) -> Aggregate:
    """Build one ORM aggregate solely from trusted registration metadata."""

    aggregate_class = AGGREGATE_BY_OPERATOR.get(metric.op)
    if aggregate_class is None:
        msg = f"Unsupported registered metric operator {metric.op!r}."
        raise PlanValidationError(msg)
    if metric.cardinality_policy == "count_distinct":
        return aggregate_class(metric.distinct_key, distinct=True)
    return aggregate_class(metric.binding)

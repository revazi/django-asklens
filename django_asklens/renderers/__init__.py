"""Result renderers for Django AskLens."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from django_asklens.compiler import ResultColumn
from django_asklens.renderers.charts import (
    SUPPORTED_CHART_TYPES,
    NormalizedChartSpec,
    normalize_chart_spec,
)
from django_asklens.renderers.tables import RenderedColumn, TablePayload, render_table


class RenderedResult(TypedDict):
    """Rendered query result payload."""

    columns: list[RenderedColumn]
    data: list[dict[str, Any]]
    row_count: int
    visualization: NormalizedChartSpec
    empty: NotRequired[bool]


def render_query_result(
    *,
    columns: Sequence[ResultColumn],
    rows: Iterable[Mapping[str, Any]],
    visualization: Mapping[str, Any] | None,
) -> RenderedResult:
    """Render query rows into table data plus a normalized chart spec."""

    table = render_table(columns=columns, rows=rows)
    chart_spec = normalize_chart_spec(visualization, columns=columns)
    rendered: RenderedResult = {
        "columns": table["columns"],
        "data": table["data"],
        "row_count": table["row_count"],
        "visualization": chart_spec,
    }
    if table.get("empty"):
        rendered["empty"] = True
    return rendered


__all__ = [
    "SUPPORTED_CHART_TYPES",
    "NormalizedChartSpec",
    "RenderedColumn",
    "RenderedResult",
    "TablePayload",
    "normalize_chart_spec",
    "render_query_result",
    "render_table",
]

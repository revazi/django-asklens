"""Result serialization helpers for Django AskLens responses."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from django_asklens.compiler import ResultColumn
from django_asklens.results.serialization import (
    SerializedColumn,
    SerializedRowsPayload,
    serialize_rows,
)
from django_asklens.results.visualization import (
    SUPPORTED_VISUALIZATION_HINT_TYPES,
    NormalizedVisualizationHint,
    normalize_visualization_hint,
)


class SerializedResult(TypedDict):
    """Serialized query result payload returned to API consumers."""

    columns: list[SerializedColumn]
    data: list[dict[str, Any]]
    row_count: int
    visualization: NotRequired[NormalizedVisualizationHint]
    empty: NotRequired[bool]


def serialize_query_result(
    *,
    columns: Sequence[ResultColumn],
    rows: Iterable[Mapping[str, Any]],
    visualization: Mapping[str, Any] | None,
    include_visualization: bool = True,
) -> SerializedResult:
    """Serialize query rows plus optional visualization hint metadata."""

    serialized_rows = serialize_rows(columns=columns, rows=rows)
    result: SerializedResult = {
        "columns": serialized_rows["columns"],
        "data": serialized_rows["data"],
        "row_count": serialized_rows["row_count"],
    }
    if include_visualization:
        result["visualization"] = normalize_visualization_hint(
            visualization, columns=columns
        )
    if serialized_rows.get("empty"):
        result["empty"] = True
    return result


__all__ = [
    "SUPPORTED_VISUALIZATION_HINT_TYPES",
    "NormalizedVisualizationHint",
    "SerializedColumn",
    "SerializedResult",
    "SerializedRowsPayload",
    "normalize_visualization_hint",
    "serialize_query_result",
    "serialize_rows",
]

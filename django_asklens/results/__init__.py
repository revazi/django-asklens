"""Core result serialization and separate presentation helpers."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from django_asklens.compiler import ResultColumn
from django_asklens.results.presentation import (
    SUPPORTED_PRESENTATION_KINDS,
    NormalizedPresentation,
    normalize_presentation,
)
from django_asklens.results.serialization import (
    SerializedColumn,
    SerializedRowsPayload,
    serialize_rows,
)


class SerializedResult(TypedDict):
    """Serialized core query result returned to API consumers."""

    columns: list[SerializedColumn]
    data: list[dict[str, Any]]
    row_count: int
    empty: NotRequired[bool]


def serialize_query_result(
    *,
    columns: Sequence[ResultColumn],
    rows: Iterable[Mapping[str, Any]],
) -> SerializedResult:
    """Serialize only query rows and columns, without presentation metadata."""

    serialized_rows = serialize_rows(columns=columns, rows=rows)
    result: SerializedResult = {
        "columns": serialized_rows["columns"],
        "data": serialized_rows["data"],
        "row_count": serialized_rows["row_count"],
    }
    if serialized_rows.get("empty"):
        result["empty"] = True
    return result


__all__ = [
    "SUPPORTED_PRESENTATION_KINDS",
    "NormalizedPresentation",
    "SerializedColumn",
    "SerializedResult",
    "SerializedRowsPayload",
    "normalize_presentation",
    "serialize_query_result",
    "serialize_rows",
]

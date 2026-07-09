"""JSON-safe result serialization helpers for AskLens responses."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, NotRequired, TypedDict
from uuid import UUID

from django_asklens.compiler import ResultColumn

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonPrimitive] | dict[str, JsonPrimitive]


class SerializedColumn(TypedDict):
    """Serialized result column metadata."""

    key: str
    label: str
    type: str


class SerializedRowsPayload(TypedDict):
    """Serialized row payload for AskLens API consumers."""

    columns: list[SerializedColumn]
    data: list[dict[str, JsonValue]]
    row_count: int
    empty: NotRequired[bool]


def serialize_rows(
    *,
    columns: Sequence[ResultColumn],
    rows: Iterable[Mapping[str, Any]],
) -> SerializedRowsPayload:
    """Serialize rows and columns into JSON-compatible response data."""

    serialized_columns = [serialize_column(column) for column in columns]
    column_types = {column.key: column.type for column in columns}
    serialized_rows = [serialize_row(row, column_types=column_types) for row in rows]
    payload: SerializedRowsPayload = {
        "columns": serialized_columns,
        "data": serialized_rows,
        "row_count": len(serialized_rows),
    }
    if not serialized_rows:
        payload["empty"] = True
    return payload


def serialize_column(column: ResultColumn) -> SerializedColumn:
    """Serialize one result column as JSON-compatible metadata."""

    return asdict(column)


def serialize_row(
    row: Mapping[str, Any],
    *,
    column_types: Mapping[str, str],
) -> dict[str, JsonValue]:
    """Serialize one result row using known column types when available."""

    return {
        key: normalize_cell_value(value, column_type=column_types.get(key))
        for key, value in row.items()
    }


def normalize_cell_value(value: Any, *, column_type: str | None = None) -> JsonValue:
    """Return a JSON-compatible cell value."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        if column_type == "integer":
            return int(value)
        if column_type == "number":
            return float(value)
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [normalize_cell_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize_cell_value(item) for key, item in value.items()}
    return str(value)

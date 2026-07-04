"""Table rendering helpers for AskLens query results."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, NotRequired, TypedDict
from uuid import UUID

from django_asklens.compiler import ResultColumn

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonPrimitive] | dict[str, JsonPrimitive]


class RenderedColumn(TypedDict):
    """Serialized result column metadata."""

    key: str
    label: str
    type: str


class TablePayload(TypedDict):
    """Rendered table payload."""

    columns: list[RenderedColumn]
    data: list[dict[str, JsonValue]]
    row_count: int
    empty: NotRequired[bool]


def render_table(
    *,
    columns: Sequence[ResultColumn],
    rows: Iterable[Mapping[str, Any]],
) -> TablePayload:
    """Render rows and columns into JSON-compatible table data."""

    rendered_columns = [render_column(column) for column in columns]
    column_types = {column.key: column.type for column in columns}
    rendered_rows = [render_row(row, column_types=column_types) for row in rows]
    payload: TablePayload = {
        "columns": rendered_columns,
        "data": rendered_rows,
        "row_count": len(rendered_rows),
    }
    if not rendered_rows:
        payload["empty"] = True
    return payload


def render_column(column: ResultColumn) -> RenderedColumn:
    """Render one result column as JSON-compatible metadata."""

    return asdict(column)


def render_row(
    row: Mapping[str, Any],
    *,
    column_types: Mapping[str, str],
) -> dict[str, JsonValue]:
    """Render one result row using known column types when available."""

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

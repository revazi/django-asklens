"""JSON-safe result serialization helpers for AskLens responses."""

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, NotRequired, TypedDict
from uuid import UUID

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import ResultSerializationError

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive


class SerializedColumn(TypedDict):
    """Serialized result column metadata."""

    key: str
    label: str
    type: str
    nullable: bool


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
    column_specs = {column.key: column for column in columns}
    serialized_rows = [serialize_row(row, column_specs=column_specs) for row in rows]
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

    return {
        "key": column.key,
        "label": column.label,
        "type": column.type,
        "nullable": column.nullable,
    }


def serialize_row(
    row: Mapping[str, Any],
    *,
    column_specs: Mapping[str, ResultColumn],
) -> dict[str, JsonValue]:
    """Serialize one result row using trusted canonical column metadata."""

    if set(row) != set(column_specs):
        msg = "Result row keys do not match declared result columns."
        raise ResultSerializationError(msg)
    return {
        key: normalize_cell_value(value, column=column_specs.get(key))
        for key, value in row.items()
    }


def normalize_cell_value(
    value: Any,
    *,
    column: ResultColumn | None = None,
) -> JsonValue:
    """Return a canonical JSON cell or fail instead of silently stringifying."""

    if column is None:
        msg = "Result row contains an undeclared column."
        raise ResultSerializationError(msg)
    if value is None:
        if column.nullable:
            return None
        msg = f"Non-null result column {column.key!r} returned null."
        raise ResultSerializationError(msg)

    column_type = column.type
    if column_type == "string" and isinstance(value, str):
        return value
    if column_type == "boolean" and isinstance(value, bool):
        return value
    if column_type == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if (
            isinstance(value, Decimal)
            and value.is_finite()
            and value == value.to_integral()
        ):
            return int(value)
    if column_type == "decimal" and isinstance(value, Decimal):
        if not value.is_finite():
            raise_non_finite_result(column)
        return str(value)
    if column_type == "float" and isinstance(value, (int, float, Decimal)):
        if isinstance(value, bool):
            raise_unsupported_result(value, column=column)
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise_non_finite_result(column)
            normalized_float = float(value)
        else:
            normalized_float = float(value)
        if not math.isfinite(normalized_float):
            raise_non_finite_result(column)
        return normalized_float
    if (
        column_type == "date"
        and isinstance(value, date)
        and not isinstance(value, datetime)
    ):
        return value.isoformat()
    if column_type == "datetime" and isinstance(value, datetime):
        return value.isoformat()
    if column_type == "time" and isinstance(value, time):
        return value.isoformat()
    if column_type == "uuid" and isinstance(value, UUID):
        return str(value)
    if column_type == "enum" and (
        isinstance(value, str)
        or (isinstance(value, int) and not isinstance(value, bool))
    ):
        if value in column.enum_values:
            return value
        msg = f"Result column {column.key!r} returned an unregistered enum value."
        raise ResultSerializationError(msg)

    if isinstance(value, (float, Decimal)):
        if (isinstance(value, float) and not math.isfinite(value)) or (
            isinstance(value, Decimal) and not value.is_finite()
        ):
            raise_non_finite_result(column)
    raise_unsupported_result(value, column=column)


def raise_non_finite_result(column: ResultColumn) -> None:
    """Reject JSON-incompatible NaN and infinity values."""

    msg = f"Result column {column.key!r} returned a non-finite numeric value."
    raise ResultSerializationError(msg)


def raise_unsupported_result(value: object, *, column: ResultColumn) -> None:
    """Reject a runtime type outside the trusted canonical result contract."""

    msg = (
        f"Unsupported result value type {type(value).__name__!r} for canonical "
        f"column type {column.type!r}."
    )
    raise ResultSerializationError(msg)

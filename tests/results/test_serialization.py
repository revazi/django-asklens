"""Tests for result row serialization."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import ResultSerializationError, public_error_payload
from django_asklens.results.serialization import serialize_rows


def test_serialize_rows_normalizes_values_to_json_primitives() -> None:
    payload = serialize_rows(
        columns=(
            ResultColumn("created_at", "Created", "datetime", nullable=False),
            ResultColumn("total", "Total", "decimal", nullable=True),
            ResultColumn("order_count", "Orders", "integer", nullable=False),
        ),
        rows=(
            {
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "total": Decimal("10.50"),
                "order_count": 2,
            },
        ),
    )

    assert payload == {
        "columns": [
            {
                "key": "created_at",
                "label": "Created",
                "type": "datetime",
                "nullable": False,
            },
            {"key": "total", "label": "Total", "type": "decimal", "nullable": True},
            {
                "key": "order_count",
                "label": "Orders",
                "type": "integer",
                "nullable": False,
            },
        ],
        "data": [
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "total": "10.50",
                "order_count": 2,
            }
        ],
        "row_count": 1,
    }


def test_serialize_rows_marks_empty_results() -> None:
    payload = serialize_rows(
        columns=(ResultColumn("status", "Status", "string", nullable=False),),
        rows=(),
    )

    assert payload == {
        "columns": [
            {"key": "status", "label": "Status", "type": "string", "nullable": False}
        ],
        "data": [],
        "row_count": 0,
        "empty": True,
    }


def test_result_serialization_error_has_only_safe_public_metadata() -> None:
    """Runtime type diagnostics remain private across public adapters."""

    error = ResultSerializationError("Unsupported result value type 'SecretObject'.")

    assert public_error_payload(error) == {
        "code": "asklens.execute.failed",
        "message": "The query could not be executed.",
    }


def test_serialize_rows_rejects_unsupported_runtime_objects() -> None:
    """Unknown values must not be silently stringified into successful results."""

    with pytest.raises(ResultSerializationError, match="Unsupported result value"):
        serialize_rows(
            columns=(ResultColumn("value", "Value", "string", nullable=False),),
            rows=({"value": object()},),
        )


def test_serialize_rows_rejects_unregistered_enum_results() -> None:
    """Rows cannot expose enum values omitted from trusted semantic metadata."""

    column = ResultColumn(
        "state",
        "State",
        "enum",
        nullable=False,
        enum_values=("draft", "active"),
    )

    assert serialize_rows(columns=(column,), rows=({"state": "active"},))["data"] == [
        {"state": "active"}
    ]
    with pytest.raises(ResultSerializationError, match="unregistered enum"):
        serialize_rows(columns=(column,), rows=({"state": "hidden"},))


def test_serialize_rows_enforces_declared_columns_and_nullability() -> None:
    """Column metadata is executable rather than descriptive-only."""

    column = ResultColumn("status", "Status", "string", nullable=False)
    with pytest.raises(ResultSerializationError, match="keys do not match"):
        serialize_rows(columns=(column,), rows=({},))
    with pytest.raises(ResultSerializationError, match="returned null"):
        serialize_rows(columns=(column,), rows=({"status": None},))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("NaN")])
def test_serialize_rows_rejects_non_finite_numbers(value: object) -> None:
    """JSON-incompatible numeric values fail through a typed result error."""

    with pytest.raises(ResultSerializationError, match="non-finite"):
        serialize_rows(
            columns=(ResultColumn("value", "Value", "float", nullable=False),),
            rows=({"value": value},),
        )

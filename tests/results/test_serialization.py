"""Tests for result row serialization."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from django_asklens.catalog.resources import Metric
from django_asklens.compiler import ResultColumn
from django_asklens.compiler.orm import metric_column
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("20.00"), "20"),
        (Decimal("10.50"), "10.5"),
        (Decimal("-0.00"), "0"),
        (Decimal("0E+10"), "0"),
        (Decimal("1E+3"), "1000"),
        (Decimal("1E-7"), "0.0000001"),
    ],
)
def test_aggregate_decimal_metrics_use_minimal_plain_strings(
    value: Decimal,
    expected: str,
) -> None:
    """Metric decimals are backend-neutral without exposing origin metadata."""

    column = metric_column(
        Metric("revenue", op="sum", binding="total", result_type="decimal")
    )

    payload = serialize_rows(columns=(column,), rows=({"revenue": value},))

    assert payload["columns"] == [
        {
            "key": "revenue",
            "label": "Revenue",
            "type": "decimal",
            "nullable": True,
        }
    ]
    assert payload["data"] == [{"revenue": expected}]
    assert "e" not in payload["data"][0]["revenue"].lower()


def test_scalar_decimal_fields_preserve_scale() -> None:
    """Option B applies only to aggregate metrics, never scalar fields."""

    payload = serialize_rows(
        columns=(ResultColumn("total", "Total", "decimal", nullable=False),),
        rows=({"total": Decimal("20.00")},),
    )

    assert payload["data"] == [{"total": "20.00"}]


@pytest.mark.parametrize(
    "value",
    [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")],
)
def test_aggregate_decimal_metrics_reject_non_finite_values(value: Decimal) -> None:
    """Aggregate canonicalization cannot turn non-finite values into strings."""

    column = metric_column(
        Metric("revenue", op="sum", binding="total", result_type="decimal")
    )

    with pytest.raises(ResultSerializationError, match="non-finite"):
        serialize_rows(columns=(column,), rows=({"revenue": value},))


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

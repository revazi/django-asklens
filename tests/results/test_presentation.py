"""Tests for presentation metadata separated from core query results."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import PresentationHintError
from django_asklens.results import normalize_presentation, serialize_query_result

COLUMNS = (
    ResultColumn("status", "Status", "string", nullable=False),
    ResultColumn("created_at", "Created", "datetime", nullable=False),
    ResultColumn("order_count", "Orders", "integer", nullable=False),
    ResultColumn("revenue", "Revenue", "decimal", nullable=True),
)


def test_normalize_table_presentation() -> None:
    assert normalize_presentation({"kind": "table"}, columns=COLUMNS) == {
        "kind": "table"
    }


def test_normalize_metric_presentation() -> None:
    assert normalize_presentation(
        {"kind": "metric", "y": "order_count"},
        columns=COLUMNS,
    ) == {
        "kind": "metric",
        "y": {"field": "order_count", "label": "Orders", "type": "integer"},
    }


def test_normalize_bar_line_and_pie_presentations() -> None:
    assert normalize_presentation(
        {"kind": "bar", "x": "status", "y": "revenue"},
        columns=COLUMNS,
    ) == {
        "kind": "bar",
        "x": {"field": "status", "label": "Status", "type": "string"},
        "y": {"field": "revenue", "label": "Revenue", "type": "decimal"},
    }
    assert (
        normalize_presentation(
            {"kind": "line", "x": "created_at", "y": "order_count"},
            columns=COLUMNS,
        )["kind"]
        == "line"
    )
    assert (
        normalize_presentation(
            {"kind": "pie", "x": "status", "y": "order_count"},
            columns=COLUMNS,
        )["kind"]
        == "pie"
    )


def test_presentation_validation_fails_closed() -> None:
    with pytest.raises(PresentationHintError, match="Unsupported"):
        normalize_presentation(
            {"kind": "scatter", "x": "status", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(PresentationHintError, match="unknown result column"):
        normalize_presentation(
            {"kind": "bar", "x": "missing", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(PresentationHintError, match="numeric"):
        normalize_presentation(
            {"kind": "bar", "x": "created_at", "y": "status"}, columns=COLUMNS
        )

    with pytest.raises(PresentationHintError, match="must not define x"):
        normalize_presentation(
            {"kind": "metric", "x": "status", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(PresentationHintError, match="Unknown presentation keys"):
        normalize_presentation({"kind": "table", "library": "chartjs"}, columns=COLUMNS)


def test_core_result_serialization_never_contains_presentation() -> None:
    payload = serialize_query_result(
        columns=COLUMNS,
        rows=(
            {
                "status": "paid",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "order_count": 2,
                "revenue": Decimal("10"),
            },
        ),
    )

    assert payload["row_count"] == 1
    assert payload["data"] == [
        {
            "status": "paid",
            "created_at": "2026-01-01T00:00:00+00:00",
            "order_count": 2,
            "revenue": "10",
        }
    ]
    assert "presentation" not in payload
    assert "visualization" not in payload

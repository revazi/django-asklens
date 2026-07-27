"""Tests for visualization hint normalization."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import VisualizationHintError
from django_asklens.results import serialize_query_result
from django_asklens.results.visualization import normalize_visualization_hint

COLUMNS = (
    ResultColumn("status", "Status", "string", nullable=False),
    ResultColumn("created_at", "Created", "datetime", nullable=False),
    ResultColumn("order_count", "Orders", "integer", nullable=False),
    ResultColumn("revenue", "Revenue", "decimal", nullable=True),
)


def test_normalize_table_visualization_hint() -> None:
    assert normalize_visualization_hint({"type": "table"}, columns=COLUMNS) == {
        "type": "table"
    }


def test_normalize_metric_visualization_hint() -> None:
    assert normalize_visualization_hint(
        {"type": "metric", "y": "order_count"},
        columns=COLUMNS,
    ) == {
        "type": "metric",
        "y": {"field": "order_count", "label": "Orders", "type": "integer"},
    }


def test_normalize_bar_line_and_pie_visualization_hints() -> None:
    assert normalize_visualization_hint(
        {"type": "bar", "x": "status", "y": "revenue"},
        columns=COLUMNS,
    ) == {
        "type": "bar",
        "x": {"field": "status", "label": "Status", "type": "string"},
        "y": {"field": "revenue", "label": "Revenue", "type": "decimal"},
    }
    assert (
        normalize_visualization_hint(
            {"type": "line", "x": "created_at", "y": "order_count"},
            columns=COLUMNS,
        )["type"]
        == "line"
    )
    assert (
        normalize_visualization_hint(
            {"type": "pie", "x": "status", "y": "order_count"},
            columns=COLUMNS,
        )["type"]
        == "pie"
    )


def test_visualization_hint_validation_fails_closed() -> None:
    with pytest.raises(VisualizationHintError, match="Unsupported"):
        normalize_visualization_hint(
            {"type": "scatter", "x": "status", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(VisualizationHintError, match="unknown column"):
        normalize_visualization_hint(
            {"type": "bar", "x": "missing", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(VisualizationHintError, match="numeric"):
        normalize_visualization_hint(
            {"type": "bar", "x": "created_at", "y": "status"}, columns=COLUMNS
        )

    with pytest.raises(VisualizationHintError, match="must not define x"):
        normalize_visualization_hint(
            {"type": "metric", "x": "status", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(VisualizationHintError, match="Unknown visualization keys"):
        normalize_visualization_hint(
            {"type": "table", "library": "chartjs"}, columns=COLUMNS
        )


def result_row() -> dict[str, object]:
    """Return one complete row matching the declared result columns."""

    return {
        "status": "paid",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "order_count": 2,
        "revenue": Decimal("10"),
    }


def serialized_result_row() -> dict[str, object]:
    """Return the canonical JSON representation of ``result_row``."""

    return {
        "status": "paid",
        "created_at": "2026-01-01T00:00:00+00:00",
        "order_count": 2,
        "revenue": "10",
    }


def test_serialize_query_result_combines_rows_and_visualization_hint() -> None:
    payload = serialize_query_result(
        columns=COLUMNS,
        rows=(result_row(),),
        visualization={"type": "bar", "x": "status", "y": "revenue"},
    )

    assert payload["row_count"] == 1
    assert payload["data"] == [serialized_result_row()]
    assert payload["visualization"]["type"] == "bar"
    assert payload["visualization"]["x"]["field"] == "status"


def test_serialize_query_result_can_return_data_without_visualization_hint() -> None:
    payload = serialize_query_result(
        columns=COLUMNS,
        rows=(result_row(),),
        visualization={"type": "bar", "x": "status", "y": "revenue"},
        include_visualization=False,
    )

    assert payload["row_count"] == 1
    assert payload["columns"]
    assert payload["data"] == [serialized_result_row()]
    assert "visualization" not in payload

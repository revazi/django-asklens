"""Tests for chart spec normalization."""

import pytest

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import RendererError
from django_asklens.renderers import render_query_result
from django_asklens.renderers.charts import normalize_chart_spec

COLUMNS = (
    ResultColumn("status", "Status", "string"),
    ResultColumn("created_at", "Created", "datetime"),
    ResultColumn("order_count", "Orders", "integer"),
    ResultColumn("revenue", "Revenue", "number"),
)


def test_normalize_table_chart_spec() -> None:
    assert normalize_chart_spec({"type": "table"}, columns=COLUMNS) == {"type": "table"}


def test_normalize_metric_chart_spec() -> None:
    assert normalize_chart_spec(
        {"type": "metric", "y": "order_count"},
        columns=COLUMNS,
    ) == {
        "type": "metric",
        "y": {"field": "order_count", "label": "Orders", "type": "integer"},
    }


def test_normalize_bar_line_and_pie_chart_specs() -> None:
    assert normalize_chart_spec(
        {"type": "bar", "x": "status", "y": "revenue"},
        columns=COLUMNS,
    ) == {
        "type": "bar",
        "x": {"field": "status", "label": "Status", "type": "string"},
        "y": {"field": "revenue", "label": "Revenue", "type": "number"},
    }
    assert (
        normalize_chart_spec(
            {"type": "line", "x": "created_at", "y": "order_count"},
            columns=COLUMNS,
        )["type"]
        == "line"
    )
    assert (
        normalize_chart_spec(
            {"type": "pie", "x": "status", "y": "order_count"},
            columns=COLUMNS,
        )["type"]
        == "pie"
    )


def test_chart_spec_validation_fails_closed() -> None:
    with pytest.raises(RendererError, match="Unsupported"):
        normalize_chart_spec(
            {"type": "scatter", "x": "status", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(RendererError, match="unknown column"):
        normalize_chart_spec(
            {"type": "bar", "x": "missing", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(RendererError, match="numeric"):
        normalize_chart_spec(
            {"type": "bar", "x": "created_at", "y": "status"}, columns=COLUMNS
        )

    with pytest.raises(RendererError, match="must not define x"):
        normalize_chart_spec(
            {"type": "metric", "x": "status", "y": "revenue"}, columns=COLUMNS
        )

    with pytest.raises(RendererError, match="Unknown visualization keys"):
        normalize_chart_spec({"type": "table", "library": "chartjs"}, columns=COLUMNS)


def test_render_query_result_combines_table_and_chart_payload() -> None:
    payload = render_query_result(
        columns=COLUMNS,
        rows=({"status": "paid", "order_count": 2, "revenue": 10},),
        visualization={"type": "bar", "x": "status", "y": "revenue"},
    )

    assert payload["row_count"] == 1
    assert payload["data"] == [{"status": "paid", "order_count": 2, "revenue": 10}]
    assert payload["visualization"]["type"] == "bar"
    assert payload["visualization"]["x"]["field"] == "status"

"""Tests for table rendering."""

from datetime import UTC, datetime
from decimal import Decimal

from django_asklens.compiler import ResultColumn
from django_asklens.renderers.tables import render_table


def test_render_table_normalizes_list_rows_to_json_values() -> None:
    payload = render_table(
        columns=(
            ResultColumn("created_at", "Created", "datetime"),
            ResultColumn("total", "Total", "number"),
            ResultColumn("order_count", "Orders", "integer"),
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
            {"key": "created_at", "label": "Created", "type": "datetime"},
            {"key": "total", "label": "Total", "type": "number"},
            {"key": "order_count", "label": "Orders", "type": "integer"},
        ],
        "data": [
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "total": 10.5,
                "order_count": 2,
            }
        ],
        "row_count": 1,
    }


def test_render_table_marks_empty_results() -> None:
    payload = render_table(
        columns=(ResultColumn("status", "Status", "string"),),
        rows=(),
    )

    assert payload == {
        "columns": [{"key": "status", "label": "Status", "type": "string"}],
        "data": [],
        "row_count": 0,
        "empty": True,
    }

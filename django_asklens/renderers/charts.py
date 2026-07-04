"""Chart-spec normalization for AskLens query results."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, TypedDict

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import RendererError

SUPPORTED_CHART_TYPES = ("table", "metric", "bar", "line", "pie")
NUMERIC_COLUMN_TYPES = {"integer", "number"}

type ChartType = Literal["table", "metric", "bar", "line", "pie"]


class ChartAxis(TypedDict):
    """Normalized chart axis metadata."""

    field: str
    label: str
    type: str


class NormalizedChartSpec(TypedDict):
    """Frontend-agnostic chart spec hint."""

    type: ChartType
    x: NotRequired[ChartAxis]
    y: NotRequired[ChartAxis]


def normalize_chart_spec(
    visualization: Mapping[str, Any] | None,
    *,
    columns: Sequence[ResultColumn],
) -> NormalizedChartSpec:
    """Validate and normalize a chart/table visualization hint."""

    spec = dict(visualization or {"type": "table"})
    validate_chart_spec_keys(spec)
    chart_type = spec.get("type", "table")
    if chart_type not in SUPPORTED_CHART_TYPES:
        msg = f"Unsupported visualization type {chart_type!r}."
        raise RendererError(msg)

    column_index = {column.key: column for column in columns}
    if chart_type == "table":
        validate_no_axis(spec, axis="x", chart_type=chart_type)
        validate_no_axis(spec, axis="y", chart_type=chart_type)
        return {"type": "table"}

    if chart_type == "metric":
        validate_no_axis(spec, axis="x", chart_type=chart_type)
        y_axis = require_axis(spec, axis="y", column_index=column_index)
        validate_numeric_axis(y_axis, axis_name="y", chart_type=chart_type)
        return {"type": "metric", "y": y_axis}

    x_axis = require_axis(spec, axis="x", column_index=column_index)
    y_axis = require_axis(spec, axis="y", column_index=column_index)
    validate_numeric_axis(y_axis, axis_name="y", chart_type=chart_type)
    return {"type": chart_type, "x": x_axis, "y": y_axis}


def validate_chart_spec_keys(spec: Mapping[str, Any]) -> None:
    """Reject unknown visualization keys."""

    allowed_keys = {"type", "x", "y"}
    unknown_keys = set(spec) - allowed_keys
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        msg = f"Unknown visualization keys: {names}."
        raise RendererError(msg)


def validate_no_axis(
    spec: Mapping[str, Any],
    *,
    axis: Literal["x", "y"],
    chart_type: str,
) -> None:
    """Validate that a chart type does not define a disallowed axis."""

    if spec.get(axis) is not None:
        msg = f"Visualization type {chart_type!r} must not define {axis}."
        raise RendererError(msg)


def require_axis(
    spec: Mapping[str, Any],
    *,
    axis: Literal["x", "y"],
    column_index: Mapping[str, ResultColumn],
) -> ChartAxis:
    """Return normalized axis metadata or fail safely."""

    field = spec.get(axis)
    if not isinstance(field, str) or not field:
        msg = f"Visualization axis {axis!r} is required."
        raise RendererError(msg)

    column = column_index.get(field)
    if column is None:
        msg = f"Visualization axis {axis!r} references unknown column {field!r}."
        raise RendererError(msg)
    return {"field": column.key, "label": column.label, "type": column.type}


def validate_numeric_axis(
    axis: ChartAxis,
    *,
    chart_type: str,
    axis_name: str = "y",
) -> None:
    """Validate that an axis is suitable for numeric chart values."""

    if axis["type"] not in NUMERIC_COLUMN_TYPES:
        msg = (
            f"Visualization type {chart_type!r} requires numeric {axis_name} axis; "
            f"got {axis['field']!r} with type {axis['type']!r}."
        )
        raise RendererError(msg)

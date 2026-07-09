"""Visualization-hint normalization for AskLens response data."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, TypedDict

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import VisualizationHintError

SUPPORTED_VISUALIZATION_HINT_TYPES = ("table", "metric", "bar", "line", "pie")
NUMERIC_COLUMN_TYPES = {"integer", "number"}

type VisualizationHintType = Literal["table", "metric", "bar", "line", "pie"]


class VisualizationAxis(TypedDict):
    """Normalized visualization axis metadata."""

    field: str
    label: str
    type: str


class NormalizedVisualizationHint(TypedDict):
    """Frontend-agnostic visualization hint metadata."""

    type: VisualizationHintType
    x: NotRequired[VisualizationAxis]
    y: NotRequired[VisualizationAxis]


def normalize_visualization_hint(
    visualization: Mapping[str, Any] | None,
    *,
    columns: Sequence[ResultColumn],
) -> NormalizedVisualizationHint:
    """Validate and normalize optional visualization hint metadata."""

    hint = dict(visualization or {"type": "table"})
    validate_visualization_hint_keys(hint)
    hint_type = hint.get("type", "table")
    if hint_type not in SUPPORTED_VISUALIZATION_HINT_TYPES:
        msg = f"Unsupported visualization type {hint_type!r}."
        raise VisualizationHintError(msg)

    column_index = {column.key: column for column in columns}
    if hint_type == "table":
        validate_no_axis(hint, axis="x", hint_type=hint_type)
        validate_no_axis(hint, axis="y", hint_type=hint_type)
        return {"type": "table"}

    if hint_type == "metric":
        validate_no_axis(hint, axis="x", hint_type=hint_type)
        y_axis = require_axis(hint, axis="y", column_index=column_index)
        validate_numeric_axis(y_axis, axis_name="y", hint_type=hint_type)
        return {"type": "metric", "y": y_axis}

    x_axis = require_axis(hint, axis="x", column_index=column_index)
    y_axis = require_axis(hint, axis="y", column_index=column_index)
    validate_numeric_axis(y_axis, axis_name="y", hint_type=hint_type)
    return {"type": hint_type, "x": x_axis, "y": y_axis}


def validate_visualization_hint_keys(hint: Mapping[str, Any]) -> None:
    """Reject unknown visualization hint keys."""

    allowed_keys = {"type", "x", "y"}
    unknown_keys = set(hint) - allowed_keys
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        msg = f"Unknown visualization keys: {names}."
        raise VisualizationHintError(msg)


def validate_no_axis(
    hint: Mapping[str, Any],
    *,
    axis: Literal["x", "y"],
    hint_type: str,
) -> None:
    """Validate that a hint type does not define a disallowed axis."""

    if hint.get(axis) is not None:
        msg = f"Visualization type {hint_type!r} must not define {axis}."
        raise VisualizationHintError(msg)


def require_axis(
    hint: Mapping[str, Any],
    *,
    axis: Literal["x", "y"],
    column_index: Mapping[str, ResultColumn],
) -> VisualizationAxis:
    """Return normalized axis metadata or fail safely."""

    field = hint.get(axis)
    if not isinstance(field, str) or not field:
        msg = f"Visualization axis {axis!r} is required."
        raise VisualizationHintError(msg)

    column = column_index.get(field)
    if column is None:
        msg = f"Visualization axis {axis!r} references unknown column {field!r}."
        raise VisualizationHintError(msg)
    return {"field": column.key, "label": column.label, "type": column.type}


def validate_numeric_axis(
    axis: VisualizationAxis,
    *,
    hint_type: str,
    axis_name: str = "y",
) -> None:
    """Validate that an axis is suitable for numeric visualizations."""

    if axis["type"] not in NUMERIC_COLUMN_TYPES:
        msg = (
            f"Visualization type {hint_type!r} requires numeric {axis_name} axis; "
            f"got {axis['field']!r} with type {axis['type']!r}."
        )
        raise VisualizationHintError(msg)

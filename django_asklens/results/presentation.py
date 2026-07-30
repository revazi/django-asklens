"""Presentation normalization kept outside core query execution."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, TypedDict

from django_asklens.compiler import ResultColumn
from django_asklens.exceptions import PresentationHintError

SUPPORTED_PRESENTATION_KINDS = ("table", "metric", "bar", "line", "pie")
NUMERIC_COLUMN_TYPES = {"decimal", "float", "integer"}

type PresentationKind = Literal["table", "metric", "bar", "line", "pie"]


class PresentationAxis(TypedDict):
    """Normalized presentation axis metadata."""

    field: str
    label: str
    type: str


class NormalizedPresentation(TypedDict):
    """Frontend-agnostic optional presentation metadata."""

    kind: PresentationKind
    x: NotRequired[PresentationAxis]
    y: NotRequired[PresentationAxis]


def normalize_presentation(
    presentation: Mapping[str, Any] | None,
    *,
    columns: Sequence[ResultColumn],
) -> NormalizedPresentation:
    """Validate presentation only against completed core result columns."""

    hint = dict(presentation or {"kind": "table"})
    validate_presentation_keys(hint)
    kind = hint.get("kind", "table")
    if kind not in SUPPORTED_PRESENTATION_KINDS:
        msg = f"Unsupported presentation kind {kind!r}."
        raise PresentationHintError(msg)

    column_index = {column.key: column for column in columns}
    if kind == "table":
        validate_no_axis(hint, axis="x", kind=kind)
        validate_no_axis(hint, axis="y", kind=kind)
        return {"kind": "table"}

    if kind == "metric":
        validate_no_axis(hint, axis="x", kind=kind)
        y_axis = require_axis(hint, axis="y", column_index=column_index)
        validate_numeric_axis(y_axis, axis_name="y", kind=kind)
        return {"kind": "metric", "y": y_axis}

    x_axis = require_axis(hint, axis="x", column_index=column_index)
    y_axis = require_axis(hint, axis="y", column_index=column_index)
    validate_numeric_axis(y_axis, axis_name="y", kind=kind)
    return {"kind": kind, "x": x_axis, "y": y_axis}


def validate_presentation_keys(hint: Mapping[str, Any]) -> None:
    """Reject unknown presentation keys."""

    unknown_keys = set(hint) - {"kind", "x", "y"}
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        msg = f"Unknown presentation keys: {names}."
        raise PresentationHintError(msg)


def validate_no_axis(
    hint: Mapping[str, Any],
    *,
    axis: Literal["x", "y"],
    kind: str,
) -> None:
    """Validate that a presentation kind omits a disallowed axis."""

    if hint.get(axis) is not None:
        msg = f"Presentation kind {kind!r} must not define {axis}."
        raise PresentationHintError(msg)


def require_axis(
    hint: Mapping[str, Any],
    *,
    axis: Literal["x", "y"],
    column_index: Mapping[str, ResultColumn],
) -> PresentationAxis:
    """Return normalized axis metadata or fail safely."""

    field = hint.get(axis)
    if not isinstance(field, str) or not field:
        msg = f"Presentation axis {axis!r} is required."
        raise PresentationHintError(msg)
    column = column_index.get(field)
    if column is None:
        msg = f"Presentation axis {axis!r} references an unknown result column."
        raise PresentationHintError(msg)
    return {"field": column.key, "label": column.label, "type": column.type}


def validate_numeric_axis(
    axis: PresentationAxis,
    *,
    kind: str,
    axis_name: str,
) -> None:
    """Validate that an axis is suitable for numeric presentation."""

    if axis["type"] not in NUMERIC_COLUMN_TYPES:
        msg = f"Presentation kind {kind!r} requires a numeric {axis_name} axis."
        raise PresentationHintError(msg)

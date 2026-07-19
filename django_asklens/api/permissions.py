"""DRF permission helpers for the AskLens API."""

from typing import Any

from django.utils.module_loading import import_string

from django_asklens.access import get_configured_permission_class_values
from django_asklens.permissions import get_request_permissions

__all__ = [
    "get_api_permission_classes",
    "get_request_permissions",
    "resolve_permission_class",
]


def get_api_permission_classes() -> tuple[type[Any], ...]:
    """Return configured permission classes for AskLens API views."""

    return tuple(
        resolve_permission_class(value)
        for value in get_configured_permission_class_values()
    )


def resolve_permission_class(value: str | type[Any]) -> type[Any]:
    """Resolve one DRF-compatible permission class."""

    if isinstance(value, str):
        value = import_string(value)
    if not isinstance(value, type):
        msg = "AskLens API permission entries must be permission classes."
        raise TypeError(msg)
    if not callable(getattr(value, "has_permission", None)):
        msg = (
            "AskLens API permission entries must define a "
            "has_permission(request, view) method."
        )
        raise TypeError(msg)
    return value

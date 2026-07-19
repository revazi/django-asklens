"""Core access checks for AskLens entry points."""

from typing import Any

from django.utils.module_loading import import_string

from django_asklens.settings import get_asklens_setting

__all__ = [
    "can_access_asklens",
    "get_configured_permission_class_values",
    "get_permission_gate_classes",
    "resolve_permission_gate_class",
]


def can_access_asklens(request: Any, *, view: Any = None) -> bool:
    """Return whether configured AskLens permission gates allow the request.

    The alpha admin query page intentionally reuses ``API_PERMISSION_CLASSES``
    so route-level and admin query access do not drift. This helper is kept out
    of ``django_asklens.api`` so non-API surfaces do not import DRF modules at
    module import time.
    """

    return all(
        permission_class().has_permission(request, view)
        for permission_class in get_permission_gate_classes()
    )


def get_configured_permission_class_values() -> tuple[Any, ...]:
    """Return configured AskLens route permission class values."""

    configured = get_asklens_setting("API_PERMISSION_CLASSES")
    if not isinstance(configured, (list, tuple)):
        msg = "DJANGO_ASKLENS['API_PERMISSION_CLASSES'] must be a list or tuple."
        raise TypeError(msg)
    return tuple(configured)


def get_permission_gate_classes() -> tuple[type[Any], ...]:
    """Return permission gate classes for non-API AskLens entry points."""

    return tuple(
        resolve_permission_gate_class(value)
        for value in get_configured_permission_class_values()
    )


def resolve_permission_gate_class(value: str | type[Any]) -> type[Any]:
    """Resolve a class with a DRF-compatible ``has_permission`` method."""

    if isinstance(value, str):
        value = import_string(value)
    if not isinstance(value, type):
        msg = "AskLens permission entries must be permission classes."
        raise TypeError(msg)
    if not callable(getattr(value, "has_permission", None)):
        msg = (
            "AskLens permission entries must define a has_permission(request, view) "
            "method."
        )
        raise TypeError(msg)
    return value

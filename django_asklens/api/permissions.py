"""DRF permission helpers for the AskLens API."""

from django.utils.module_loading import import_string
from rest_framework.permissions import BasePermission

from django_asklens.access import get_configured_permission_class_values
from django_asklens.permissions import get_request_permissions

__all__ = [
    "get_api_permission_classes",
    "get_request_permissions",
    "resolve_permission_class",
]


def get_api_permission_classes() -> tuple[type[BasePermission], ...]:
    """Return configured DRF permission classes for AskLens API views."""

    return tuple(
        resolve_permission_class(value)
        for value in get_configured_permission_class_values()
    )


def resolve_permission_class(value: str | type[BasePermission]) -> type[BasePermission]:
    """Resolve one DRF permission class from a class object or import string."""

    if isinstance(value, str):
        value = import_string(value)
    if not isinstance(value, type) or not issubclass(value, BasePermission):
        msg = "AskLens API permission entries must be DRF permission classes."
        raise TypeError(msg)
    return value

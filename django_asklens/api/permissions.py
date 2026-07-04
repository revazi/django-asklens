"""Permission helpers for the AskLens DRF API."""

from django.utils.module_loading import import_string
from rest_framework.permissions import BasePermission

from django_asklens.settings import get_asklens_setting


def get_api_permission_classes() -> tuple[type[BasePermission], ...]:
    """Return configured DRF permission classes for AskLens API views."""

    configured = get_asklens_setting("API_PERMISSION_CLASSES")
    if not isinstance(configured, (list, tuple)):
        msg = "DJANGO_ASKLENS['API_PERMISSION_CLASSES'] must be a list or tuple."
        raise TypeError(msg)

    return tuple(resolve_permission_class(value) for value in configured)


def resolve_permission_class(value: str | type[BasePermission]) -> type[BasePermission]:
    """Resolve one permission class from a class object or import string."""

    if isinstance(value, str):
        value = import_string(value)
    if not isinstance(value, type) or not issubclass(value, BasePermission):
        msg = "AskLens API permission entries must be DRF permission classes."
        raise TypeError(msg)
    return value

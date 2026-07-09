"""Permission helpers for the AskLens DRF API."""

from collections.abc import Callable, Iterable
from typing import Any

from django.utils.module_loading import import_string
from rest_framework.permissions import BasePermission

from django_asklens.settings import get_asklens_setting

RequestPermissionsGetter = Callable[[Any], Iterable[str] | None]


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


def get_request_permissions(request: Any) -> frozenset[str]:
    """Return permission strings used for AskLens catalog and plan validation."""

    configured = get_asklens_setting("REQUEST_PERMISSIONS_GETTER")
    if configured is None:
        return default_request_permissions(request)

    getter = resolve_request_permissions_getter(configured)
    permissions = getter(request)
    if permissions is None:
        return frozenset()
    if isinstance(permissions, str):
        msg = (
            "AskLens request permission getter must return an iterable of "
            "strings, not a string."
        )
        raise TypeError(msg)
    try:
        return frozenset(str(permission) for permission in permissions)
    except TypeError as exc:
        msg = "AskLens request permission getter must return an iterable of strings."
        raise TypeError(msg) from exc


def default_request_permissions(request: Any) -> frozenset[str]:
    """Return Django permission strings for the authenticated request user."""

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    return frozenset(user.get_all_permissions())


def resolve_request_permissions_getter(
    value: str | RequestPermissionsGetter,
) -> RequestPermissionsGetter:
    """Resolve the configured request permission getter."""

    if isinstance(value, str):
        value = import_string(value)
    if not callable(value):
        msg = (
            "DJANGO_ASKLENS['REQUEST_PERMISSIONS_GETTER'] must be a callable "
            "or import string."
        )
        raise TypeError(msg)
    return value

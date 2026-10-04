"""Request permission helpers for AskLens catalog and plan validation."""

from collections.abc import Callable, Iterable
from typing import Any

from django.utils.module_loading import import_string

from django_asklens.settings import get_asklens_setting

RequestPermissionsGetter = Callable[[Any], Iterable[str] | None]

__all__ = [
    "RequestPermissionsGetter",
    "default_request_permissions",
    "get_request_permissions",
    "resolve_request_permissions_getter",
]


def _validated_permission_set(permissions: Any, *, source: str) -> frozenset[str]:
    """Return only exact built-in strings from a server permission source."""

    requirement = f"{source} must return an iterable of strings"
    msg = f"{requirement}."
    if isinstance(permissions, str):
        raise TypeError(f"{requirement}, not a string.")
    try:
        resolved_permissions = tuple(permissions)
    except TypeError as exc:
        raise TypeError(msg) from exc
    if any(type(permission) is not str for permission in resolved_permissions):
        # Do not retain subclasses with object-defined hashing or comparison at
        # this authorization boundary.
        raise TypeError(msg)
    return frozenset(resolved_permissions)


def get_request_permissions(request: Any) -> frozenset[str]:
    """Return permission strings used for AskLens catalog and plan validation."""

    configured = get_asklens_setting("REQUEST_PERMISSIONS_GETTER")
    if configured is None:
        return default_request_permissions(request)

    getter = resolve_request_permissions_getter(configured)
    permissions = getter(request)
    if permissions is None:
        return frozenset()
    return _validated_permission_set(
        permissions,
        source="AskLens request permission getter",
    )


def default_request_permissions(request: Any) -> frozenset[str]:
    """Return Django permission strings for the authenticated request user."""

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    return _validated_permission_set(
        user.get_all_permissions(),
        source="Django permission backend",
    )


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

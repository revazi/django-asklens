"""Permission test doubles for AskLens route-gate tests."""

from rest_framework.permissions import BasePermission


class DenyAskLensAccess(BasePermission):
    """Deny every request for configurable permission gate tests."""

    def has_permission(self, request, view) -> bool:
        """Return False for every request."""

        return False


def get_request_permissions(request):
    """Return Django permissions plus test-only permissions attached to the user."""

    user = request.user
    if not getattr(user, "is_authenticated", False):
        return frozenset()

    permissions = set(user.get_all_permissions())
    permissions.update(getattr(user, "asklens_extra_permissions", ()))
    return permissions

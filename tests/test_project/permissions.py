"""DRF permission test doubles for AskLens route-gate tests."""

from rest_framework.permissions import BasePermission


class DenyAskLensAccess(BasePermission):
    """Deny every request for configurable permission gate tests."""

    def has_permission(self, request, view) -> bool:
        """Return False for every request."""

        return False

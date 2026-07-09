"""Permission helpers and test doubles for AskLens route-gate tests."""

from rest_framework.permissions import BasePermission


class DenyAskLensAccess(BasePermission):
    """Deny every request for configurable permission gate tests."""

    def has_permission(self, request, view) -> bool:
        """Return False for every request."""

        return False


class CanUseComplexAnalytics(BasePermission):
    """Allow users with synthetic reporting grants to access AskLens."""

    def has_permission(self, request, view) -> bool:
        """Return whether the request has any reporting grant."""

        user = getattr(request, "user", None)
        if getattr(user, "is_staff", False):
            return True
        permissions = get_request_permissions(request)
        return bool(permissions & reporting_permission_names())


def get_request_permissions(request):
    """Return Django, test-only, and tenant-scoped synthetic permissions."""

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()

    permissions = set(user.get_all_permissions())
    permissions.update(getattr(user, "asklens_extra_permissions", ()))
    permissions.update(get_staff_assignment_permissions(user))
    return permissions


def get_staff_assignment_permissions(user) -> set[str]:
    """Return flattened role/grant strings for active synthetic assignments."""

    from tests.test_project.models import StaffAssignment

    permissions: set[str] = set()
    assignments = (
        StaffAssignment.objects.filter(user=user, is_active=True)
        .select_related("facility")
        .prefetch_related("grants")
    )
    for assignment in assignments:
        permissions.add(f"role:{assignment.role}")
        permissions.add(f"facility:{assignment.facility_id}:role:{assignment.role}")
        if assignment.can_access_all_facilities:
            permissions.add("facility:*:access")
        for grant in assignment.grants.all():
            permissions.add(grant.name)
            permissions.add(f"facility:{assignment.facility_id}:{grant.name}")
    return permissions


def reporting_permission_names() -> set[str]:
    """Return permission names that can grant AskLens demo route access."""

    from tests.test_project.models import StaffGrant

    return {
        StaffGrant.ANALYTICS_VIEW,
        StaffGrant.BILLING_REPORTS_VIEW,
        StaffGrant.PAYMENT_REPORTS_VIEW,
        StaffGrant.MEMBER_REPORTS_VIEW,
        StaffGrant.PACKAGE_REPORTS_VIEW,
        StaffGrant.SCHEDULE_REPORTS_VIEW,
    }

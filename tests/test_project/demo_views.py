"""Demo-only views for the runnable AskLens test project."""

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import reverse

from tests.test_project.models import Facility, StaffAssignment
from tests.test_project.permissions import (
    get_request_permissions,
    permission_set_allows_any,
    reporting_permission_names,
)

DEMO_QUESTIONS = (
    "Show paid billing revenue by product",
    "Show payment totals by status",
    "List member contact emails",
    "Count member subscriptions by plan and status",
    "Show scheduled capacity by session type",
)


def asklens_demo(request):
    """Render a small vanilla-JS AskLens demo page for local exploration."""

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return redirect_to_login(request.get_full_path(), login_url="/admin/login/")
    if not can_access_asklens_demo(request):
        raise PermissionDenied("You do not have permission to use the AskLens demo.")

    return render(
        request,
        "test_project/asklens_demo.html",
        {
            "catalog_url": reverse("django_asklens:catalog"),
            "query_url": reverse("django_asklens:query"),
            "demo_questions": DEMO_QUESTIONS,
            "facility_scope": get_facility_scope_labels(request),
        },
    )


def can_access_asklens_demo(request) -> bool:
    """Return whether the request user may load the demo AskLens UI."""

    user = getattr(request, "user", None)
    if getattr(user, "is_superuser", False):
        return True
    permissions = get_request_permissions(request)
    return permission_set_allows_any(permissions, reporting_permission_names())


def get_facility_scope_labels(request) -> list[str]:
    """Return human-readable facility row scope labels for the demo page."""

    user = getattr(request, "user", None)
    if getattr(user, "is_superuser", False):
        return ["All demo facilities (superuser)"]

    assignments = StaffAssignment.objects.filter(
        user=user,
        is_active=True,
    ).select_related("facility")
    if assignments.filter(can_access_all_facilities=True).exists():
        return list(Facility.objects.order_by("name").values_list("name", flat=True))

    labels = {
        assignment.facility.name
        for assignment in assignments
        if assignment.facility_id is not None
    }
    return sorted(labels) or ["No facility row scope"]

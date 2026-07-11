"""Demo-only views for the runnable AskLens test project."""

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from django_asklens.frontend.views import render_asklens_frontend
from tests.test_project.models import Facility, StaffAssignment, StaffGrant
from tests.test_project.permissions import (
    get_request_permissions,
    permission_set_allows,
    permission_set_allows_any,
    reporting_permission_names,
)

DEMO_QUESTIONS = (
    (
        "Show paid billing revenue by product",
        StaffGrant.BILLING_REPORTS_VIEW,
    ),
    (
        "Show payment totals by status",
        StaffGrant.PAYMENT_REPORTS_VIEW,
    ),
    (
        "List member contact emails",
        StaffGrant.MEMBER_PII_VIEW,
    ),
    (
        "Count member subscriptions by plan and status",
        StaffGrant.PACKAGE_REPORTS_VIEW,
    ),
    (
        "Show scheduled capacity by session type",
        StaffGrant.SCHEDULE_REPORTS_VIEW,
    ),
    (
        "Show campaign spend and conversions by channel",
        StaffGrant.ANALYTICS_VIEW,
    ),
    (
        "Count leads by source and stage",
        StaffGrant.MEMBER_REPORTS_VIEW,
    ),
    (
        "Show booking attendance by session type",
        StaffGrant.SCHEDULE_REPORTS_VIEW,
    ),
    (
        "Show staff labor minutes by role",
        StaffGrant.SCHEDULE_REPORTS_VIEW,
    ),
    (
        "Show support tickets by priority and status",
        StaffGrant.ANALYTICS_VIEW,
    ),
)


def asklens_demo(request):
    """Render a small vanilla-JS AskLens demo page for local exploration."""

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return redirect_to_login(request.get_full_path(), login_url="/admin/login/")
    if not can_access_asklens_demo(request):
        raise PermissionDenied("You do not have permission to use the AskLens demo.")

    return render_asklens_frontend(
        request,
        extra_context={
            "page_title": "AskLens",
            "page_subtitle": "Synthetic demo data.",
            "starter_questions": get_demo_questions(request),
            "scope_title": "Tenant row scope",
            "scope_labels": get_facility_scope_labels(request),
        },
    )


def can_access_asklens_demo(request) -> bool:
    """Return whether the request user may load the demo AskLens UI."""

    user = getattr(request, "user", None)
    if getattr(user, "is_superuser", False):
        return True
    permissions = get_request_permissions(request)
    return permission_set_allows_any(permissions, reporting_permission_names())


def get_demo_questions(request) -> list[str]:
    """Return demo questions the current user has grants to execute."""

    user = getattr(request, "user", None)
    if getattr(user, "is_superuser", False):
        return [question for question, _permission in DEMO_QUESTIONS]
    permissions = get_request_permissions(request)
    return [
        question
        for question, required_permission in DEMO_QUESTIONS
        if permission_set_allows(permissions, required_permission)
    ]


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

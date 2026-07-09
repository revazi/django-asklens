"""AskLens registrations for the complex runnable test project."""

from collections.abc import Callable
from typing import Any

from django.db.models import Model, QuerySet

from django_asklens import Metric, register
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import UnknownResourceError
from tests.test_project.models import (
    BillingLine,
    Facility,
    MemberProfile,
    MemberStatus,
    MemberSubscription,
    PaymentAttempt,
    ScheduleSession,
    StaffAssignment,
    StaffGrant,
)


def ensure_complex_resources_registered() -> None:
    """Register complex resources once for the runnable demo settings."""

    try:
        default_registry.get("billing_lines")
    except UnknownResourceError:
        register_complex_resources()


def register_complex_resources() -> None:
    """Register complex resources in the default AskLens registry."""

    register_facilities()
    register_member_resources()
    register_billing_resources()
    register_schedule_resources()


def register_facilities() -> None:
    """Register tenant/facility metadata."""

    register(
        model=Facility,
        name="facilities",
        label="Facilities",
        description="Facilities visible to the current reporting user.",
        default_date_field="created_at",
        fields={
            "id": {"label": "Facility ID", "llm_visible": False},
            "name": {
                "label": "Facility name",
                "requires_permission": StaffGrant.FACILITY_VIEW,
            },
            "slug": {
                "label": "Facility slug",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": StaffGrant.FACILITY_VIEW,
            },
            "facility_type": {"label": "Facility type"},
            "timezone": {"label": "Timezone"},
            "is_active": {"label": "Active"},
            "created_at": {"label": "Created date"},
        },
        metrics=[
            Metric("facility_count", op="count", field="name", label="Facilities")
        ],
        base_queryset=queryset_for_permission(Facility, StaffGrant.FACILITY_VIEW),
    )


def register_member_resources() -> None:
    """Register member, member-contact, status, and subscription resources."""

    register(
        model=MemberProfile,
        name="members",
        label="Members",
        description="Non-PII member profile facts scoped by facility reporting grants.",
        default_date_field="member_since",
        fields={
            "member_id": {"label": "Member ID", "llm_visible": False},
            "facility.name": {
                "label": "Facility",
                "requires_permission": StaffGrant.FACILITY_VIEW,
            },
            "gender": {"label": "Gender"},
            "member_since": {"label": "Member since"},
            "created_at": {"label": "Created date"},
            "created_via_portal": {"label": "Created via portal"},
        },
        metrics=[Metric("member_count", op="count", field="gender", label="Members")],
        base_queryset=queryset_for_permission(
            MemberProfile, StaffGrant.MEMBER_REPORTS_VIEW
        ),
    )

    register(
        model=MemberProfile,
        name="member_contacts",
        label="Member contacts",
        description="Permission-scoped member contact details for approved facilities.",
        default_date_field="member_since",
        fields={
            "member_id": {"label": "Member ID", "llm_visible": False},
            "facility.name": {
                "label": "Facility",
                "requires_permission": StaffGrant.FACILITY_VIEW,
            },
            "first_name": {
                "label": "First name",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": StaffGrant.MEMBER_PII_VIEW,
            },
            "last_name": {
                "label": "Last name",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": StaffGrant.MEMBER_PII_VIEW,
            },
            "email": {
                "label": "Email",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": StaffGrant.MEMBER_PII_VIEW,
            },
            "phone": {
                "label": "Phone",
                "sensitive": True,
                "result_visible": False,
                "requires_permission": StaffGrant.MEMBER_PII_VIEW,
            },
            "date_of_birth": {
                "label": "Date of birth",
                "sensitive": True,
                "result_visible": False,
                "requires_permission": StaffGrant.MEMBER_PII_VIEW,
            },
            "member_since": {"label": "Member since"},
        },
        metrics=[
            Metric("contact_count", op="count", field="member_id", label="Contacts")
        ],
        base_queryset=queryset_for_permission(
            MemberProfile, StaffGrant.MEMBER_PII_VIEW
        ),
    )

    register(
        model=MemberStatus,
        name="member_statuses",
        label="Member statuses",
        description="Tenant-scoped member status history.",
        default_date_field="start_date",
        fields={
            "status_id": {"label": "Status ID", "llm_visible": False},
            "status": {"label": "Status"},
            "start_date": {"label": "Start date"},
            "end_date": {"label": "End date"},
            "member.member_since": {"label": "Member since"},
        },
        metrics=[Metric("status_count", op="count", field="status", label="Statuses")],
        base_queryset=queryset_for_permission(
            MemberStatus, StaffGrant.MEMBER_REPORTS_VIEW
        ),
    )

    register(
        model=MemberSubscription,
        name="member_subscriptions",
        label="Member subscriptions",
        description="Purchased subscription/package facts scoped by facility grants.",
        default_date_field="start_date",
        fields={
            "subscription_id": {"label": "Subscription ID", "llm_visible": False},
            "status": {"label": "Status"},
            "start_date": {"label": "Start date"},
            "end_date": {"label": "End date"},
            "billing_start_date": {"label": "Billing start date"},
            "cancellation_date": {"label": "Cancellation date"},
            "auto_renew": {"label": "Auto-renew"},
            "auto_pay": {"label": "Auto-pay"},
            "is_prorated": {"label": "Prorated"},
            "plan.name": {"label": "Plan"},
            "plan.sales_status": {"label": "Plan sales status"},
        },
        metrics=[
            Metric(
                "subscription_count",
                op="count",
                field="status",
                label="Subscriptions",
            )
        ],
        base_queryset=queryset_for_permission(
            MemberSubscription,
            StaffGrant.PACKAGE_REPORTS_VIEW,
        ),
    )


def register_billing_resources() -> None:
    """Register billing-line and payment resources."""

    register(
        model=BillingLine,
        name="billing_lines",
        label="Billing lines",
        description="Tenant-scoped billing line items for reporting.",
        default_date_field="billing_document.paid_at",
        fields={
            "line_id": {"label": "Billing line ID", "llm_visible": False},
            "billing_document.paid_at": {"label": "Paid date"},
            "billing_document.due_date": {"label": "Due date"},
            "billing_document.status": {"label": "Billing status"},
            "product_name": {"label": "Product"},
            "plan.name": {"label": "Plan"},
            "quantity": {"label": "Quantity", "metric": True},
            "item_price_cents": {
                "label": "Item price in cents",
                "metric": True,
                "requires_permission": StaffGrant.BILLING_REPORTS_VIEW,
            },
            "pretax_amount_cents": {
                "label": "Pre-tax amount in cents",
                "metric": True,
                "requires_permission": StaffGrant.BILLING_REPORTS_VIEW,
            },
            "tax_cents": {
                "label": "Tax in cents",
                "metric": True,
                "requires_permission": StaffGrant.BILLING_REPORTS_VIEW,
            },
            "total_amount_cents": {
                "label": "Total amount in cents",
                "metric": True,
                "requires_permission": StaffGrant.BILLING_REPORTS_VIEW,
            },
        },
        metrics=[
            Metric(
                "billing_line_count",
                op="count",
                field="product_name",
                label="Billing lines",
            ),
            Metric(
                "gross_revenue",
                op="sum",
                field="total_amount_cents",
                label="Gross revenue",
            ),
            Metric(
                "pretax_revenue",
                op="sum",
                field="pretax_amount_cents",
                label="Pre-tax revenue",
            ),
            Metric("tax_collected", op="sum", field="tax_cents", label="Tax collected"),
        ],
        base_queryset=queryset_for_permission(
            BillingLine, StaffGrant.BILLING_REPORTS_VIEW
        ),
    )

    register(
        model=PaymentAttempt,
        name="payment_attempts",
        label="Payment attempts",
        description="Tenant-scoped payment attempts with processor fields omitted.",
        default_date_field="created_at",
        fields={
            "payment_id": {"label": "Payment ID", "llm_visible": False},
            "created_at": {"label": "Created date"},
            "status": {"label": "Payment status"},
            "billing_document.status": {"label": "Billing status"},
            "amount_cents": {
                "label": "Amount in cents",
                "metric": True,
                "requires_permission": StaffGrant.PAYMENT_REPORTS_VIEW,
            },
            "amount_refunded_cents": {
                "label": "Refunded amount in cents",
                "metric": True,
                "requires_permission": StaffGrant.PAYMENT_REPORTS_VIEW,
            },
            "refunded": {"label": "Refunded"},
        },
        metrics=[
            Metric("payment_count", op="count", field="status", label="Payments"),
            Metric(
                "payment_amount", op="sum", field="amount_cents", label="Payment amount"
            ),
            Metric(
                "refunded_amount",
                op="sum",
                field="amount_refunded_cents",
                label="Refunded amount",
            ),
        ],
        base_queryset=queryset_for_permission(
            PaymentAttempt, StaffGrant.PAYMENT_REPORTS_VIEW
        ),
    )


def register_schedule_resources() -> None:
    """Register schedule/session resources."""

    register(
        model=ScheduleSession,
        name="schedule_sessions",
        label="Schedule sessions",
        description="Tenant-scoped scheduled sessions/classes.",
        default_date_field="start_date",
        fields={
            "session_id": {"label": "Session ID", "llm_visible": False},
            "start_date": {"label": "Start date"},
            "start_time": {"label": "Start time"},
            "duration_minutes": {"label": "Duration minutes", "metric": True},
            "capacity": {"label": "Capacity", "metric": True},
            "waitlist_limit": {"label": "Waitlist limit", "metric": True},
            "session_type.name": {"label": "Session type"},
            "location.name": {"label": "Location"},
        },
        metrics=[
            Metric("session_count", op="count", field="start_date", label="Sessions"),
            Metric(
                "total_capacity", op="sum", field="capacity", label="Total capacity"
            ),
            Metric(
                "average_duration",
                op="avg",
                field="duration_minutes",
                label="Average duration",
            ),
        ],
        base_queryset=queryset_for_permission(
            ScheduleSession, StaffGrant.SCHEDULE_REPORTS_VIEW
        ),
    )


def queryset_for_permission(
    model: type[Model],
    permission_name: str,
) -> Callable[[Any], QuerySet]:
    """Return a base queryset hook scoped to facilities granting a permission."""

    def base_queryset(request: Any) -> QuerySet:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return model.objects.none()
        if getattr(user, "is_superuser", False):
            return model.objects.all()
        facility_ids = permitted_facility_ids(user, permission_name)
        filter_key = "id__in" if model is Facility else "facility_id__in"
        return model.objects.filter(**{filter_key: facility_ids})

    return base_queryset


def permitted_facility_ids(user: Any, permission_name: str) -> QuerySet:
    """Return facility IDs where a user has an active synthetic grant."""

    global_assignment = StaffAssignment.objects.filter(
        user=user,
        is_active=True,
        can_access_all_facilities=True,
    ).first()
    if global_assignment is not None:
        return Facility.objects.values("id")

    owner_facility_ids = StaffAssignment.objects.filter(
        user=user,
        is_active=True,
        role=StaffAssignment.Role.OWNER,
    ).values("facility_id")
    grant_facility_ids = StaffAssignment.objects.filter(
        user=user,
        is_active=True,
        grants__name=permission_name,
    ).values("facility_id")
    return owner_facility_ids.union(grant_facility_ids)

"""AskLens registrations for the complex runnable test project."""

from collections.abc import Callable, Iterable
from typing import Any

from django.db.models import Model, Q, QuerySet

from django_asklens import Metric, register
from django_asklens.catalog.registry import default_registry
from django_asklens.exceptions import UnknownResourceError
from tests.test_project.models import (
    BillingDocument,
    BillingLine,
    Facility,
    Lead,
    MarketingCampaign,
    MemberProfile,
    MemberStatus,
    MemberSubscription,
    PaymentAttempt,
    ScheduleSession,
    SessionBooking,
    StaffAssignment,
    StaffGrant,
    StaffShift,
    SupportTicket,
)


def semantic_field(
    binding: str,
    field_type: str,
    *,
    nullable: bool,
    **metadata: object,
) -> dict[str, object]:
    """Build explicit test-project field metadata without binding inference."""

    return {
        "binding": binding,
        "type": field_type,
        "nullable": nullable,
        **metadata,
    }


def explicit_enum_field(
    binding: str,
    choices: Iterable[tuple[str | int, object]],
    *,
    nullable: bool,
    **metadata: object,
) -> dict[str, object]:
    """Opt explicitly into safe enum metadata for a reviewed Django choice set."""

    values = []
    for value, label in choices:
        item: dict[str, object] = {"value": value, "label": str(label)}
        aliases = []
        for candidate in (str(label), str(value).casefold()):
            if candidate != value and candidate not in aliases:
                aliases.append(candidate)
        if aliases:
            item["aliases"] = aliases
        values.append(item)
    underlying_type = (
        "integer"
        if all(
            isinstance(item["value"], int) and not isinstance(item["value"], bool)
            for item in values
        )
        else "string"
    )
    return semantic_field(
        binding,
        "enum",
        nullable=nullable,
        enum={"type": underlying_type, "values": values},
        **metadata,
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
    register_staff_resources()
    register_member_resources()
    register_billing_resources()
    register_growth_resources()
    register_schedule_resources()
    register_support_resources()


def register_facilities() -> None:
    """Register tenant/facility metadata."""

    register(
        model=Facility,
        name="facilities",
        label="Facilities",
        description="Facilities visible to the current reporting user.",
        default_date_field="created_at",
        fields={
            "id": semantic_field(
                "id", "integer", nullable=False, label="Facility ID", llm_visible=False
            ),
            "name": semantic_field(
                "name",
                "string",
                nullable=False,
                label="Facility name",
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "slug": semantic_field(
                "slug",
                "string",
                nullable=False,
                label="Facility slug",
                sensitive=True,
                result_visible=True,
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "facility_type": explicit_enum_field(
                "facility_type",
                Facility.FacilityType.choices,
                nullable=False,
                label="Facility type",
            ),
            "timezone": semantic_field(
                "timezone", "string", nullable=False, label="Timezone"
            ),
            "is_active": semantic_field(
                "is_active", "boolean", nullable=False, label="Active"
            ),
            "created_at": semantic_field(
                "created_at", "datetime", nullable=False, label="Created date"
            ),
        },
        metrics=[
            Metric(
                "facility_count",
                op="count",
                binding="name",
                result_type="integer",
                label="Facilities",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(Facility, StaffGrant.FACILITY_VIEW),
        requires_permission=StaffGrant.FACILITY_VIEW,
        scope_resource=True,
    )


def register_staff_resources() -> None:
    """Register owner-specific facility staff resources."""

    register(
        model=StaffAssignment,
        name="facility_owners",
        label="Facility owners",
        description=(
            "Tenant-scoped active facility owner assignments. Use this resource "
            "for questions about facility owner names."
        ),
        default_date_field="created_at",
        fields={
            "id": semantic_field(
                "id",
                "integer",
                nullable=False,
                label="Assignment ID",
                llm_visible=False,
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "user.first_name": semantic_field(
                "user__first_name", "string", nullable=False, label="Owner first name"
            ),
            "user.last_name": semantic_field(
                "user__last_name", "string", nullable=False, label="Owner last name"
            ),
            "user.username": semantic_field(
                "user__username", "string", nullable=False, label="Owner username"
            ),
            "user.email": semantic_field(
                "user__email",
                "string",
                nullable=False,
                label="Owner email",
                sensitive=True,
                result_visible=True,
                requires_permission=StaffGrant.STAFF_PII_VIEW,
            ),
            "is_primary": semantic_field(
                "is_primary",
                "boolean",
                nullable=False,
                label="Primary owner assignment",
            ),
            "created_at": semantic_field(
                "created_at", "datetime", nullable=False, label="Created date"
            ),
        },
        metrics=[
            Metric(
                "facility_owner_count",
                op="count",
                binding="user__username",
                result_type="integer",
                label="Facility owners",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=owner_queryset_for_permission(StaffGrant.FACILITY_VIEW),
        requires_permission=StaffGrant.FACILITY_VIEW,
        examples_enabled=False,
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
            "member_id": semantic_field(
                "member_id",
                "uuid",
                nullable=False,
                label="Member ID",
                llm_visible=False,
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "gender": explicit_enum_field(
                "gender", MemberProfile.Gender.choices, nullable=False, label="Gender"
            ),
            "member_since": semantic_field(
                "member_since", "datetime", nullable=True, label="Member since"
            ),
            "created_at": semantic_field(
                "created_at", "datetime", nullable=False, label="Created date"
            ),
            "created_via_portal": semantic_field(
                "created_via_portal",
                "boolean",
                nullable=False,
                label="Created via portal",
            ),
        },
        metrics=[
            Metric(
                "member_count",
                op="count",
                binding="gender",
                result_type="integer",
                label="Members",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            MemberProfile, StaffGrant.MEMBER_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.MEMBER_REPORTS_VIEW,
    )

    register(
        model=MemberProfile,
        name="member_contacts",
        label="Member contacts",
        description="Permission-scoped member contact details for approved facilities.",
        default_date_field="member_since",
        fields={
            "member_id": semantic_field(
                "member_id",
                "uuid",
                nullable=False,
                label="Member ID",
                llm_visible=False,
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "first_name": semantic_field(
                "first_name",
                "string",
                nullable=False,
                label="First name",
                sensitive=True,
                result_visible=True,
                requires_permission=StaffGrant.MEMBER_PII_VIEW,
            ),
            "last_name": semantic_field(
                "last_name",
                "string",
                nullable=False,
                label="Last name",
                sensitive=True,
                result_visible=True,
                requires_permission=StaffGrant.MEMBER_PII_VIEW,
            ),
            "email": semantic_field(
                "email",
                "string",
                nullable=False,
                label="Email",
                sensitive=True,
                result_visible=True,
                requires_permission=StaffGrant.MEMBER_PII_VIEW,
            ),
            "phone": semantic_field(
                "phone",
                "string",
                nullable=False,
                label="Phone",
                sensitive=True,
                result_visible=False,
                requires_permission=StaffGrant.MEMBER_PII_VIEW,
            ),
            "date_of_birth": semantic_field(
                "date_of_birth",
                "date",
                nullable=True,
                label="Date of birth",
                sensitive=True,
                result_visible=False,
                requires_permission=StaffGrant.MEMBER_PII_VIEW,
            ),
            "member_since": semantic_field(
                "member_since", "datetime", nullable=True, label="Member since"
            ),
        },
        metrics=[
            Metric(
                "contact_count",
                op="count",
                binding="member_id",
                result_type="integer",
                label="Contacts",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            MemberProfile, StaffGrant.MEMBER_PII_VIEW
        ),
        requires_permission=StaffGrant.MEMBER_PII_VIEW,
    )

    register(
        model=MemberStatus,
        name="member_statuses",
        label="Member statuses",
        description="Tenant-scoped member status history.",
        default_date_field="start_date",
        fields={
            "status_id": semantic_field(
                "status_id",
                "uuid",
                nullable=False,
                label="Status ID",
                llm_visible=False,
            ),
            "status": explicit_enum_field(
                "status", MemberStatus.Status.choices, nullable=False, label="Status"
            ),
            "start_date": semantic_field(
                "start_date", "datetime", nullable=False, label="Start date"
            ),
            "end_date": semantic_field(
                "end_date", "datetime", nullable=True, label="End date"
            ),
            "member.member_since": semantic_field(
                "member__member_since", "datetime", nullable=True, label="Member since"
            ),
        },
        metrics=[
            Metric(
                "status_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Statuses",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            MemberStatus, StaffGrant.MEMBER_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.MEMBER_REPORTS_VIEW,
    )

    register(
        model=MemberSubscription,
        name="member_subscriptions",
        label="Member subscriptions",
        description="Purchased subscription/package facts scoped by facility grants.",
        default_date_field="start_date",
        fields={
            "subscription_id": semantic_field(
                "subscription_id",
                "uuid",
                nullable=False,
                label="Subscription ID",
                llm_visible=False,
            ),
            "status": explicit_enum_field(
                "status",
                MemberSubscription.Status.choices,
                nullable=False,
                label="Status",
            ),
            "start_date": semantic_field(
                "start_date", "datetime", nullable=False, label="Start date"
            ),
            "end_date": semantic_field(
                "end_date", "datetime", nullable=False, label="End date"
            ),
            "billing_start_date": semantic_field(
                "billing_start_date",
                "datetime",
                nullable=False,
                label="Billing start date",
            ),
            "cancellation_date": semantic_field(
                "cancellation_date",
                "datetime",
                nullable=True,
                label="Cancellation date",
            ),
            "auto_renew": semantic_field(
                "auto_renew", "boolean", nullable=False, label="Auto-renew"
            ),
            "auto_pay": semantic_field(
                "auto_pay", "boolean", nullable=False, label="Auto-pay"
            ),
            "is_prorated": semantic_field(
                "is_prorated", "boolean", nullable=False, label="Prorated"
            ),
            "plan.name": semantic_field(
                "plan__name", "string", nullable=False, label="Plan"
            ),
            "plan.sales_status": semantic_field(
                "plan__sales_status",
                "string",
                nullable=False,
                label="Plan sales status",
            ),
        },
        metrics=[
            Metric(
                "subscription_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Subscriptions",
            )
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            MemberSubscription,
            StaffGrant.PACKAGE_REPORTS_VIEW,
        ),
        requires_permission=StaffGrant.PACKAGE_REPORTS_VIEW,
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
            "line_id": semantic_field(
                "line_id",
                "uuid",
                nullable=False,
                label="Billing line ID",
                llm_visible=False,
            ),
            "billing_document.paid_at": semantic_field(
                "billing_document__paid_at",
                "datetime",
                nullable=True,
                label="Paid date",
            ),
            "billing_document.due_date": semantic_field(
                "billing_document__due_date",
                "datetime",
                nullable=False,
                label="Due date",
            ),
            "billing_document.status": explicit_enum_field(
                "billing_document__status",
                BillingDocument.Status.choices,
                nullable=False,
                label="Billing status",
            ),
            "product_name": semantic_field(
                "product_name", "string", nullable=False, label="Product"
            ),
            "plan.name": semantic_field(
                "plan__name", "string", nullable=True, label="Plan"
            ),
            "quantity": semantic_field(
                "quantity", "integer", nullable=False, label="Quantity"
            ),
            "item_price_cents": semantic_field(
                "item_price_cents",
                "integer",
                nullable=False,
                label="Item price in cents",
                requires_permission=StaffGrant.BILLING_REPORTS_VIEW,
            ),
            "pretax_amount_cents": semantic_field(
                "pretax_amount_cents",
                "integer",
                nullable=False,
                label="Pre-tax amount in cents",
                requires_permission=StaffGrant.BILLING_REPORTS_VIEW,
            ),
            "tax_cents": semantic_field(
                "tax_cents",
                "integer",
                nullable=False,
                label="Tax in cents",
                requires_permission=StaffGrant.BILLING_REPORTS_VIEW,
            ),
            "total_amount_cents": semantic_field(
                "total_amount_cents",
                "integer",
                nullable=False,
                label="Total amount in cents",
                requires_permission=StaffGrant.BILLING_REPORTS_VIEW,
            ),
        },
        metrics=[
            Metric(
                "billing_line_count",
                op="count",
                binding="product_name",
                result_type="integer",
                label="Billing lines",
            ),
            Metric(
                "gross_revenue",
                op="sum",
                binding="total_amount_cents",
                result_type="integer",
                label="Gross revenue",
            ),
            Metric(
                "pretax_revenue",
                op="sum",
                binding="pretax_amount_cents",
                result_type="integer",
                label="Pre-tax revenue",
            ),
            Metric(
                "tax_collected",
                op="sum",
                binding="tax_cents",
                result_type="integer",
                label="Tax collected",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            BillingLine, StaffGrant.BILLING_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.BILLING_REPORTS_VIEW,
    )

    register(
        model=PaymentAttempt,
        name="payment_attempts",
        label="Payment attempts",
        description="Tenant-scoped payment attempts with processor fields omitted.",
        default_date_field="created_at",
        fields={
            "payment_id": semantic_field(
                "payment_id",
                "uuid",
                nullable=False,
                label="Payment ID",
                llm_visible=False,
            ),
            "created_at": semantic_field(
                "created_at", "datetime", nullable=False, label="Created date"
            ),
            "status": explicit_enum_field(
                "status",
                PaymentAttempt.Status.choices,
                nullable=False,
                label="Payment status",
            ),
            "billing_document.status": explicit_enum_field(
                "billing_document__status",
                BillingDocument.Status.choices,
                nullable=False,
                label="Billing status",
            ),
            "amount_cents": semantic_field(
                "amount_cents",
                "integer",
                nullable=False,
                label="Amount in cents",
                requires_permission=StaffGrant.PAYMENT_REPORTS_VIEW,
            ),
            "amount_refunded_cents": semantic_field(
                "amount_refunded_cents",
                "integer",
                nullable=False,
                label="Refunded amount in cents",
                requires_permission=StaffGrant.PAYMENT_REPORTS_VIEW,
            ),
            "refunded": semantic_field(
                "refunded", "boolean", nullable=False, label="Refunded"
            ),
        },
        metrics=[
            Metric(
                "payment_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Payments",
            ),
            Metric(
                "payment_amount",
                op="sum",
                binding="amount_cents",
                result_type="integer",
                label="Payment amount",
            ),
            Metric(
                "refunded_amount",
                op="sum",
                binding="amount_refunded_cents",
                result_type="integer",
                label="Refunded amount",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            PaymentAttempt, StaffGrant.PAYMENT_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.PAYMENT_REPORTS_VIEW,
    )


def register_growth_resources() -> None:
    """Register marketing and lead pipeline resources."""

    register(
        model=MarketingCampaign,
        name="marketing_campaigns",
        label="Marketing campaigns",
        description="Tenant-scoped marketing campaign performance.",
        default_date_field="start_date",
        fields={
            "campaign_id": semantic_field(
                "campaign_id",
                "uuid",
                nullable=False,
                label="Campaign ID",
                llm_visible=False,
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.ANALYTICS_VIEW,
            ),
            "name": semantic_field("name", "string", nullable=False, label="Campaign"),
            "channel": explicit_enum_field(
                "channel",
                MarketingCampaign.Channel.choices,
                nullable=False,
                label="Channel",
            ),
            "audience": explicit_enum_field(
                "audience",
                MarketingCampaign.Audience.choices,
                nullable=False,
                label="Audience",
            ),
            "status": explicit_enum_field(
                "status",
                MarketingCampaign.Status.choices,
                nullable=False,
                label="Status",
            ),
            "start_date": semantic_field(
                "start_date", "date", nullable=False, label="Start date"
            ),
            "end_date": semantic_field(
                "end_date", "date", nullable=True, label="End date"
            ),
            "budget_cents": semantic_field(
                "budget_cents",
                "integer",
                nullable=False,
                label="Budget in cents",
            ),
            "spend_cents": semantic_field(
                "spend_cents",
                "integer",
                nullable=False,
                label="Spend in cents",
            ),
            "impressions": semantic_field(
                "impressions",
                "integer",
                nullable=False,
                label="Impressions",
            ),
            "clicks": semantic_field(
                "clicks", "integer", nullable=False, label="Clicks"
            ),
            "conversions": semantic_field(
                "conversions",
                "integer",
                nullable=False,
                label="Conversions",
            ),
        },
        metrics=[
            Metric(
                "campaign_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Campaigns",
            ),
            Metric(
                "marketing_budget",
                op="sum",
                binding="budget_cents",
                result_type="integer",
                label="Marketing budget",
            ),
            Metric(
                "marketing_spend",
                op="sum",
                binding="spend_cents",
                result_type="integer",
                label="Marketing spend",
            ),
            Metric(
                "total_impressions",
                op="sum",
                binding="impressions",
                result_type="integer",
                label="Impressions",
            ),
            Metric(
                "total_clicks",
                op="sum",
                binding="clicks",
                result_type="integer",
                label="Clicks",
            ),
            Metric(
                "total_conversions",
                op="sum",
                binding="conversions",
                result_type="integer",
                label="Conversions",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            MarketingCampaign, StaffGrant.ANALYTICS_VIEW
        ),
        requires_permission=StaffGrant.ANALYTICS_VIEW,
    )

    register(
        model=Lead,
        name="leads",
        label="Leads",
        description="Tenant-scoped lead funnel facts without contact PII.",
        default_date_field="inquiry_date",
        fields={
            "lead_id": semantic_field(
                "lead_id", "uuid", nullable=False, label="Lead ID", llm_visible=False
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "campaign.name": semantic_field(
                "campaign__name", "string", nullable=True, label="Campaign"
            ),
            "source": explicit_enum_field(
                "source", Lead.Source.choices, nullable=False, label="Lead source"
            ),
            "stage": explicit_enum_field(
                "stage", Lead.Stage.choices, nullable=False, label="Lead stage"
            ),
            "status": explicit_enum_field(
                "status", Lead.Status.choices, nullable=False, label="Lead status"
            ),
            "inquiry_date": semantic_field(
                "inquiry_date", "datetime", nullable=False, label="Inquiry date"
            ),
            "trial_date": semantic_field(
                "trial_date", "datetime", nullable=True, label="Trial date"
            ),
            "converted_at": semantic_field(
                "converted_at", "datetime", nullable=True, label="Converted date"
            ),
            "estimated_value_cents": semantic_field(
                "estimated_value_cents",
                "integer",
                nullable=False,
                label="Estimated value in cents",
            ),
        },
        metrics=[
            Metric(
                "lead_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Leads",
            ),
            Metric(
                "pipeline_value",
                op="sum",
                binding="estimated_value_cents",
                result_type="integer",
                label="Pipeline value",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(Lead, StaffGrant.MEMBER_REPORTS_VIEW),
        requires_permission=StaffGrant.MEMBER_REPORTS_VIEW,
    )


def register_schedule_resources() -> None:
    """Register schedule/session resources."""

    register(
        model=StaffShift,
        name="staff_shifts",
        label="Staff shifts",
        description="Tenant-scoped staff schedule and labor coverage.",
        default_date_field="start_at",
        fields={
            "shift_id": semantic_field(
                "shift_id", "uuid", nullable=False, label="Shift ID", llm_visible=False
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.FACILITY_VIEW,
            ),
            "staff_user.username": semantic_field(
                "staff_user__username", "string", nullable=False, label="Staff username"
            ),
            "location.name": semantic_field(
                "location__name", "string", nullable=True, label="Location"
            ),
            "role": explicit_enum_field(
                "role", StaffShift.Role.choices, nullable=False, label="Role"
            ),
            "status": explicit_enum_field(
                "status",
                StaffShift.Status.choices,
                nullable=False,
                label="Shift status",
            ),
            "start_at": semantic_field(
                "start_at", "datetime", nullable=False, label="Start time"
            ),
            "end_at": semantic_field(
                "end_at", "datetime", nullable=False, label="End time"
            ),
            "planned_minutes": semantic_field(
                "planned_minutes",
                "integer",
                nullable=False,
                label="Planned minutes",
            ),
            "actual_minutes": semantic_field(
                "actual_minutes",
                "integer",
                nullable=False,
                label="Actual minutes",
            ),
            "labor_cost_cents": semantic_field(
                "labor_cost_cents",
                "integer",
                nullable=False,
                label="Labor cost in cents",
            ),
        },
        metrics=[
            Metric(
                "shift_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Shifts",
            ),
            Metric(
                "planned_minutes",
                op="sum",
                binding="planned_minutes",
                result_type="integer",
                label="Planned minutes",
            ),
            Metric(
                "actual_minutes",
                op="sum",
                binding="actual_minutes",
                result_type="integer",
                label="Actual minutes",
            ),
            Metric(
                "labor_cost",
                op="sum",
                binding="labor_cost_cents",
                result_type="integer",
                label="Labor cost",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            StaffShift, StaffGrant.SCHEDULE_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.SCHEDULE_REPORTS_VIEW,
    )

    register(
        model=ScheduleSession,
        name="schedule_sessions",
        label="Schedule sessions",
        description="Tenant-scoped scheduled sessions/classes.",
        default_date_field="start_date",
        fields={
            "session_id": semantic_field(
                "session_id",
                "uuid",
                nullable=False,
                label="Session ID",
                llm_visible=False,
            ),
            "start_date": semantic_field(
                "start_date", "date", nullable=False, label="Start date"
            ),
            "start_time": semantic_field(
                "start_time", "time", nullable=False, label="Start time"
            ),
            "duration_minutes": semantic_field(
                "duration_minutes",
                "integer",
                nullable=False,
                label="Duration minutes",
            ),
            "capacity": semantic_field(
                "capacity", "integer", nullable=False, label="Capacity"
            ),
            "waitlist_limit": semantic_field(
                "waitlist_limit",
                "integer",
                nullable=True,
                label="Waitlist limit",
            ),
            "session_type.name": semantic_field(
                "session_type__name", "string", nullable=False, label="Session type"
            ),
            "location.name": semantic_field(
                "location__name", "string", nullable=True, label="Location"
            ),
        },
        metrics=[
            Metric(
                "session_count",
                op="count",
                binding="start_date",
                result_type="integer",
                label="Sessions",
            ),
            Metric(
                "total_capacity",
                op="sum",
                binding="capacity",
                result_type="integer",
                label="Total capacity",
            ),
            Metric(
                "average_duration",
                op="avg",
                binding="duration_minutes",
                result_type="float",
                label="Average duration",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            ScheduleSession, StaffGrant.SCHEDULE_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.SCHEDULE_REPORTS_VIEW,
    )

    register(
        model=SessionBooking,
        name="session_bookings",
        label="Session bookings",
        description=(
            "Tenant-scoped booking and attendance facts for scheduled sessions."
        ),
        default_date_field="booked_at",
        fields={
            "booking_id": semantic_field(
                "booking_id",
                "uuid",
                nullable=False,
                label="Booking ID",
                llm_visible=False,
            ),
            "booked_at": semantic_field(
                "booked_at", "datetime", nullable=False, label="Booked date"
            ),
            "checked_in_at": semantic_field(
                "checked_in_at", "datetime", nullable=True, label="Check-in date"
            ),
            "canceled_at": semantic_field(
                "canceled_at", "datetime", nullable=True, label="Canceled date"
            ),
            "status": explicit_enum_field(
                "status",
                SessionBooking.Status.choices,
                nullable=False,
                label="Booking status",
            ),
            "source": explicit_enum_field(
                "source",
                SessionBooking.Source.choices,
                nullable=False,
                label="Booking source",
            ),
            "party_size": semantic_field(
                "party_size", "integer", nullable=False, label="Party size"
            ),
            "price_cents": semantic_field(
                "price_cents",
                "integer",
                nullable=False,
                label="Booking price in cents",
            ),
            "session.start_date": semantic_field(
                "session__start_date", "date", nullable=False, label="Session date"
            ),
            "session.session_type.name": semantic_field(
                "session__session_type__name",
                "string",
                nullable=False,
                label="Session type",
            ),
            "session.location.name": semantic_field(
                "session__location__name", "string", nullable=True, label="Location"
            ),
        },
        metrics=[
            Metric(
                "booking_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Bookings",
            ),
            Metric(
                "total_party_size",
                op="sum",
                binding="party_size",
                result_type="integer",
                label="Party size",
            ),
            Metric(
                "booking_revenue",
                op="sum",
                binding="price_cents",
                result_type="integer",
                label="Booking revenue",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            SessionBooking, StaffGrant.SCHEDULE_REPORTS_VIEW
        ),
        requires_permission=StaffGrant.SCHEDULE_REPORTS_VIEW,
    )


def register_support_resources() -> None:
    """Register support/operations resources."""

    register(
        model=SupportTicket,
        name="support_tickets",
        label="Support tickets",
        description="Tenant-scoped support ticket volume and resolution facts.",
        default_date_field="opened_at",
        fields={
            "ticket_id": semantic_field(
                "ticket_id",
                "uuid",
                nullable=False,
                label="Ticket ID",
                llm_visible=False,
            ),
            "facility.name": semantic_field(
                "facility__name",
                "string",
                nullable=False,
                label="Facility",
                scope_dimension=True,
                requires_permission=StaffGrant.ANALYTICS_VIEW,
            ),
            "category": explicit_enum_field(
                "category",
                SupportTicket.Category.choices,
                nullable=False,
                label="Category",
            ),
            "priority": explicit_enum_field(
                "priority",
                SupportTicket.Priority.choices,
                nullable=False,
                label="Priority",
            ),
            "status": explicit_enum_field(
                "status",
                SupportTicket.Status.choices,
                nullable=False,
                label="Ticket status",
            ),
            "channel": explicit_enum_field(
                "channel",
                SupportTicket.Channel.choices,
                nullable=False,
                label="Channel",
            ),
            "opened_at": semantic_field(
                "opened_at", "datetime", nullable=False, label="Opened date"
            ),
            "first_response_at": semantic_field(
                "first_response_at",
                "datetime",
                nullable=True,
                label="First response date",
            ),
            "resolved_at": semantic_field(
                "resolved_at", "datetime", nullable=True, label="Resolved date"
            ),
            "satisfaction_score": semantic_field(
                "satisfaction_score",
                "integer",
                nullable=True,
                label="Satisfaction score",
            ),
            "messages_count": semantic_field(
                "messages_count",
                "integer",
                nullable=False,
                label="Message count",
            ),
        },
        metrics=[
            Metric(
                "ticket_count",
                op="count",
                binding="status",
                result_type="integer",
                label="Tickets",
            ),
            Metric(
                "message_count",
                op="sum",
                binding="messages_count",
                result_type="integer",
                label="Messages",
            ),
            Metric(
                "average_satisfaction",
                op="avg",
                binding="satisfaction_score",
                result_type="float",
                label="Average satisfaction",
            ),
        ],
        scope_mode="context_scoped",
        scope_provider=queryset_for_permission(
            SupportTicket, StaffGrant.ANALYTICS_VIEW
        ),
        requires_permission=StaffGrant.ANALYTICS_VIEW,
    )


def owner_queryset_for_permission(permission_name: str) -> Callable[[Any], QuerySet]:
    """Return active owner assignments scoped by a facility permission."""

    def scope_provider(request: Any) -> QuerySet:
        return queryset_for_permission(StaffAssignment, permission_name)(
            request
        ).filter(
            role=StaffAssignment.Role.OWNER,
            is_active=True,
        )

    return scope_provider


def queryset_for_permission(
    model: type[Model],
    permission_name: str,
) -> Callable[[Any], QuerySet]:
    """Return a scope provider limited to facilities granting a permission."""

    def scope_provider(request: Any) -> QuerySet:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return model.objects.none()
        if getattr(user, "is_superuser", False):
            return model.objects.all()
        facility_ids = permitted_facility_ids(user, permission_name)
        filter_key = "id__in" if model is Facility else "facility_id__in"
        return model.objects.filter(**{filter_key: facility_ids})

    return scope_provider


def permitted_facility_ids(user: Any, permission_name: str) -> QuerySet:
    """Return facility IDs where a user has an active synthetic grant."""

    has_global_grant = StaffAssignment.objects.filter(
        Q(role=StaffAssignment.Role.OWNER) | Q(grants__name=permission_name),
        user=user,
        is_active=True,
        can_access_all_facilities=True,
    ).exists()
    if has_global_grant:
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

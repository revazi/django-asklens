"""Admin registrations for the runnable AskLens test project."""

from django.contrib import admin

from tests.test_project.models import (
    Account,
    AccountMembership,
    BillingDocument,
    BillingLine,
    Customer,
    Facility,
    FacilityLocation,
    Lead,
    MarketingCampaign,
    MemberProfile,
    MemberStatus,
    MemberSubscription,
    Order,
    PaymentAttempt,
    ScheduleSession,
    SessionBooking,
    SessionType,
    StaffAssignment,
    StaffGrant,
    StaffShift,
    SubscriptionPlan,
    SupportTicket,
)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    """Admin for tenant facilities."""

    list_display = ("name", "slug", "facility_type", "timezone", "is_active")
    search_fields = ("name", "slug")
    list_filter = ("facility_type", "is_active")


class StaffGrantInline(admin.TabularInline):
    """Inline staff grants for a facility assignment."""

    model = StaffGrant
    extra = 1


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(admin.ModelAdmin):
    """Admin for tenant-scoped staff assignments."""

    inlines = [StaffGrantInline]
    list_display = (
        "user",
        "facility",
        "role",
        "is_active",
        "can_access_all_facilities",
    )
    list_filter = ("role", "is_active", "can_access_all_facilities")
    search_fields = ("user__username", "facility__name", "facility__slug")


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    """Admin for synthetic member profiles."""

    list_display = (
        "full_name",
        "facility",
        "email",
        "member_since",
        "created_via_portal",
    )
    list_filter = ("facility", "gender", "created_via_portal")
    search_fields = ("first_name", "last_name", "email", "facility__name")


@admin.register(MemberStatus)
class MemberStatusAdmin(admin.ModelAdmin):
    """Admin for member status history."""

    list_display = ("member", "facility", "status", "start_date", "end_date")
    list_filter = ("facility", "status")
    search_fields = ("member__first_name", "member__last_name", "member__email")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin for subscription plans."""

    list_display = (
        "name",
        "facility",
        "sales_status",
        "auto_renew",
        "member_sales_enabled",
    )
    list_filter = ("facility", "sales_status", "auto_renew", "member_sales_enabled")
    search_fields = ("name", "facility__name")


@admin.register(MemberSubscription)
class MemberSubscriptionAdmin(admin.ModelAdmin):
    """Admin for member subscriptions."""

    list_display = ("member", "plan", "facility", "status", "start_date", "end_date")
    list_filter = ("facility", "status", "auto_renew", "auto_pay")
    search_fields = ("member__first_name", "member__last_name", "plan__name")


class BillingLineInline(admin.TabularInline):
    """Inline billing lines for a billing document."""

    model = BillingLine
    extra = 1


@admin.register(BillingDocument)
class BillingDocumentAdmin(admin.ModelAdmin):
    """Admin for billing documents."""

    inlines = [BillingLineInline]
    list_display = (
        "document_id",
        "facility",
        "member",
        "status",
        "due_date",
        "paid_at",
    )
    list_filter = ("facility", "status", "auto_pay")
    search_fields = (
        "document_id",
        "member__first_name",
        "member__last_name",
        "member__email",
    )


@admin.register(BillingLine)
class BillingLineAdmin(admin.ModelAdmin):
    """Admin for billing line items."""

    list_display = (
        "product_name",
        "facility",
        "billing_document",
        "quantity",
        "total_amount_cents",
    )
    list_filter = ("facility", "product_name")
    search_fields = ("product_name", "billing_document__document_id")


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    """Admin for payment attempts."""

    list_display = (
        "payment_id",
        "facility",
        "billing_document",
        "status",
        "amount_cents",
        "refunded",
    )
    list_filter = ("facility", "status", "refunded")
    search_fields = ("payment_id", "billing_document__document_id", "member__email")


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    """Admin for marketing campaigns."""

    list_display = ("name", "facility", "channel", "audience", "status", "start_date")
    list_filter = ("facility", "channel", "audience", "status")
    search_fields = ("name", "facility__name")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Admin for synthetic lead pipeline rows."""

    list_display = ("email", "facility", "source", "stage", "status", "inquiry_date")
    list_filter = ("facility", "source", "stage", "status")
    search_fields = ("first_name", "last_name", "email", "facility__name")


@admin.register(FacilityLocation)
class FacilityLocationAdmin(admin.ModelAdmin):
    """Admin for facility locations."""

    list_display = ("name", "facility", "capacity", "is_active")
    list_filter = ("facility", "is_active")
    search_fields = ("name", "facility__name")


@admin.register(SessionType)
class SessionTypeAdmin(admin.ModelAdmin):
    """Admin for session types."""

    list_display = ("name", "facility", "is_bookable")
    list_filter = ("facility", "is_bookable")
    search_fields = ("name", "facility__name")


@admin.register(StaffShift)
class StaffShiftAdmin(admin.ModelAdmin):
    """Admin for staff shifts."""

    list_display = (
        "staff_user",
        "facility",
        "role",
        "status",
        "start_at",
        "actual_minutes",
    )
    list_filter = ("facility", "role", "status")
    search_fields = ("staff_user__username", "facility__name", "location__name")


@admin.register(ScheduleSession)
class ScheduleSessionAdmin(admin.ModelAdmin):
    """Admin for scheduled sessions."""

    list_display = (
        "session_type",
        "facility",
        "location",
        "start_date",
        "start_time",
        "capacity",
    )
    list_filter = ("facility", "session_type", "location")
    search_fields = ("session_type__name", "location__name", "facility__name")


@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    """Admin for session bookings and attendance."""

    list_display = ("session", "member", "facility", "status", "source", "party_size")
    list_filter = ("facility", "status", "source")
    search_fields = ("member__first_name", "member__last_name", "member__email")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Admin for support tickets."""

    list_display = ("facility", "category", "priority", "status", "opened_at")
    list_filter = ("facility", "category", "priority", "status", "channel")
    search_fields = ("member__first_name", "member__last_name", "member__email")


admin.site.register(Account)
admin.site.register(AccountMembership)
admin.site.register(Customer)
admin.site.register(Order)

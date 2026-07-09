"""Models used by Django AskLens tests and local demo project."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    """Abstract timestamped model for complex test-project fixtures."""

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Account(models.Model):
    """Tenant/account fixture model for API security tests."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        app_label = "test_project"


class AccountMembership(models.Model):
    """User-to-account membership fixture model for tenant scoping tests."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    role = models.CharField(max_length=32, default="member")

    class Meta:
        app_label = "test_project"
        unique_together = ("user", "account")


class Customer(models.Model):
    """Customer fixture model for catalog tests."""

    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        app_label = "test_project"


class Order(models.Model):
    """Order fixture model for catalog tests."""

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    internal_notes = models.TextField(blank=True)

    class Meta:
        app_label = "test_project"


class Facility(TimestampedModel):
    """Tenant fixture for complex permission and reporting tests."""

    class FacilityType(models.TextChoices):
        STUDIO = "studio", "Studio"
        CLINIC = "clinic", "Clinic"
        TRAINING_CENTER = "training_center", "Training center"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    facility_type = models.CharField(
        max_length=32,
        choices=FacilityType.choices,
        default=FacilityType.STUDIO,
    )
    timezone = models.CharField(max_length=64, default="UTC")
    notification_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "test_project"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class StaffAssignment(TimestampedModel):
    """User-to-facility role assignment fixture."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"
        SUPPORT = "support", "Support"
        MEMBER = "member", "Member"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name="staff_assignments",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.STAFF)
    is_primary = models.BooleanField(default=False)
    can_access_all_facilities = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "test_project"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "facility", "role"],
                name="unique_test_project_staff_assignment_role",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.facility} — {self.role}"


class StaffGrant(models.Model):
    """Tenant-scoped staff permission fixture."""

    ANALYTICS_VIEW = "AnalyticsView"
    BILLING_REPORTS_VIEW = "BillingReportsView"
    PAYMENT_REPORTS_VIEW = "PaymentReportsView"
    MEMBER_REPORTS_VIEW = "MemberReportsView"
    MEMBER_PII_VIEW = "MemberPIIView"
    PACKAGE_REPORTS_VIEW = "PackageReportsView"
    SCHEDULE_REPORTS_VIEW = "ScheduleReportsView"
    FACILITY_VIEW = "FacilityView"

    GRANT_CHOICES = (
        (ANALYTICS_VIEW, "Analytics view"),
        (BILLING_REPORTS_VIEW, "Billing reports view"),
        (PAYMENT_REPORTS_VIEW, "Payment reports view"),
        (MEMBER_REPORTS_VIEW, "Member reports view"),
        (MEMBER_PII_VIEW, "Member PII view"),
        (PACKAGE_REPORTS_VIEW, "Package reports view"),
        (SCHEDULE_REPORTS_VIEW, "Schedule reports view"),
        (FACILITY_VIEW, "Facility view"),
    )

    assignment = models.ForeignKey(
        StaffAssignment,
        on_delete=models.CASCADE,
        related_name="grants",
    )
    name = models.CharField(max_length=80, choices=GRANT_CHOICES)

    class Meta:
        app_label = "test_project"
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "name"],
                name="unique_test_project_staff_grant",
            )
        ]

    def __str__(self) -> str:
        return f"{self.assignment}: {self.name}"


class MemberProfile(TimestampedModel):
    """Tenant-scoped member/customer fixture with deliberately sensitive fields."""

    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        NON_BINARY = "non_binary", "Non-binary"
        NOT_PROVIDED = "not_provided", "Not provided"

    member_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="members"
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=32,
        choices=Gender.choices,
        default=Gender.NOT_PROVIDED,
    )
    member_since = models.DateTimeField(null=True, blank=True)
    created_via_portal = models.BooleanField(default=False)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)
    medical_notes = models.TextField(blank=True)
    external_profile_id = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = "test_project"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "email"],
                name="unique_test_project_member_email_per_facility",
            )
        ]
        ordering = ["facility__name", "last_name", "first_name"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self) -> str:
        return self.full_name


class MemberStatus(TimestampedModel):
    """Status history for a member profile."""

    class Status(models.TextChoices):
        PROSPECT = "Prospect", "Prospect"
        TRIAL = "Trial", "Trial"
        ACTIVE = "Active", "Active"
        NON_PAYING = "Non-Paying", "Non-paying"
        ALUMNI = "Alumni", "Alumni"

    status_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name="statuses",
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "test_project"
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.member} — {self.status}"


class SubscriptionPlan(TimestampedModel):
    """Tenant-scoped subscription/package fixture."""

    class SalesStatus(models.TextChoices):
        DISABLED = "disabled", "Disabled"
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    plan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="plans"
    )
    name = models.CharField(max_length=112)
    description = models.CharField(max_length=250, blank=True)
    auto_renew = models.BooleanField(default=False)
    allow_proration = models.BooleanField(default=False)
    sales_status = models.CharField(
        max_length=20,
        choices=SalesStatus.choices,
        default=SalesStatus.DISABLED,
    )
    member_sales_enabled = models.BooleanField(default=False)
    start_date = models.DateTimeField(null=True, blank=True)
    max_sales_allowed = models.IntegerField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "test_project"
        ordering = ["facility__name", "name"]

    def __str__(self) -> str:
        return self.name


class MemberSubscription(TimestampedModel):
    """Purchased member subscription fixture."""

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        ACTIVE = "ACTIVE", "Active"
        HOLD = "HOLD", "Hold"
        ENDED = "ENDED", "Ended"
        CANCELLED = "CANCELLED", "Cancelled"

    subscription_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.RESTRICT,
        related_name="subscriptions",
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    billing_start_date = models.DateTimeField()
    cancellation_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPCOMING
    )
    auto_renew = models.BooleanField(default=False)
    auto_pay = models.BooleanField(default=False)
    is_prorated = models.BooleanField(default=False)
    cancellation_reason = models.CharField(max_length=250, blank=True)
    parent = models.OneToOneField(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="renewal",
    )

    class Meta:
        app_label = "test_project"
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.member} — {self.plan} — {self.status}"


class BillingDocument(TimestampedModel):
    """Tenant-scoped billing document/invoice fixture."""

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        PAST_DUE = "PAST_DUE", "Past due"
        PAYMENT_FAILED = "PAYMENT_FAILED", "Payment failed"
        REFUNDED = "REFUNDED", "Refunded"
        VOID = "VOID", "Void"

    document_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="billing_documents"
    )
    member = models.ForeignKey(
        MemberProfile, on_delete=models.CASCADE, related_name="billing_documents"
    )
    subscription = models.ForeignKey(
        MemberSubscription,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="billing_documents",
    )
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.UPCOMING
    )
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    auto_pay = models.BooleanField(default=False)
    failure_code = models.CharField(max_length=64, blank=True)
    failure_message = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "test_project"
        ordering = ["-due_date"]

    def __str__(self) -> str:
        return f"{self.document_id} — {self.status}"


class BillingLine(TimestampedModel):
    """Line-item fixture with database fields suitable for aggregate metrics."""

    line_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    billing_document = models.ForeignKey(
        BillingDocument,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="billing_lines",
    )
    product_name = models.CharField(max_length=112)
    quantity = models.IntegerField(default=1)
    item_price_cents = models.IntegerField()
    pretax_amount_cents = models.IntegerField()
    tax_cents = models.IntegerField()
    total_amount_cents = models.IntegerField()

    class Meta:
        app_label = "test_project"
        ordering = ["billing_document__due_date", "product_name"]

    def __str__(self) -> str:
        return f"{self.product_name} — {self.total_amount_cents}"


class PaymentAttempt(TimestampedModel):
    """Payment attempt fixture with sensitive processor fields."""

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        REQUIRES_PAYMENT_METHOD = "requires_payment_method", "Requires payment method"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    billing_document = models.ForeignKey(
        BillingDocument,
        on_delete=models.RESTRICT,
        related_name="payment_attempts",
    )
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PROCESSING
    )
    amount_cents = models.IntegerField()
    amount_refunded_cents = models.IntegerField(default=0)
    refunded = models.BooleanField(default=False)
    processor_payment_id = models.CharField(max_length=255, blank=True)
    failure_code = models.CharField(max_length=64, blank=True)
    failure_message = models.TextField(blank=True)

    class Meta:
        app_label = "test_project"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.payment_id} — {self.status}"


class FacilityLocation(TimestampedModel):
    """Physical location fixture for schedule/session joins."""

    location_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(max_length=120)
    capacity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "test_project"
        ordering = ["facility__name", "name"]

    def __str__(self) -> str:
        return self.name


class SessionType(TimestampedModel):
    """Class/session type fixture."""

    session_type_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="session_types"
    )
    name = models.CharField(max_length=120)
    is_bookable = models.BooleanField(default=True)

    class Meta:
        app_label = "test_project"
        ordering = ["facility__name", "name"]

    def __str__(self) -> str:
        return self.name


class ScheduleSession(TimestampedModel):
    """Scheduled class/session fixture."""

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    session_type = models.ForeignKey(SessionType, on_delete=models.RESTRICT)
    location = models.ForeignKey(
        FacilityLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    start_date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.IntegerField()
    capacity = models.IntegerField()
    waitlist_limit = models.IntegerField(null=True, blank=True)
    reservation_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "test_project"
        ordering = ["start_date", "start_time"]

    def __str__(self) -> str:
        return f"{self.session_type} — {self.start_date} {self.start_time}"

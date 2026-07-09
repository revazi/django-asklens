"""Seed the runnable AskLens test project with synthetic complex data."""

from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tests.test_project.models import (
    BillingDocument,
    BillingLine,
    Facility,
    FacilityLocation,
    MemberProfile,
    MemberStatus,
    MemberSubscription,
    PaymentAttempt,
    ScheduleSession,
    SessionType,
    StaffAssignment,
    StaffGrant,
    SubscriptionPlan,
)

DEMO_PASSWORD = "12admin34"


def aware_datetime(year: int, month: int, day: int, hour: int = 12) -> datetime:
    """Return a timezone-aware datetime in the active timezone."""

    return timezone.make_aware(datetime(year, month, day, hour, 0, 0))


class Command(BaseCommand):
    """Create deterministic synthetic data for local admin/API exploration."""

    help = "Seed the runnable AskLens test project with synthetic complex data."

    def handle(self, *args, **options) -> None:
        """Seed users, tenants, grants, members, billing, payments, and sessions."""

        north = create_facility("North Studio", "north-studio")
        south = create_facility("South Studio", "south-studio")

        create_demo_user("admin", is_staff=True, is_superuser=True)
        owner = create_demo_user("facility-owner", is_staff=True)
        north_billing_user = create_demo_user("north-billing", is_staff=True)
        south_billing_user = create_demo_user("south-billing", is_staff=True)
        mixed_user = create_demo_user("mixed-reporter", is_staff=True)
        schedule_user = create_demo_user("schedule-reporter", is_staff=True)
        support_user = create_demo_user("support-reporter", is_staff=True)
        create_demo_user("no-report", is_staff=True)

        create_assignment(owner, north, StaffAssignment.Role.OWNER)
        create_assignment(owner, south, StaffAssignment.Role.OWNER)
        create_assignment(
            north_billing_user,
            north,
            StaffAssignment.Role.STAFF,
            StaffGrant.BILLING_REPORTS_VIEW,
            StaffGrant.PAYMENT_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            south_billing_user,
            south,
            StaffAssignment.Role.STAFF,
            StaffGrant.BILLING_REPORTS_VIEW,
            StaffGrant.PAYMENT_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            mixed_user,
            north,
            StaffAssignment.Role.STAFF,
            StaffGrant.MEMBER_REPORTS_VIEW,
            StaffGrant.MEMBER_PII_VIEW,
            StaffGrant.BILLING_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            mixed_user,
            south,
            StaffAssignment.Role.STAFF,
            StaffGrant.MEMBER_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            schedule_user,
            north,
            StaffAssignment.Role.STAFF,
            StaffGrant.SCHEDULE_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            schedule_user,
            south,
            StaffAssignment.Role.STAFF,
            StaffGrant.SCHEDULE_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            support_user,
            north,
            StaffAssignment.Role.SUPPORT,
            StaffGrant.ANALYTICS_VIEW,
            can_access_all_facilities=True,
        )

        seed_facility_data(
            north, "North", paid_amounts=(12000, 8000), failed_amount=4500
        )
        seed_facility_data(
            south, "South", paid_amounts=(22000, 6000), failed_amount=7000
        )

        self.stdout.write(
            self.style.SUCCESS("Seeded synthetic AskLens test-project data.")
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Created demo admin login admin / "
                f"{DEMO_PASSWORD} and staff demo users."
            )
        )


def create_demo_user(
    username: str,
    *,
    is_staff: bool = False,
    is_superuser: bool = False,
):
    """Create or update a login-capable synthetic demo user."""

    user_model = get_user_model()
    user, _created = user_model.objects.get_or_create(
        username=username,
        defaults={"email": f"{username}@example.test"},
    )
    user.email = f"{username}@example.test"
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.is_active = True
    user.set_password(DEMO_PASSWORD)
    user.save(
        update_fields=[
            "email",
            "is_staff",
            "is_superuser",
            "is_active",
            "password",
        ]
    )
    return user


def create_facility(name: str, slug: str) -> Facility:
    """Create or update a facility."""

    facility, _created = Facility.objects.update_or_create(
        slug=slug,
        defaults={
            "name": name,
            "facility_type": Facility.FacilityType.STUDIO,
            "timezone": "UTC",
            "notification_email": f"{slug}@example.test",
            "is_active": True,
        },
    )
    return facility


def create_assignment(
    user,
    facility: Facility,
    role: str,
    *grants: str,
    can_access_all_facilities: bool = False,
) -> StaffAssignment:
    """Create a synthetic staff assignment with grants."""

    assignment, _created = StaffAssignment.objects.update_or_create(
        user=user,
        facility=facility,
        role=role,
        defaults={
            "is_active": True,
            "can_access_all_facilities": can_access_all_facilities,
        },
    )
    for grant_name in grants:
        StaffGrant.objects.get_or_create(assignment=assignment, name=grant_name)
    return assignment


def seed_facility_data(
    facility: Facility,
    prefix: str,
    *,
    paid_amounts: tuple[int, int],
    failed_amount: int,
) -> None:
    """Seed members, subscriptions, billing, payments, and sessions for one facility."""

    main_plan = create_plan(facility, f"{prefix} Unlimited", auto_renew=True)
    punch_plan = create_plan(facility, f"{prefix} Punch Card", auto_renew=False)

    first_member = create_member(
        facility,
        first_name=f"{prefix} Alex",
        last_name="Member",
        email=f"{prefix.lower()}-alex@example.test",
        member_since=aware_datetime(2026, 1, 5),
    )
    second_member = create_member(
        facility,
        first_name=f"{prefix} Blair",
        last_name="Member",
        email=f"{prefix.lower()}-blair@example.test",
        member_since=aware_datetime(2026, 2, 10),
        created_via_portal=True,
    )

    create_status(
        facility, first_member, MemberStatus.Status.ACTIVE, aware_datetime(2026, 1, 5)
    )
    create_status(
        facility, second_member, MemberStatus.Status.TRIAL, aware_datetime(2026, 2, 10)
    )

    first_subscription = create_subscription(
        facility, first_member, main_plan, MemberSubscription.Status.ACTIVE
    )
    second_subscription = create_subscription(
        facility, second_member, punch_plan, MemberSubscription.Status.ACTIVE
    )

    paid_doc = create_document(
        facility,
        first_member,
        first_subscription,
        BillingDocument.Status.PAID,
        due_date=aware_datetime(2026, 3, 1),
        paid_at=aware_datetime(2026, 3, 2),
    )
    create_line(paid_doc, main_plan, f"{prefix} membership", paid_amounts[0])
    create_line(paid_doc, None, f"{prefix} retail", paid_amounts[1])
    create_payment(
        paid_doc, first_member, PaymentAttempt.Status.SUCCEEDED, sum(paid_amounts)
    )

    failed_doc = create_document(
        facility,
        second_member,
        second_subscription,
        BillingDocument.Status.PAYMENT_FAILED,
        due_date=aware_datetime(2026, 3, 15),
        paid_at=None,
        failure_code="card_declined",
        failure_message="Synthetic payment failure for local testing.",
    )
    create_line(failed_doc, punch_plan, f"{prefix} punch card", failed_amount)
    create_payment(
        failed_doc,
        second_member,
        PaymentAttempt.Status.REQUIRES_PAYMENT_METHOD,
        failed_amount,
        failure_code="card_declined",
        failure_message="Synthetic payment failure for local testing.",
    )

    location, _created = FacilityLocation.objects.get_or_create(
        facility=facility,
        name=f"{prefix} Main Room",
        defaults={"capacity": 20, "is_active": True},
    )
    session_type, _created = SessionType.objects.get_or_create(
        facility=facility,
        name=f"{prefix} Conditioning",
        defaults={"is_bookable": True},
    )
    ScheduleSession.objects.get_or_create(
        facility=facility,
        session_type=session_type,
        location=location,
        start_date=datetime(2026, 3, 20).date(),
        start_time=time(9, 0),
        defaults={
            "duration_minutes": 60,
            "capacity": 18,
            "waitlist_limit": 4,
            "reservation_settings": {"late_cancel_minutes": 60},
        },
    )


def create_plan(facility: Facility, name: str, *, auto_renew: bool) -> SubscriptionPlan:
    """Create or update a subscription plan."""

    plan, _created = SubscriptionPlan.objects.update_or_create(
        facility=facility,
        name=name,
        defaults={
            "description": "Synthetic plan for local AskLens testing.",
            "auto_renew": auto_renew,
            "allow_proration": True,
            "sales_status": SubscriptionPlan.SalesStatus.PUBLIC,
            "member_sales_enabled": True,
        },
    )
    return plan


def create_member(
    facility: Facility,
    *,
    first_name: str,
    last_name: str,
    email: str,
    member_since: datetime,
    created_via_portal: bool = False,
) -> MemberProfile:
    """Create or update a synthetic member."""

    member, _created = MemberProfile.objects.update_or_create(
        facility=facility,
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone": "+15555550100",
            "gender": MemberProfile.Gender.NOT_PROVIDED,
            "member_since": member_since,
            "created_via_portal": created_via_portal,
            "emergency_contact_name": "Synthetic Contact",
            "emergency_contact_phone": "+15555550101",
            "medical_notes": "Synthetic note for sensitivity testing.",
        },
    )
    return member


def create_status(
    facility: Facility,
    member: MemberProfile,
    status: str,
    start_date: datetime,
) -> MemberStatus:
    """Create a member status if missing."""

    status_obj, _created = MemberStatus.objects.get_or_create(
        facility=facility,
        member=member,
        status=status,
        start_date=start_date,
        defaults={"end_date": None},
    )
    return status_obj


def create_subscription(
    facility: Facility,
    member: MemberProfile,
    plan: SubscriptionPlan,
    status: str,
) -> MemberSubscription:
    """Create or update a member subscription."""

    subscription, _created = MemberSubscription.objects.update_or_create(
        facility=facility,
        member=member,
        plan=plan,
        defaults={
            "status": status,
            "start_date": aware_datetime(2026, 3, 1),
            "end_date": aware_datetime(2026, 4, 1),
            "billing_start_date": aware_datetime(2026, 3, 1),
            "auto_renew": plan.auto_renew,
            "auto_pay": True,
            "is_prorated": False,
        },
    )
    return subscription


def create_document(
    facility: Facility,
    member: MemberProfile,
    subscription: MemberSubscription,
    status: str,
    *,
    due_date: datetime,
    paid_at: datetime | None,
    failure_code: str = "",
    failure_message: str = "",
) -> BillingDocument:
    """Create or update a billing document."""

    document, _created = BillingDocument.objects.update_or_create(
        facility=facility,
        member=member,
        subscription=subscription,
        due_date=due_date,
        defaults={
            "status": status,
            "paid_at": paid_at,
            "auto_pay": True,
            "failure_code": failure_code,
            "failure_message": failure_message,
        },
    )
    return document


def create_line(
    document: BillingDocument,
    plan: SubscriptionPlan | None,
    product_name: str,
    total_cents: int,
) -> BillingLine:
    """Create or update a billing line."""

    tax_cents = round(total_cents * 0.08)
    pretax_cents = total_cents - tax_cents
    line, _created = BillingLine.objects.update_or_create(
        facility=document.facility,
        billing_document=document,
        product_name=product_name,
        defaults={
            "plan": plan,
            "quantity": 1,
            "item_price_cents": pretax_cents,
            "pretax_amount_cents": pretax_cents,
            "tax_cents": tax_cents,
            "total_amount_cents": total_cents,
        },
    )
    return line


def create_payment(
    document: BillingDocument,
    member: MemberProfile,
    status: str,
    amount_cents: int,
    *,
    failure_code: str = "",
    failure_message: str = "",
) -> PaymentAttempt:
    """Create or update a payment attempt."""

    payment, _created = PaymentAttempt.objects.update_or_create(
        facility=document.facility,
        billing_document=document,
        member=member,
        status=status,
        defaults={
            "amount_cents": amount_cents,
            "amount_refunded_cents": 0,
            "refunded": False,
            "processor_payment_id": f"synthetic-{document.document_id}",
            "failure_code": failure_code,
            "failure_message": failure_message,
        },
    )
    return payment

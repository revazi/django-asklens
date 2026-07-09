"""Seed the runnable AskLens test project with synthetic complex data."""

from datetime import datetime, time, timedelta

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

MEMBER_FIXTURES = (
    {
        "first_name": "Alex",
        "last_name": "Member",
        "email_slug": "alex",
        "plan_key": "unlimited",
        "status": MemberStatus.Status.ACTIVE,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 12000,
        "portal": False,
        "gender": MemberProfile.Gender.NOT_PROVIDED,
    },
    {
        "first_name": "Blair",
        "last_name": "Trial",
        "email_slug": "blair",
        "plan_key": "punch_card",
        "status": MemberStatus.Status.TRIAL,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 7000,
        "portal": True,
        "gender": MemberProfile.Gender.FEMALE,
    },
    {
        "first_name": "Casey",
        "last_name": "Coach",
        "email_slug": "casey",
        "plan_key": "personal_training",
        "status": MemberStatus.Status.ACTIVE,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 18000,
        "portal": False,
        "gender": MemberProfile.Gender.NON_BINARY,
    },
    {
        "first_name": "Devon",
        "last_name": "Hold",
        "email_slug": "devon",
        "plan_key": "unlimited",
        "status": MemberStatus.Status.NON_PAYING,
        "subscription_status": MemberSubscription.Status.HOLD,
        "base_amount": 9000,
        "portal": False,
        "gender": MemberProfile.Gender.MALE,
    },
    {
        "first_name": "Emery",
        "last_name": "Alumni",
        "email_slug": "emery",
        "plan_key": "punch_card",
        "status": MemberStatus.Status.ALUMNI,
        "subscription_status": MemberSubscription.Status.ENDED,
        "base_amount": 6000,
        "portal": True,
        "gender": MemberProfile.Gender.NOT_PROVIDED,
    },
    {
        "first_name": "Finley",
        "last_name": "Prospect",
        "email_slug": "finley",
        "plan_key": "drop_in",
        "status": MemberStatus.Status.PROSPECT,
        "subscription_status": MemberSubscription.Status.UPCOMING,
        "base_amount": 2500,
        "portal": True,
        "gender": MemberProfile.Gender.FEMALE,
    },
    {
        "first_name": "Gray",
        "last_name": "Renewal",
        "email_slug": "gray",
        "plan_key": "unlimited",
        "status": MemberStatus.Status.ACTIVE,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 13500,
        "portal": False,
        "gender": MemberProfile.Gender.MALE,
    },
    {
        "first_name": "Harper",
        "last_name": "Cancel",
        "email_slug": "harper",
        "plan_key": "personal_training",
        "status": MemberStatus.Status.ALUMNI,
        "subscription_status": MemberSubscription.Status.CANCELLED,
        "base_amount": 15000,
        "portal": False,
        "gender": MemberProfile.Gender.FEMALE,
    },
    {
        "first_name": "Indigo",
        "last_name": "Visitor",
        "email_slug": "indigo",
        "plan_key": "drop_in",
        "status": MemberStatus.Status.TRIAL,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 4000,
        "portal": True,
        "gender": MemberProfile.Gender.NON_BINARY,
    },
    {
        "first_name": "Jules",
        "last_name": "Family",
        "email_slug": "jules",
        "plan_key": "family",
        "status": MemberStatus.Status.ACTIVE,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 20000,
        "portal": False,
        "gender": MemberProfile.Gender.NOT_PROVIDED,
    },
    {
        "first_name": "Kai",
        "last_name": "Scholarship",
        "email_slug": "kai",
        "plan_key": "community",
        "status": MemberStatus.Status.NON_PAYING,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 3000,
        "portal": False,
        "gender": MemberProfile.Gender.MALE,
    },
    {
        "first_name": "Logan",
        "last_name": "Late",
        "email_slug": "logan",
        "plan_key": "unlimited",
        "status": MemberStatus.Status.ACTIVE,
        "subscription_status": MemberSubscription.Status.ACTIVE,
        "base_amount": 11500,
        "portal": True,
        "gender": MemberProfile.Gender.FEMALE,
    },
)


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

        seed_facility_data(north, "North", amount_multiplier=1.0)
        seed_facility_data(south, "South", amount_multiplier=1.35)

        self.stdout.write(
            self.style.SUCCESS("Seeded synthetic AskLens test-project data.")
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Created demo admin login admin / "
                f"{DEMO_PASSWORD} and staff demo users."
            )
        )


def aware_datetime(year: int, month: int, day: int, hour: int = 12) -> datetime:
    """Return a timezone-aware datetime in the active timezone."""

    return timezone.make_aware(datetime(year, month, day, hour, 0, 0))


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
    amount_multiplier: float,
) -> None:
    """Seed rich members, subscriptions, billing, payments, and sessions."""

    plans = create_plan_catalog(facility, prefix)
    members: list[tuple[MemberProfile, MemberSubscription, dict]] = []

    for index, member_fixture in enumerate(MEMBER_FIXTURES, start=1):
        member = create_member_from_fixture(
            facility,
            prefix,
            index=index,
            fixture=member_fixture,
        )
        create_status_history(
            facility,
            member,
            current_status=member_fixture["status"],
            index=index,
        )
        subscription = create_subscription(
            facility,
            member,
            plans[member_fixture["plan_key"]],
            status=member_fixture["subscription_status"],
            index=index,
        )
        members.append((member, subscription, member_fixture))

    seed_billing_documents(
        facility,
        prefix,
        members=members,
        amount_multiplier=amount_multiplier,
    )
    seed_schedule(facility, prefix)


def create_plan_catalog(facility: Facility, prefix: str) -> dict[str, SubscriptionPlan]:
    """Create a varied subscription-plan catalog for one facility."""

    return {
        "unlimited": create_plan(
            facility,
            f"{prefix} Unlimited",
            auto_renew=True,
            allow_proration=True,
            sales_status=SubscriptionPlan.SalesStatus.PUBLIC,
            max_sales_allowed=None,
        ),
        "punch_card": create_plan(
            facility,
            f"{prefix} Punch Card",
            auto_renew=False,
            allow_proration=False,
            sales_status=SubscriptionPlan.SalesStatus.PUBLIC,
            max_sales_allowed=100,
        ),
        "personal_training": create_plan(
            facility,
            f"{prefix} Personal Training",
            auto_renew=True,
            allow_proration=True,
            sales_status=SubscriptionPlan.SalesStatus.PRIVATE,
            max_sales_allowed=30,
        ),
        "drop_in": create_plan(
            facility,
            f"{prefix} Drop In",
            auto_renew=False,
            allow_proration=False,
            sales_status=SubscriptionPlan.SalesStatus.PUBLIC,
            max_sales_allowed=None,
        ),
        "family": create_plan(
            facility,
            f"{prefix} Family Plan",
            auto_renew=True,
            allow_proration=True,
            sales_status=SubscriptionPlan.SalesStatus.PUBLIC,
            max_sales_allowed=50,
        ),
        "community": create_plan(
            facility,
            f"{prefix} Community Access",
            auto_renew=False,
            allow_proration=True,
            sales_status=SubscriptionPlan.SalesStatus.PRIVATE,
            max_sales_allowed=25,
        ),
    }


def create_plan(
    facility: Facility,
    name: str,
    *,
    auto_renew: bool,
    allow_proration: bool,
    sales_status: str,
    max_sales_allowed: int | None,
) -> SubscriptionPlan:
    """Create or update a subscription plan."""

    plan, _created = SubscriptionPlan.objects.update_or_create(
        facility=facility,
        name=name,
        defaults={
            "description": "Synthetic plan for local AskLens testing.",
            "auto_renew": auto_renew,
            "allow_proration": allow_proration,
            "sales_status": sales_status,
            "member_sales_enabled": sales_status == SubscriptionPlan.SalesStatus.PUBLIC,
            "max_sales_allowed": max_sales_allowed,
            "start_date": aware_datetime(2026, 1, 1),
            "archived_at": None,
        },
    )
    return plan


def create_member_from_fixture(
    facility: Facility,
    prefix: str,
    *,
    index: int,
    fixture: dict,
) -> MemberProfile:
    """Create or update one synthetic member from fixture metadata."""

    return create_member(
        facility,
        first_name=f"{prefix} {fixture['first_name']}",
        last_name=fixture["last_name"],
        email=f"{prefix.lower()}-{fixture['email_slug']}@example.test",
        member_since=aware_datetime(2026, 1 + ((index - 1) % 4), 2 + index),
        created_via_portal=fixture["portal"],
        gender=fixture["gender"],
        phone=f"+1555555{index:04d}",
        date_of_birth=datetime(1988 + (index % 12), (index % 12) + 1, 10).date(),
        external_profile_id=f"synthetic-{facility.slug}-{index:02d}",
    )


def create_member(
    facility: Facility,
    *,
    first_name: str,
    last_name: str,
    email: str,
    member_since: datetime,
    created_via_portal: bool,
    gender: str,
    phone: str,
    date_of_birth,
    external_profile_id: str,
) -> MemberProfile:
    """Create or update a synthetic member."""

    member, _created = MemberProfile.objects.update_or_create(
        facility=facility,
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "date_of_birth": date_of_birth,
            "gender": gender,
            "member_since": member_since,
            "created_via_portal": created_via_portal,
            "emergency_contact_name": "Synthetic Contact",
            "emergency_contact_phone": "+15555550101",
            "medical_notes": "Synthetic note for sensitivity testing.",
            "external_profile_id": external_profile_id,
        },
    )
    return member


def create_status_history(
    facility: Facility,
    member: MemberProfile,
    *,
    current_status: str,
    index: int,
) -> None:
    """Create a short deterministic status history for one member."""

    prospect_start = aware_datetime(2026, 1, min(index + 1, 27), 8)
    trial_start = aware_datetime(2026, 1, min(index + 6, 28), 8)
    current_start = aware_datetime(2026, 2, min(index + 3, 28), 8)

    create_status(
        facility,
        member,
        MemberStatus.Status.PROSPECT,
        prospect_start,
        end_date=trial_start,
    )
    if current_status != MemberStatus.Status.PROSPECT:
        create_status(
            facility,
            member,
            MemberStatus.Status.TRIAL,
            trial_start,
            end_date=current_start,
        )
    create_status(
        facility,
        member,
        current_status,
        current_start,
        end_date=None,
    )


def create_status(
    facility: Facility,
    member: MemberProfile,
    status: str,
    start_date: datetime,
    *,
    end_date: datetime | None = None,
) -> MemberStatus:
    """Create or update a member status."""

    status_obj, _created = MemberStatus.objects.update_or_create(
        facility=facility,
        member=member,
        status=status,
        start_date=start_date,
        defaults={"end_date": end_date},
    )
    return status_obj


def create_subscription(
    facility: Facility,
    member: MemberProfile,
    plan: SubscriptionPlan,
    *,
    status: str,
    index: int,
) -> MemberSubscription:
    """Create or update a member subscription."""

    start_date = aware_datetime(2026, 2, min(index + 1, 26))
    end_date = aware_datetime(2026, 6, min(index + 1, 26))
    cancellation_date = None
    cancellation_reason = ""
    if status in {MemberSubscription.Status.CANCELLED, MemberSubscription.Status.ENDED}:
        cancellation_date = aware_datetime(2026, 4, min(index + 2, 26))
        cancellation_reason = "Synthetic cancellation reason for demo reporting."

    subscription, _created = MemberSubscription.objects.update_or_create(
        facility=facility,
        member=member,
        plan=plan,
        defaults={
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "billing_start_date": start_date,
            "cancellation_date": cancellation_date,
            "cancellation_reason": cancellation_reason,
            "auto_renew": plan.auto_renew and status != MemberSubscription.Status.ENDED,
            "auto_pay": status != MemberSubscription.Status.UPCOMING,
            "is_prorated": index % 4 == 0,
        },
    )
    return subscription


def seed_billing_documents(
    facility: Facility,
    prefix: str,
    *,
    members: list[tuple[MemberProfile, MemberSubscription, dict]],
    amount_multiplier: float,
) -> None:
    """Create several months of billing and payment rows for each member."""

    for member_index, (member, subscription, fixture) in enumerate(members, start=1):
        base_amount = round(fixture["base_amount"] * amount_multiplier)
        for month in range(1, 7):
            status = billing_status_for(member_index=member_index, month=month)
            due_day = min(2 + member_index, 26)
            paid_at = None
            failure_code = ""
            failure_message = ""
            if status in {BillingDocument.Status.PAID, BillingDocument.Status.REFUNDED}:
                paid_at = aware_datetime(2026, month, min(due_day + 1, 27), 14)
            if status == BillingDocument.Status.PAYMENT_FAILED:
                failure_code = "card_declined"
                failure_message = "Synthetic payment failure for local testing."

            document = create_document(
                facility,
                member,
                subscription,
                status,
                due_date=aware_datetime(2026, month, due_day),
                paid_at=paid_at,
                failure_code=failure_code,
                failure_message=failure_message,
            )
            total_cents = base_amount + (month * 175) + (member_index * 50)
            document_total_cents = create_line(
                document,
                subscription.plan,
                f"{prefix} membership",
                total_cents,
                quantity=1,
            ).total_amount_cents
            if (member_index + month) % 2 == 0:
                document_total_cents += create_line(
                    document,
                    None,
                    f"{prefix} retail",
                    round(1800 * amount_multiplier) + (month * 125),
                    quantity=1 + (member_index % 2),
                ).total_amount_cents
            if member_index % 3 == 0:
                document_total_cents += create_line(
                    document,
                    subscription.plan,
                    f"{prefix} coaching add-on",
                    round(3200 * amount_multiplier),
                    quantity=1,
                ).total_amount_cents
            create_payment_for_document(
                document,
                member,
                status=status,
                amount_cents=document_total_cents,
                month=month,
            )


def billing_status_for(*, member_index: int, month: int) -> str:
    """Return a deterministic billing status for one synthetic invoice."""

    if month == 6 and member_index % 5 == 0:
        return BillingDocument.Status.UPCOMING
    if month in {3, 5} and member_index % 4 == 0:
        return BillingDocument.Status.PAYMENT_FAILED
    if month == 4 and member_index % 6 == 0:
        return BillingDocument.Status.REFUNDED
    if month == 2 and member_index % 7 == 0:
        return BillingDocument.Status.PAST_DUE
    return BillingDocument.Status.PAID


def create_payment_for_document(
    document: BillingDocument,
    member: MemberProfile,
    *,
    status: str,
    amount_cents: int,
    month: int,
) -> None:
    """Create a representative payment attempt for a billing document."""

    if status == BillingDocument.Status.UPCOMING:
        return
    if status == BillingDocument.Status.PAYMENT_FAILED:
        create_payment(
            document,
            member,
            PaymentAttempt.Status.REQUIRES_PAYMENT_METHOD,
            amount_cents,
            failure_code="card_declined",
            failure_message="Synthetic payment failure for local testing.",
        )
        create_payment(
            document,
            member,
            PaymentAttempt.Status.FAILED,
            amount_cents,
            failure_code="retry_failed",
            failure_message="Synthetic retry failure for local testing.",
        )
        return
    if status == BillingDocument.Status.REFUNDED:
        create_payment(
            document,
            member,
            PaymentAttempt.Status.SUCCEEDED,
            amount_cents,
            amount_refunded_cents=round(amount_cents * 0.35),
            refunded=True,
        )
        return
    payment_status = (
        PaymentAttempt.Status.PROCESSING
        if status == BillingDocument.Status.PAST_DUE
        else PaymentAttempt.Status.SUCCEEDED
    )
    create_payment(document, member, payment_status, amount_cents + (month * 10))


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
            "notes": "Synthetic billing note for admin exploration.",
        },
    )
    return document


def create_line(
    document: BillingDocument,
    plan: SubscriptionPlan | None,
    product_name: str,
    total_cents: int,
    *,
    quantity: int,
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
            "quantity": quantity,
            "item_price_cents": round(pretax_cents / quantity),
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
    amount_refunded_cents: int = 0,
    refunded: bool = False,
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
            "amount_refunded_cents": amount_refunded_cents,
            "refunded": refunded,
            "processor_payment_id": f"synthetic-{document.document_id}-{status}",
            "failure_code": failure_code,
            "failure_message": failure_message,
        },
    )
    return payment


def seed_schedule(facility: Facility, prefix: str) -> None:
    """Create several rooms, session types, and scheduled sessions."""

    locations = [
        create_location(facility, f"{prefix} Main Room", capacity=20),
        create_location(facility, f"{prefix} Annex", capacity=12),
        create_location(facility, f"{prefix} Outdoor Yard", capacity=30),
    ]
    session_types = [
        create_session_type(facility, f"{prefix} Conditioning"),
        create_session_type(facility, f"{prefix} Strength"),
        create_session_type(facility, f"{prefix} Mobility"),
        create_session_type(facility, f"{prefix} Foundations"),
    ]

    base_date = datetime(2026, 3, 2).date()
    for week in range(6):
        for type_index, session_type in enumerate(session_types):
            location = locations[(week + type_index) % len(locations)]
            start_date = base_date + timedelta(days=(week * 7) + type_index)
            start_hour = 6 + ((type_index + week) % 6)
            ScheduleSession.objects.update_or_create(
                facility=facility,
                session_type=session_type,
                location=location,
                start_date=start_date,
                start_time=time(start_hour, 0),
                defaults={
                    "duration_minutes": 45 + (type_index * 10),
                    "capacity": max(location.capacity - type_index, 1),
                    "waitlist_limit": 3 + type_index,
                    "reservation_settings": {
                        "late_cancel_minutes": 30 + (type_index * 15),
                        "waitlist_enabled": type_index % 2 == 0,
                    },
                },
            )


def create_location(
    facility: Facility, name: str, *, capacity: int
) -> FacilityLocation:
    """Create or update a facility location."""

    location, _created = FacilityLocation.objects.update_or_create(
        facility=facility,
        name=name,
        defaults={"capacity": capacity, "is_active": True},
    )
    return location


def create_session_type(facility: Facility, name: str) -> SessionType:
    """Create or update a session type."""

    session_type, _created = SessionType.objects.update_or_create(
        facility=facility,
        name=name,
        defaults={"is_bookable": True},
    )
    return session_type

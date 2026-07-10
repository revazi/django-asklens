"""Seed the runnable AskLens test project with synthetic complex data."""

from argparse import ArgumentTypeError
from dataclasses import dataclass, replace
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
SCALED_FACILITY_SLUG_PREFIX = "demo-tenant-"


@dataclass(frozen=True, slots=True)
class SeedProfile:
    """Configuration for synthetic seed scale."""

    name: str
    scaled_tenant_count: int
    members_per_tenant: int
    billing_months: int
    schedule_weeks: int
    batch_size: int


SEED_PROFILES = {
    "small": SeedProfile(
        name="small",
        scaled_tenant_count=0,
        members_per_tenant=0,
        billing_months=6,
        schedule_weeks=6,
        batch_size=500,
    ),
    "medium": SeedProfile(
        name="medium",
        scaled_tenant_count=10,
        members_per_tenant=1_000,
        billing_months=6,
        schedule_weeks=12,
        batch_size=1_000,
    ),
    "large": SeedProfile(
        name="large",
        scaled_tenant_count=10,
        members_per_tenant=25_000,
        billing_months=12,
        schedule_weeks=26,
        batch_size=1_000,
    ),
}

SCALED_FIRST_NAMES = (
    "Avery",
    "Bailey",
    "Cameron",
    "Dakota",
    "Elliot",
    "Frankie",
    "Gale",
    "Hayden",
    "Jordan",
    "Kendall",
    "Lane",
    "Morgan",
    "Noel",
    "Oakley",
    "Parker",
    "Quinn",
)
SCALED_LAST_NAMES = (
    "Atlas",
    "Brooks",
    "Chen",
    "Diaz",
    "Ellis",
    "Fields",
    "Garcia",
    "Hart",
    "Iverson",
    "Jones",
    "Kim",
    "Lopez",
    "Miller",
    "Nguyen",
    "Owens",
    "Patel",
)
SCALED_PLAN_KEYS = (
    "unlimited",
    "punch_card",
    "personal_training",
    "drop_in",
    "family",
    "community",
)
SCALED_MEMBER_STATUSES = (
    MemberStatus.Status.ACTIVE,
    MemberStatus.Status.ACTIVE,
    MemberStatus.Status.TRIAL,
    MemberStatus.Status.PROSPECT,
    MemberStatus.Status.NON_PAYING,
    MemberStatus.Status.ALUMNI,
)
SCALED_SUBSCRIPTION_STATUSES = (
    MemberSubscription.Status.ACTIVE,
    MemberSubscription.Status.ACTIVE,
    MemberSubscription.Status.ACTIVE,
    MemberSubscription.Status.HOLD,
    MemberSubscription.Status.ENDED,
    MemberSubscription.Status.CANCELLED,
    MemberSubscription.Status.UPCOMING,
)
SCALED_GENDERS = (
    MemberProfile.Gender.FEMALE,
    MemberProfile.Gender.MALE,
    MemberProfile.Gender.NON_BINARY,
    MemberProfile.Gender.NOT_PROVIDED,
)

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

    def add_arguments(self, parser) -> None:
        """Configure seed size/profile options."""

        parser.add_argument(
            "--size",
            choices=tuple(SEED_PROFILES),
            default="small",
            help=(
                "Seed profile: small keeps the fast demo; medium/large add "
                "scaled tenants."
            ),
        )
        parser.add_argument(
            "--tenant-count",
            type=positive_int_argument,
            default=None,
            help="Override scaled tenant count for medium/large/custom smoke runs.",
        )
        parser.add_argument(
            "--members-per-tenant",
            type=positive_int_argument,
            default=None,
            help="Override scaled member count per generated tenant.",
        )
        parser.add_argument(
            "--months",
            type=positive_int_argument,
            default=None,
            help="Override billing months per generated scaled member.",
        )
        parser.add_argument(
            "--schedule-weeks",
            type=positive_int_argument,
            default=None,
            help="Override scheduled-session weeks per generated scaled tenant.",
        )
        parser.add_argument(
            "--batch-size",
            type=positive_int_argument,
            default=None,
            help="Bulk-create batch size for scaled data.",
        )

    def handle(self, *args, **options) -> None:
        """Seed users, tenants, grants, members, billing, payments, and sessions."""

        profile = resolve_seed_profile(options)

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
        deactivate_assignment(owner, south, StaffAssignment.Role.OWNER)
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
        seed_scaled_demo_data(profile, stdout=self.stdout, style=self.style)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded synthetic AskLens test-project data ({profile.name})."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Created demo admin login admin / "
                f"{DEMO_PASSWORD} and staff demo users."
            )
        )


def positive_int_argument(value: str) -> int:
    """Parse a positive integer command argument."""

    try:
        parsed = int(value)
    except ValueError as exc:
        msg = f"Expected a positive integer, got {value!r}."
        raise ArgumentTypeError(msg) from exc
    if parsed < 1:
        msg = f"Expected a positive integer, got {value!r}."
        raise ArgumentTypeError(msg)
    return parsed


def resolve_seed_profile(options: dict) -> SeedProfile:
    """Resolve the selected seed profile plus CLI overrides."""

    profile = SEED_PROFILES[options["size"]]
    updates = {}
    option_to_field = {
        "tenant_count": "scaled_tenant_count",
        "members_per_tenant": "members_per_tenant",
        "months": "billing_months",
        "schedule_weeks": "schedule_weeks",
        "batch_size": "batch_size",
    }
    for option_name, field_name in option_to_field.items():
        if options.get(option_name) is not None:
            updates[field_name] = options[option_name]
    if not updates:
        return profile
    name = profile.name if profile.name != "small" else "custom"
    return replace(profile, name=name, **updates)


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
    desired_grants = set(grants)
    StaffGrant.objects.filter(assignment=assignment).exclude(
        name__in=desired_grants
    ).delete()
    for grant_name in desired_grants:
        StaffGrant.objects.get_or_create(assignment=assignment, name=grant_name)
    return assignment


def deactivate_assignment(user, facility: Facility, role: str) -> None:
    """Deactivate a synthetic assignment that should no longer be active."""

    StaffAssignment.objects.filter(
        user=user,
        facility=facility,
        role=role,
    ).update(is_active=False, can_access_all_facilities=False)


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


def seed_scaled_demo_data(profile: SeedProfile, *, stdout, style) -> None:
    """Seed bulk-generated tenants and operational data for larger profiles."""

    if profile.scaled_tenant_count <= 0 or profile.members_per_tenant <= 0:
        reset_scaled_facilities()
        return

    reset_scaled_facilities()
    scaled_billing_user = create_demo_user("scaled-billing", is_staff=True)
    scaled_member_user = create_demo_user("scaled-members", is_staff=True)
    scaled_schedule_user = create_demo_user("scaled-schedule", is_staff=True)

    stdout.write(
        style.NOTICE(
            "Seeding scaled demo data: "
            f"{profile.scaled_tenant_count} tenants × "
            f"{profile.members_per_tenant} members"
        )
    )
    for tenant_number in range(1, profile.scaled_tenant_count + 1):
        prefix = f"Tenant {tenant_number:02d}"
        facility = create_facility(
            f"Demo Tenant {tenant_number:02d}",
            f"{SCALED_FACILITY_SLUG_PREFIX}{tenant_number:02d}",
        )
        amount_multiplier = 1 + (tenant_number * 0.04)
        create_assignment(
            scaled_billing_user,
            facility,
            StaffAssignment.Role.STAFF,
            StaffGrant.BILLING_REPORTS_VIEW,
            StaffGrant.PAYMENT_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            scaled_member_user,
            facility,
            StaffAssignment.Role.STAFF,
            StaffGrant.MEMBER_REPORTS_VIEW,
            StaffGrant.PACKAGE_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        create_assignment(
            scaled_schedule_user,
            facility,
            StaffAssignment.Role.STAFF,
            StaffGrant.SCHEDULE_REPORTS_VIEW,
            StaffGrant.FACILITY_VIEW,
        )
        seed_scaled_facility_data(
            facility,
            prefix,
            profile=profile,
            amount_multiplier=amount_multiplier,
        )
        stdout.write(
            style.SUCCESS(
                f"  {facility.slug}: {profile.members_per_tenant} members, "
                f"{profile.billing_months} billing months"
            )
        )


def reset_scaled_facilities() -> None:
    """Delete previously generated scaled tenants in dependency order."""

    facility_ids = list(
        Facility.objects.filter(slug__startswith=SCALED_FACILITY_SLUG_PREFIX)
        .order_by("id")
        .values_list("id", flat=True)
    )
    if not facility_ids:
        return

    PaymentAttempt.objects.filter(facility_id__in=facility_ids).delete()
    BillingLine.objects.filter(facility_id__in=facility_ids).delete()
    BillingDocument.objects.filter(facility_id__in=facility_ids).delete()
    MemberStatus.objects.filter(facility_id__in=facility_ids).delete()
    MemberSubscription.objects.filter(facility_id__in=facility_ids).delete()
    ScheduleSession.objects.filter(facility_id__in=facility_ids).delete()
    SessionType.objects.filter(facility_id__in=facility_ids).delete()
    FacilityLocation.objects.filter(facility_id__in=facility_ids).delete()
    SubscriptionPlan.objects.filter(facility_id__in=facility_ids).delete()
    MemberProfile.objects.filter(facility_id__in=facility_ids).delete()
    StaffGrant.objects.filter(assignment__facility_id__in=facility_ids).delete()
    StaffAssignment.objects.filter(facility_id__in=facility_ids).delete()
    Facility.objects.filter(id__in=facility_ids).delete()


def seed_scaled_facility_data(
    facility: Facility,
    prefix: str,
    *,
    profile: SeedProfile,
    amount_multiplier: float,
) -> None:
    """Seed one larger tenant with bulk-generated operational rows."""

    plans = create_plan_catalog(facility, prefix)
    for start_index in range(1, profile.members_per_tenant + 1, profile.batch_size):
        end_index = min(
            start_index + profile.batch_size - 1, profile.members_per_tenant
        )
        seed_scaled_member_batch(
            facility,
            prefix,
            plans=plans,
            start_index=start_index,
            end_index=end_index,
            profile=profile,
            amount_multiplier=amount_multiplier,
        )
    seed_scaled_schedule(facility, prefix, weeks=profile.schedule_weeks)


def seed_scaled_member_batch(
    facility: Facility,
    prefix: str,
    *,
    plans: dict[str, SubscriptionPlan],
    start_index: int,
    end_index: int,
    profile: SeedProfile,
    amount_multiplier: float,
) -> None:
    """Bulk-create one batch of scaled members and related reporting rows."""

    indexes = range(start_index, end_index + 1)
    members = [build_scaled_member(facility, prefix, index) for index in indexes]
    MemberProfile.objects.bulk_create(members, batch_size=profile.batch_size)

    status_rows: list[MemberStatus] = []
    subscriptions: list[MemberSubscription] = []
    for member, index in zip(members, indexes, strict=True):
        current_status = scaled_member_status(index)
        status_rows.extend(
            build_scaled_status_rows(facility, member, current_status, index)
        )
        subscriptions.append(
            build_scaled_subscription(
                facility,
                member,
                plans[scaled_plan_key(index)],
                status=scaled_subscription_status(index),
                index=index,
            )
        )
    MemberStatus.objects.bulk_create(status_rows, batch_size=profile.batch_size)
    MemberSubscription.objects.bulk_create(subscriptions, batch_size=profile.batch_size)
    seed_scaled_billing_batch(
        facility,
        prefix,
        subscriptions=subscriptions,
        profile=profile,
        amount_multiplier=amount_multiplier,
    )


def build_scaled_member(facility: Facility, prefix: str, index: int) -> MemberProfile:
    """Build one deterministic scaled member profile."""

    first_name = SCALED_FIRST_NAMES[index % len(SCALED_FIRST_NAMES)]
    last_name = SCALED_LAST_NAMES[
        (index // len(SCALED_FIRST_NAMES)) % len(SCALED_LAST_NAMES)
    ]
    member_month = 1 + (index % 12)
    member_day = 1 + (index % 27)
    birth_year = 1965 + (index % 40)
    return MemberProfile(
        facility=facility,
        first_name=f"{prefix} {first_name}",
        last_name=f"{last_name} {index:06d}",
        email=f"{facility.slug}-member-{index:06d}@example.test",
        phone=f"+1555{facility.id:03d}{index % 1_000_000:06d}",
        date_of_birth=datetime(birth_year, 1 + (index % 12), member_day).date(),
        gender=SCALED_GENDERS[index % len(SCALED_GENDERS)],
        member_since=aware_datetime(2025, member_month, member_day),
        created_via_portal=index % 3 == 0,
        emergency_contact_name="Synthetic Contact",
        emergency_contact_phone="+15555550101",
        medical_notes="Synthetic scaled note for sensitivity testing.",
        external_profile_id=f"scaled-{facility.slug}-{index:06d}",
    )


def build_scaled_status_rows(
    facility: Facility,
    member: MemberProfile,
    current_status: str,
    index: int,
) -> list[MemberStatus]:
    """Build deterministic status history rows for one scaled member."""

    prospect_start = aware_datetime(2025, 1 + (index % 6), 1 + (index % 20), 8)
    current_start = prospect_start + timedelta(days=14 + (index % 45))
    rows = [
        MemberStatus(
            facility=facility,
            member=member,
            status=MemberStatus.Status.PROSPECT,
            start_date=prospect_start,
            end_date=current_start,
        )
    ]
    if current_status != MemberStatus.Status.PROSPECT:
        rows.append(
            MemberStatus(
                facility=facility,
                member=member,
                status=current_status,
                start_date=current_start,
                end_date=None,
            )
        )
    return rows


def build_scaled_subscription(
    facility: Facility,
    member: MemberProfile,
    plan: SubscriptionPlan,
    *,
    status: str,
    index: int,
) -> MemberSubscription:
    """Build one scaled subscription row."""

    start_month = 1 + (index % 12)
    start_day = 1 + (index % 26)
    start_date = aware_datetime(2025, start_month, start_day)
    end_date = start_date + timedelta(days=180 + (index % 120))
    cancellation_date = None
    cancellation_reason = ""
    if status in {MemberSubscription.Status.CANCELLED, MemberSubscription.Status.ENDED}:
        cancellation_date = start_date + timedelta(days=90 + (index % 45))
        cancellation_reason = "Synthetic scaled cancellation reason."
    return MemberSubscription(
        facility=facility,
        member=member,
        plan=plan,
        status=status,
        start_date=start_date,
        end_date=end_date,
        billing_start_date=start_date,
        cancellation_date=cancellation_date,
        cancellation_reason=cancellation_reason,
        auto_renew=plan.auto_renew and status != MemberSubscription.Status.ENDED,
        auto_pay=status != MemberSubscription.Status.UPCOMING,
        is_prorated=index % 9 == 0,
    )


def seed_scaled_billing_batch(
    facility: Facility,
    prefix: str,
    *,
    subscriptions: list[MemberSubscription],
    profile: SeedProfile,
    amount_multiplier: float,
) -> None:
    """Bulk-create billing documents, lines, and payments for subscriptions."""

    documents: list[BillingDocument] = []
    contexts: list[tuple[BillingDocument, MemberSubscription, int, str]] = []
    for subscription in subscriptions:
        global_index = extract_scaled_member_index(subscription.member.email)
        for month in range(1, profile.billing_months + 1):
            status = billing_status_for(member_index=global_index, month=month)
            due_day = 1 + (global_index % 26)
            paid_at = None
            failure_code = ""
            failure_message = ""
            if status in {BillingDocument.Status.PAID, BillingDocument.Status.REFUNDED}:
                paid_at = aware_datetime(
                    2026, month_for_year(month), min(due_day + 1, 27), 14
                )
            if status == BillingDocument.Status.PAYMENT_FAILED:
                failure_code = "card_declined"
                failure_message = "Synthetic scaled payment failure."
            document = BillingDocument(
                facility=facility,
                member=subscription.member,
                subscription=subscription,
                status=status,
                due_date=aware_datetime(2026, month_for_year(month), due_day),
                paid_at=paid_at,
                auto_pay=True,
                failure_code=failure_code,
                failure_message=failure_message,
                notes="Synthetic scaled billing note.",
            )
            documents.append(document)
            contexts.append((document, subscription, month, status))
    BillingDocument.objects.bulk_create(documents, batch_size=profile.batch_size)

    lines: list[BillingLine] = []
    payments: list[PaymentAttempt] = []
    for document, subscription, month, status in contexts:
        member_index = extract_scaled_member_index(subscription.member.email)
        base_amount = round(scaled_base_amount(member_index) * amount_multiplier)
        membership_total = base_amount + (month * 175) + (member_index % 500)
        lines.append(
            build_scaled_line(
                document,
                subscription.plan,
                f"{prefix} membership",
                membership_total,
                quantity=1,
            )
        )
        document_total_cents = membership_total
        if (member_index + month) % 2 == 0:
            retail_total = round(1800 * amount_multiplier) + (month * 125)
            lines.append(
                build_scaled_line(
                    document,
                    None,
                    f"{prefix} retail",
                    retail_total,
                    quantity=1 + (member_index % 2),
                )
            )
            document_total_cents += retail_total
        if member_index % 5 == 0:
            coaching_total = round(3200 * amount_multiplier)
            lines.append(
                build_scaled_line(
                    document,
                    subscription.plan,
                    f"{prefix} coaching add-on",
                    coaching_total,
                    quantity=1,
                )
            )
            document_total_cents += coaching_total
        payments.extend(
            build_scaled_payments(
                document,
                subscription.member,
                status=status,
                amount_cents=document_total_cents,
                month=month,
            )
        )
    BillingLine.objects.bulk_create(lines, batch_size=profile.batch_size)
    PaymentAttempt.objects.bulk_create(payments, batch_size=profile.batch_size)


def build_scaled_line(
    document: BillingDocument,
    plan: SubscriptionPlan | None,
    product_name: str,
    total_cents: int,
    *,
    quantity: int,
) -> BillingLine:
    """Build one scaled billing line."""

    tax_cents = round(total_cents * 0.08)
    pretax_cents = total_cents - tax_cents
    return BillingLine(
        facility=document.facility,
        billing_document=document,
        plan=plan,
        product_name=product_name,
        quantity=quantity,
        item_price_cents=round(pretax_cents / quantity),
        pretax_amount_cents=pretax_cents,
        tax_cents=tax_cents,
        total_amount_cents=total_cents,
    )


def build_scaled_payments(
    document: BillingDocument,
    member: MemberProfile,
    *,
    status: str,
    amount_cents: int,
    month: int,
) -> list[PaymentAttempt]:
    """Build scaled payment attempts for one billing document."""

    if status == BillingDocument.Status.UPCOMING:
        return []
    if status == BillingDocument.Status.PAYMENT_FAILED:
        return [
            build_scaled_payment(
                document,
                member,
                PaymentAttempt.Status.REQUIRES_PAYMENT_METHOD,
                amount_cents,
                failure_code="card_declined",
                failure_message="Synthetic scaled payment failure.",
            ),
            build_scaled_payment(
                document,
                member,
                PaymentAttempt.Status.FAILED,
                amount_cents,
                failure_code="retry_failed",
                failure_message="Synthetic scaled retry failure.",
            ),
        ]
    if status == BillingDocument.Status.REFUNDED:
        return [
            build_scaled_payment(
                document,
                member,
                PaymentAttempt.Status.SUCCEEDED,
                amount_cents,
                amount_refunded_cents=round(amount_cents * 0.35),
                refunded=True,
            )
        ]
    payment_status = (
        PaymentAttempt.Status.PROCESSING
        if status == BillingDocument.Status.PAST_DUE
        else PaymentAttempt.Status.SUCCEEDED
    )
    return [
        build_scaled_payment(
            document, member, payment_status, amount_cents + (month * 10)
        )
    ]


def build_scaled_payment(
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
    """Build one scaled payment attempt."""

    return PaymentAttempt(
        facility=document.facility,
        billing_document=document,
        member=member,
        status=status,
        amount_cents=amount_cents,
        amount_refunded_cents=amount_refunded_cents,
        refunded=refunded,
        processor_payment_id=f"synthetic-{document.document_id}-{status}",
        failure_code=failure_code,
        failure_message=failure_message,
    )


def seed_scaled_schedule(facility: Facility, prefix: str, *, weeks: int) -> None:
    """Create a larger schedule surface for a scaled tenant."""

    locations = [
        create_location(facility, f"{prefix} Main Room", capacity=32),
        create_location(facility, f"{prefix} Annex", capacity=18),
        create_location(facility, f"{prefix} Recovery Room", capacity=14),
        create_location(facility, f"{prefix} Outdoor Yard", capacity=40),
    ]
    session_types = [
        create_session_type(facility, f"{prefix} Conditioning"),
        create_session_type(facility, f"{prefix} Strength"),
        create_session_type(facility, f"{prefix} Mobility"),
        create_session_type(facility, f"{prefix} Foundations"),
        create_session_type(facility, f"{prefix} Youth Training"),
        create_session_type(facility, f"{prefix} Personal Training"),
    ]
    base_date = datetime(2026, 1, 5).date()
    sessions: list[ScheduleSession] = []
    for week in range(weeks):
        for type_index, session_type in enumerate(session_types):
            for day_offset in (0, 2, 4):
                location = locations[(week + type_index + day_offset) % len(locations)]
                start_date = base_date + timedelta(days=(week * 7) + day_offset)
                start_hour = 6 + ((type_index + week + day_offset) % 10)
                sessions.append(
                    ScheduleSession(
                        facility=facility,
                        session_type=session_type,
                        location=location,
                        start_date=start_date,
                        start_time=time(start_hour, 0),
                        duration_minutes=45 + ((type_index % 4) * 10),
                        capacity=max(location.capacity - (type_index % 5), 1),
                        waitlist_limit=3 + (type_index % 4),
                        reservation_settings={
                            "late_cancel_minutes": 30 + (type_index * 10),
                            "waitlist_enabled": type_index % 2 == 0,
                        },
                    )
                )
    ScheduleSession.objects.bulk_create(sessions, batch_size=1_000)


def scaled_plan_key(index: int) -> str:
    """Return a deterministic plan key for one scaled member."""

    return SCALED_PLAN_KEYS[index % len(SCALED_PLAN_KEYS)]


def scaled_member_status(index: int) -> str:
    """Return a deterministic current member status."""

    return SCALED_MEMBER_STATUSES[index % len(SCALED_MEMBER_STATUSES)]


def scaled_subscription_status(index: int) -> str:
    """Return a deterministic subscription status."""

    return SCALED_SUBSCRIPTION_STATUSES[index % len(SCALED_SUBSCRIPTION_STATUSES)]


def scaled_base_amount(index: int) -> int:
    """Return a deterministic scaled member base billing amount."""

    return 4_000 + ((index % 60) * 250)


def extract_scaled_member_index(email: str) -> int:
    """Extract the deterministic member index from a scaled synthetic email."""

    local_part = email.split("@", 1)[0]
    return int(local_part.rsplit("-", 1)[1])


def month_for_year(month: int) -> int:
    """Map unbounded month counters into a calendar month."""

    return 1 + ((month - 1) % 12)


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

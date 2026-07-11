"""Tests for the runnable complex test-project seed command."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from rest_framework.test import APIClient

from django_asklens.catalog.registry import default_registry
from tests.test_project.asklens_registry import (
    permitted_facility_ids,
    register_complex_resources,
)
from tests.test_project.models import (
    BillingDocument,
    BillingLine,
    Facility,
    Lead,
    MarketingCampaign,
    MemberProfile,
    PaymentAttempt,
    ScheduleSession,
    SessionBooking,
    StaffAssignment,
    StaffGrant,
    StaffShift,
    SupportTicket,
)
from tests.test_project.permissions import (
    get_request_permissions,
    permission_set_allows,
)

pytestmark = pytest.mark.django_db

QUESTION_REVENUE_BY_PRODUCT = "Show paid billing revenue by product"
QUESTION_FACILITY_OWNER_NAMES = (
    "List facilities, facility name titles and facility owner full name as a table."
)


def revenue_by_product_plan() -> dict[str, Any]:
    """Return the demo revenue-by-product plan."""

    return {
        "resource": "billing_lines",
        "intent": "aggregate",
        "filters": [{"field": "billing_document.status", "op": "eq", "value": "PAID"}],
        "group_by": [{"field": "product_name"}],
        "metrics": [
            {"name": "gross_revenue", "op": "sum", "field": "total_amount_cents"}
        ],
        "order_by": [{"metric": "gross_revenue", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "product_name", "y": "gross_revenue"},
    }


@pytest.fixture(autouse=True)
def clear_default_registry() -> None:
    """Keep seed/API tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


def facility_owner_names_plan() -> dict[str, Any]:
    """Return a staff-assignment list plan for facility owner lookup."""

    return {
        "resource": "facility_staff_assignments",
        "intent": "list",
        "filters": [
            {"field": "role", "op": "eq", "value": StaffAssignment.Role.OWNER},
            {"field": "is_active", "op": "eq", "value": True},
        ],
        "select": ["facility.name", "user.first_name", "user.last_name"],
        "order_by": [{"field": "facility.name", "direction": "asc"}],
        "limit": 20,
        "visualization": {"type": "table"},
    }


def configure_complex_query_settings(settings) -> None:
    """Configure AskLens API settings for seeded complex-project tests."""

    settings.DJANGO_ASKLENS = {
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.CanUseComplexAnalytics",
        ],
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.permissions.get_request_permissions"
        ),
        "DUMMY_PLANS": {
            QUESTION_REVENUE_BY_PRODUCT: revenue_by_product_plan(),
            QUESTION_FACILITY_OWNER_NAMES: facility_owner_names_plan(),
        },
        "MAX_ROWS": 100,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }


def facility_slugs_for(user, permission_name: str) -> list[str]:
    """Return sorted facility slugs visible for one synthetic permission."""

    return list(
        Facility.objects.filter(id__in=permitted_facility_ids(user, permission_name))
        .order_by("slug")
        .values_list("slug", flat=True)
    )


def test_seed_scopes_facility_owner_to_one_facility() -> None:
    """The demo facility-owner should only own North Studio after seeding."""

    call_command("seed_complex_test_project", verbosity=0)

    owner = get_user_model().objects.get(username="facility-owner")
    active_assignments = StaffAssignment.objects.filter(
        user=owner,
        is_active=True,
        role=StaffAssignment.Role.OWNER,
    ).select_related("facility")

    assert [assignment.facility.slug for assignment in active_assignments] == [
        "north-studio"
    ]


def test_seed_deactivates_stale_south_owner_assignment() -> None:
    """Re-running the seed fixes old local DBs where facility-owner owned South."""

    call_command("seed_complex_test_project", verbosity=0)
    owner = get_user_model().objects.get(username="facility-owner")
    south = Facility.objects.get(slug="south-studio")
    StaffAssignment.objects.update_or_create(
        user=owner,
        facility=south,
        role=StaffAssignment.Role.OWNER,
        defaults={"is_active": True, "can_access_all_facilities": False},
    )

    call_command("seed_complex_test_project", verbosity=0)

    assert not StaffAssignment.objects.filter(
        user=owner,
        facility=south,
        role=StaffAssignment.Role.OWNER,
        is_active=True,
    ).exists()


def test_seed_sets_demo_user_names_and_role_groups() -> None:
    """Seeded role data should be easy to inspect in the admin database."""

    call_command("seed_complex_test_project", verbosity=0)
    owner = get_user_model().objects.get(username="facility-owner")
    role_group_names = set(
        Group.objects.filter(name__startswith="AskLens Demo ").values_list(
            "name", flat=True
        )
    )

    assert owner.first_name == "Facility"
    assert owner.last_name == "Owner"
    assert role_group_names == {
        "AskLens Demo Members",
        "AskLens Demo Owners",
        "AskLens Demo Staff",
        "AskLens Demo Support",
    }
    assert list(owner.groups.values_list("name", flat=True)) == ["AskLens Demo Owners"]


def test_seeded_permissions_use_scoped_facility_tokens() -> None:
    """Tenant assignments should not emit unscoped global grant names."""

    call_command("seed_complex_test_project", verbosity=0)
    owner = get_user_model().objects.get(username="facility-owner")
    north = Facility.objects.get(slug="north-studio")
    permissions = get_request_permissions(type("Request", (), {"user": owner})())

    owner_assignment = StaffAssignment.objects.get(
        user=owner,
        facility=north,
        role=StaffAssignment.Role.OWNER,
        is_active=True,
    )
    owner_grants = set(owner_assignment.grants.values_list("name", flat=True))

    assert StaffGrant.BILLING_REPORTS_VIEW not in permissions
    assert f"facility:{north.id}:{StaffGrant.BILLING_REPORTS_VIEW}" in permissions
    assert permission_set_allows(permissions, StaffGrant.BILLING_REPORTS_VIEW)
    assert owner_grants == {name for name, _label in StaffGrant.GRANT_CHOICES}


def test_seed_size_medium_can_create_scaled_tenants_with_overrides() -> None:
    """Scaled seed profiles create realistic extra tenants without huge CI data."""

    call_command(
        "seed_complex_test_project",
        size="medium",
        tenant_count=3,
        members_per_tenant=10,
        months=2,
        schedule_weeks=1,
        batch_size=4,
        verbosity=0,
    )

    scaled_facilities = Facility.objects.filter(slug__startswith="demo-tenant-")
    assert scaled_facilities.count() == 3
    assert MemberProfile.objects.filter(facility__in=scaled_facilities).count() == 30
    assert (
        MarketingCampaign.objects.filter(facility__in=scaled_facilities).count() == 24
    )
    assert Lead.objects.filter(facility__in=scaled_facilities).count() == 15
    assert BillingDocument.objects.filter(facility__in=scaled_facilities).count() == 60
    assert BillingLine.objects.filter(facility__in=scaled_facilities).count() > 60
    assert PaymentAttempt.objects.filter(facility__in=scaled_facilities).count() > 0
    assert ScheduleSession.objects.filter(facility__in=scaled_facilities).count() == 54
    assert SessionBooking.objects.filter(facility__in=scaled_facilities).count() == 30
    assert StaffShift.objects.filter(facility__in=scaled_facilities).count() == 63
    assert SupportTicket.objects.filter(facility__in=scaled_facilities).count() == 3

    scaled_billing = get_user_model().objects.get(username="scaled-billing")
    assert facility_slugs_for(scaled_billing, StaffGrant.BILLING_REPORTS_VIEW) == [
        "demo-tenant-01",
        "demo-tenant-02",
        "demo-tenant-03",
    ]


def test_scaled_seed_rerun_resets_generated_tenants() -> None:
    """Scaled seed output should be deterministic when the size changes."""

    call_command(
        "seed_complex_test_project",
        size="medium",
        tenant_count=3,
        members_per_tenant=5,
        months=2,
        schedule_weeks=1,
        verbosity=0,
    )
    call_command(
        "seed_complex_test_project",
        size="medium",
        tenant_count=2,
        members_per_tenant=4,
        months=1,
        schedule_weeks=1,
        verbosity=0,
    )

    scaled_facilities = Facility.objects.filter(slug__startswith="demo-tenant-")
    assert scaled_facilities.count() == 2
    assert MemberProfile.objects.filter(facility__in=scaled_facilities).count() == 8
    assert (
        MarketingCampaign.objects.filter(facility__in=scaled_facilities).count() == 16
    )
    assert Lead.objects.filter(facility__in=scaled_facilities).count() == 4
    assert BillingDocument.objects.filter(facility__in=scaled_facilities).count() == 8
    assert SessionBooking.objects.filter(facility__in=scaled_facilities).count() == 8


def test_seeded_permission_matrix_scopes_facilities_by_grant() -> None:
    """Seeded demo users should resolve to the intended tenant scopes."""

    call_command("seed_complex_test_project", verbosity=0)
    user_model = get_user_model()

    owner = user_model.objects.get(username="facility-owner")
    north_billing = user_model.objects.get(username="north-billing")
    south_billing = user_model.objects.get(username="south-billing")
    support = user_model.objects.get(username="support-reporter")

    assert facility_slugs_for(owner, StaffGrant.BILLING_REPORTS_VIEW) == [
        "north-studio"
    ]
    assert facility_slugs_for(north_billing, StaffGrant.BILLING_REPORTS_VIEW) == [
        "north-studio"
    ]
    assert facility_slugs_for(south_billing, StaffGrant.BILLING_REPORTS_VIEW) == [
        "south-studio"
    ]
    assert facility_slugs_for(support, StaffGrant.BILLING_REPORTS_VIEW) == []
    assert facility_slugs_for(support, StaffGrant.ANALYTICS_VIEW) == [
        "north-studio",
        "south-studio",
    ]


def test_seed_syncs_assignment_grants() -> None:
    """Re-running the seed removes stale grants that would broaden access."""

    call_command("seed_complex_test_project", verbosity=0)
    user = get_user_model().objects.get(username="north-billing")
    assignment = StaffAssignment.objects.get(
        user=user,
        facility__slug="north-studio",
        role=StaffAssignment.Role.STAFF,
    )
    StaffGrant.objects.create(
        assignment=assignment,
        name=StaffGrant.MEMBER_PII_VIEW,
    )

    call_command("seed_complex_test_project", verbosity=0)

    assert not StaffGrant.objects.filter(
        assignment=assignment,
        name=StaffGrant.MEMBER_PII_VIEW,
    ).exists()


def test_support_reporter_catalog_includes_analytics_resources(settings) -> None:
    """Support analytics users should see analytics resources, not an empty catalog."""

    configure_complex_query_settings(settings)
    register_complex_resources()
    call_command("seed_complex_test_project", verbosity=0)
    support = get_user_model().objects.get(username="support-reporter")
    client = APIClient()
    client.force_authenticate(user=support)

    response = client.get("/asklens/catalog/")

    assert response.status_code == 200
    catalog_text = str(response.data)
    assert "marketing_campaigns" in catalog_text
    assert "support_tickets" in catalog_text
    assert "billing_lines" not in catalog_text
    assert "member_contacts" not in catalog_text


def test_facility_owner_can_query_facility_owner_name(settings) -> None:
    """Seeded owner assignments should be queryable through AskLens."""

    configure_complex_query_settings(settings)
    register_complex_resources()
    call_command("seed_complex_test_project", verbosity=0)
    owner = get_user_model().objects.get(username="facility-owner")
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        "/asklens/query/",
        {"question": QUESTION_FACILITY_OWNER_NAMES},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"] == [
        {
            "facility.name": "North Studio",
            "user.first_name": "Facility",
            "user.last_name": "Owner",
        }
    ]
    assert "South Studio" not in str(response.data)


def test_facility_owner_query_returns_only_owned_facility(settings) -> None:
    """The seeded facility-owner should not see South data through AskLens."""

    configure_complex_query_settings(settings)
    register_complex_resources()
    call_command("seed_complex_test_project", verbosity=0)
    owner = get_user_model().objects.get(username="facility-owner")
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        "/asklens/query/",
        {"question": QUESTION_REVENUE_BY_PRODUCT},
        format="json",
    )

    assert response.status_code == 200, response.data
    response_text = str(response.data)
    assert "North membership" in response_text
    assert "South membership" not in response_text
    assert "South retail" not in response_text
    assert "South coaching add-on" not in response_text

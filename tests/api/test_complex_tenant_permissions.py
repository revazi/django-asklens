"""Complex tenant, permission, and relation tests for AskLens API."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from django_asklens.planning.validation import parse_and_validate_query_plan
from tests.test_project.asklens_registry import register_complex_resources
from tests.test_project.models import (
    BillingDocument,
    BillingLine,
    Facility,
    MemberProfile,
    MemberSubscription,
    PaymentAttempt,
    StaffAssignment,
    StaffGrant,
    SubscriptionPlan,
)

pytestmark = pytest.mark.django_db

QUESTION_REVENUE_BY_PRODUCT = "Show paid billing revenue by product"
QUESTION_MEMBER_CONTACTS = "List member contact emails"
QUESTION_MEMBER_SUBSCRIPTIONS = "Count member subscriptions by plan and status"
QUESTION_HIDDEN_TENANT_FIELD = "Show billing rows for another facility slug"


@dataclass(frozen=True, slots=True)
class ComplexTenantData:
    """Synthetic complex tenant data used by API tests."""

    north: Facility
    south: Facility
    north_billing_user: Any
    south_billing_user: Any
    mixed_member_user: Any
    no_report_user: Any


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for deterministic fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_default_registry() -> None:
    """Keep complex API tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return a DRF API client."""

    return APIClient()


@pytest.fixture
def registered_complex_resources() -> None:
    """Register the complex synthetic resources for API tests."""

    register_complex_resources()


@pytest.fixture
def complex_tenant_data() -> ComplexTenantData:
    """Create deterministic multi-tenant data with tenant-scoped grants."""

    user_model = get_user_model()
    north_billing_user = user_model.objects.create_user(
        username="north-billing", password="pw"
    )
    south_billing_user = user_model.objects.create_user(
        username="south-billing", password="pw"
    )
    mixed_member_user = user_model.objects.create_user(
        username="mixed-member", password="pw"
    )
    no_report_user = user_model.objects.create_user(
        username="no-report",
        password="pw",
    )

    north = Facility.objects.create(name="North Studio", slug="north-studio")
    south = Facility.objects.create(name="South Studio", slug="south-studio")

    grant_user(
        north_billing_user,
        north,
        StaffGrant.BILLING_REPORTS_VIEW,
        StaffGrant.FACILITY_VIEW,
    )
    grant_user(
        south_billing_user,
        south,
        StaffGrant.BILLING_REPORTS_VIEW,
        StaffGrant.FACILITY_VIEW,
    )
    grant_user(
        mixed_member_user,
        north,
        StaffGrant.MEMBER_REPORTS_VIEW,
        StaffGrant.MEMBER_PII_VIEW,
        StaffGrant.FACILITY_VIEW,
    )
    grant_user(
        mixed_member_user,
        south,
        StaffGrant.MEMBER_REPORTS_VIEW,
        StaffGrant.FACILITY_VIEW,
    )
    StaffAssignment.objects.create(
        user=no_report_user,
        facility=north,
        role=StaffAssignment.Role.STAFF,
    )

    create_billing_fixture(
        facility=north,
        member_email="north-member@example.test",
        product_amounts={"Membership": 10000, "Retail": 5000},
    )
    create_billing_fixture(
        facility=south,
        member_email="south-member@example.test",
        product_amounts={"Membership": 7000, "Retail": 3000},
    )

    return ComplexTenantData(
        north=north,
        south=south,
        north_billing_user=north_billing_user,
        south_billing_user=south_billing_user,
        mixed_member_user=mixed_member_user,
        no_report_user=no_report_user,
    )


def grant_user(user: Any, facility: Facility, *grant_names: str) -> StaffAssignment:
    """Create an active assignment and grants for a user."""

    assignment = StaffAssignment.objects.create(
        user=user,
        facility=facility,
        role=StaffAssignment.Role.STAFF,
    )
    StaffGrant.objects.bulk_create(
        StaffGrant(assignment=assignment, name=grant_name) for grant_name in grant_names
    )
    return assignment


def create_billing_fixture(
    *,
    facility: Facility,
    member_email: str,
    product_amounts: dict[str, int],
) -> None:
    """Create a member, plan, document, lines, and payment for one facility."""

    member = MemberProfile.objects.create(
        facility=facility,
        first_name=facility.name.split()[0],
        last_name="Member",
        email=member_email,
        member_since=aware_datetime(2026, 1, 1),
        phone="+15555550100",
        medical_notes="Synthetic sensitive note.",
    )
    plan = SubscriptionPlan.objects.create(
        facility=facility,
        name=f"{facility.name} Plan",
        auto_renew=True,
        allow_proration=True,
        sales_status=SubscriptionPlan.SalesStatus.PUBLIC,
    )
    subscription = MemberSubscription.objects.create(
        facility=facility,
        member=member,
        plan=plan,
        start_date=aware_datetime(2026, 1, 1),
        end_date=aware_datetime(2026, 2, 1),
        billing_start_date=aware_datetime(2026, 1, 1),
        status=MemberSubscription.Status.ACTIVE,
        auto_renew=True,
        auto_pay=True,
    )
    document = BillingDocument.objects.create(
        facility=facility,
        member=member,
        subscription=subscription,
        status=BillingDocument.Status.PAID,
        due_date=aware_datetime(2026, 1, 1),
        paid_at=aware_datetime(2026, 1, 2),
        auto_pay=True,
    )
    for product_name, total_cents in product_amounts.items():
        tax_cents = round(total_cents * 0.08)
        pretax_amount = total_cents - tax_cents
        BillingLine.objects.create(
            facility=facility,
            billing_document=document,
            plan=plan if product_name == "Membership" else None,
            product_name=product_name,
            quantity=1,
            item_price_cents=pretax_amount,
            pretax_amount_cents=pretax_amount,
            tax_cents=tax_cents,
            total_amount_cents=total_cents,
        )
    PaymentAttempt.objects.create(
        facility=facility,
        billing_document=document,
        member=member,
        status=PaymentAttempt.Status.SUCCEEDED,
        amount_cents=sum(product_amounts.values()),
        processor_payment_id=f"processor-{facility.slug}",
    )


def configure_complex_dummy_plans(settings, plans: dict[str, dict[str, Any]]) -> None:
    """Configure AskLens for complex API tests."""

    settings.DJANGO_ASKLENS = {
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.CanUseComplexAnalytics",
        ],
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.permissions.get_request_permissions"
        ),
        "DUMMY_PLANS": plans,
        "MAX_ROWS": 50,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }


def revenue_by_product_plan() -> dict[str, Any]:
    """Return a revenue aggregate over a complex relation-backed resource."""

    return {
        "resource": "billing_lines",
        "intent": "aggregate",
        "filters": [{"field": "billing_document.status", "op": "eq", "value": "PAID"}],
        "group_by": [{"field": "product_name"}],
        "metrics": [
            {"name": "gross_revenue", "op": "sum", "field": "total_amount_cents"}
        ],
        "order_by": [{"field": "product_name", "direction": "asc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "product_name", "y": "gross_revenue"},
    }


def member_contacts_plan() -> dict[str, Any]:
    """Return a sensitive-field list plan for the contact-only resource."""

    return {
        "resource": "member_contacts",
        "intent": "list",
        "select": ["facility.name", "first_name", "email"],
        "order_by": [{"field": "email", "direction": "asc"}],
        "limit": 10,
        "visualization": {"type": "table"},
    }


def member_subscriptions_plan() -> dict[str, Any]:
    """Return a subscription count plan requiring package-report access."""

    return {
        "resource": "member_subscriptions",
        "intent": "aggregate",
        "group_by": [{"field": "plan.name"}, {"field": "status"}],
        "metrics": [{"name": "subscription_count", "op": "count", "field": "status"}],
        "order_by": [{"metric": "subscription_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {
            "type": "bar",
            "x": "plan.name",
            "y": "subscription_count",
        },
    }


def hidden_tenant_field_plan() -> dict[str, Any]:
    """Return a crafted plan attempting to use an unregistered tenant slug field."""

    return {
        "resource": "billing_lines",
        "intent": "list",
        "filters": [{"field": "facility.slug", "op": "eq", "value": "south-studio"}],
        "select": ["product_name"],
        "limit": 10,
        "visualization": {"type": "table"},
    }


def test_complex_catalog_scopes_fields_to_tenant_grants(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    configure_complex_dummy_plans(settings, {})
    api_client.force_authenticate(user=complex_tenant_data.north_billing_user)

    response = api_client.get("/asklens/catalog/")

    assert response.status_code == 200
    catalog_text = str(response.data)
    assert "billing_lines" in catalog_text
    assert "gross_revenue" in catalog_text
    assert "payment_amount" not in catalog_text
    assert "member_contacts" not in catalog_text
    assert "member_subscriptions" not in catalog_text
    assert "schedule_sessions" not in catalog_text
    assert "email" not in catalog_text
    assert "processor_payment_id" not in catalog_text


def test_complex_billing_query_scopes_rows_to_granted_facility(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    configure_complex_dummy_plans(
        settings,
        {QUESTION_REVENUE_BY_PRODUCT: revenue_by_product_plan()},
    )
    api_client.force_authenticate(user=complex_tenant_data.north_billing_user)

    north_response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_REVENUE_BY_PRODUCT},
        format="json",
    )

    assert north_response.status_code == 200, north_response.data
    assert north_response.data["data"] == [
        {"product_name": "Membership", "gross_revenue": 10000},
        {"product_name": "Retail", "gross_revenue": 5000},
    ]

    api_client.force_authenticate(user=complex_tenant_data.south_billing_user)
    south_response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_REVENUE_BY_PRODUCT},
        format="json",
    )

    assert south_response.status_code == 200, south_response.data
    assert south_response.data["data"] == [
        {"product_name": "Membership", "gross_revenue": 7000},
        {"product_name": "Retail", "gross_revenue": 3000},
    ]


def test_complex_contact_resource_scopes_to_facilities_with_pii_grant(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    configure_complex_dummy_plans(
        settings,
        {QUESTION_MEMBER_CONTACTS: member_contacts_plan()},
    )
    api_client.force_authenticate(user=complex_tenant_data.mixed_member_user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_MEMBER_CONTACTS},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"] == [
        {
            "facility.name": "North Studio",
            "first_name": "North",
            "email": "north-member@example.test",
        }
    ]
    assert "south-member@example.test" not in str(response.data)


def test_complex_query_rejects_resource_without_required_grant(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    configure_complex_dummy_plans(
        settings,
        {QUESTION_MEMBER_SUBSCRIPTIONS: member_subscriptions_plan()},
    )
    api_client.force_authenticate(user=complex_tenant_data.north_billing_user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_MEMBER_SUBSCRIPTIONS},
        format="json",
    )

    assert response.status_code == 400
    assert "member_subscriptions" in response.data["error"]
    assert "PackageReportsView" in response.data["error"]
    assert "Traceback" not in response.data["error"]
    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.status == SemanticQueryRun.Status.FAILED
    assert run.plan == {}


def test_complex_crafted_plan_cannot_use_unregistered_tenant_field(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    configure_complex_dummy_plans(
        settings,
        {QUESTION_HIDDEN_TENANT_FIELD: hidden_tenant_field_plan()},
    )
    api_client.force_authenticate(user=complex_tenant_data.north_billing_user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_HIDDEN_TENANT_FIELD},
        format="json",
    )

    assert response.status_code == 400
    assert "facility.slug" in response.data["error"]
    assert "Traceback" not in response.data["error"]
    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.status == SemanticQueryRun.Status.FAILED
    assert run.plan == {}


def test_capability_help_for_single_facility_user_avoids_multi_facility_examples(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    """Capability help should not imply broader tenant access than granted."""

    configure_complex_dummy_plans(settings, {})
    api_client.force_authenticate(user=complex_tenant_data.north_billing_user)

    response = api_client.post(
        "/asklens/query/",
        {"question": "What can I query?"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["response_type"] == "capabilities"
    resources = {
        resource["name"]: resource
        for resource in response.data["capabilities"]["resources"]
    }
    assert resources["billing_lines"]["scope"]["level"] == "single"
    assert resources["billing_lines"]["scope"]["kind"] == "facility"
    assert f"facility:{complex_tenant_data.north.id}" not in str(response.data)
    capability_examples = response.data["capabilities"]["examples"]
    suggestion_questions = [
        suggestion["question"]
        for suggestion in response.data["query_help"]["suggestions"]
    ]
    suggestion_text = "\n".join([*capability_examples, *suggestion_questions]).lower()
    assert "list facilities with facility name" not in suggestion_text
    assert "across facilities" not in suggestion_text
    assert "by facility" not in suggestion_text


def test_complex_route_permission_blocks_users_without_reporting_grants(
    settings,
    api_client: APIClient,
    complex_tenant_data: ComplexTenantData,
    registered_complex_resources: None,
) -> None:
    configure_complex_dummy_plans(settings, {})
    api_client.force_authenticate(user=complex_tenant_data.no_report_user)

    response = api_client.get("/asklens/catalog/")
    capabilities_response = api_client.get("/asklens/capabilities/")

    assert response.status_code == 403
    assert capabilities_response.status_code == 403


def test_demo_settings_include_valid_dummy_plans(
    registered_complex_resources: None,
) -> None:
    from tests.test_project.demo_settings import DJANGO_ASKLENS
    from tests.test_project.permissions import all_staff_grant_names

    dummy_plans = DJANGO_ASKLENS["DUMMY_PLANS"]
    assert len(dummy_plans) == 11

    for plan in dummy_plans.values():
        parse_and_validate_query_plan(plan, permissions=all_staff_grant_names())

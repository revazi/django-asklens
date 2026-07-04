"""Multi-tenant and route-security tests for the AskLens API."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from django_asklens.planning.planner import build_planner_request
from tests.test_project.models import Account, AccountMembership, Customer, Order

pytestmark = pytest.mark.django_db

QUESTION_BY_STATUS = "Show my orders by status"
QUESTION_TENANT_FILTER = "List beta tenant orders"
QUESTION_TENANT_FIELD = "List my order tenants"
ACCOUNT_VIEW_PERMISSION = "test_project.view_account"


@dataclass(frozen=True, slots=True)
class TenantData:
    """Users and tenants used by multi-tenant API tests."""

    alpha: Account
    beta: Account
    alpha_user: Any
    beta_user: Any
    staff_user: Any


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_default_registry() -> None:
    """Keep API tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return a DRF API client."""

    return APIClient()


@pytest.fixture
def tenant_data() -> TenantData:
    """Create deterministic multi-tenant data."""

    user_model = get_user_model()
    alpha_user = user_model.objects.create_user(username="alpha-user", password="pw")
    beta_user = user_model.objects.create_user(username="beta-user", password="pw")
    staff_user = user_model.objects.create_user(
        username="staff-user",
        password="pw",
        is_staff=True,
    )
    alpha = Account.objects.create(name="Alpha Co", slug="alpha")
    beta = Account.objects.create(name="Beta Co", slug="beta")
    AccountMembership.objects.create(user=alpha_user, account=alpha)
    AccountMembership.objects.create(user=beta_user, account=beta)

    alice = Customer.objects.create(name="Alice", email="alice@example.com")
    bob = Customer.objects.create(name="Bob", email="bob@example.com")
    Order.objects.bulk_create(
        [
            Order(
                account=alpha,
                customer=alice,
                status="paid",
                created_at=aware_datetime(2026, 1, 1),
                total=Decimal("100.00"),
            ),
            Order(
                account=alpha,
                customer=alice,
                status="paid",
                created_at=aware_datetime(2026, 1, 2),
                total=Decimal("50.00"),
            ),
            Order(
                account=beta,
                customer=bob,
                status="pending",
                created_at=aware_datetime(2026, 1, 3),
                total=Decimal("75.00"),
            ),
            Order(
                account=beta,
                customer=bob,
                status="pending",
                created_at=aware_datetime(2026, 1, 4),
                total=Decimal("25.00"),
            ),
            Order(
                account=beta,
                customer=bob,
                status="pending",
                created_at=aware_datetime(2026, 1, 5),
                total=Decimal("125.00"),
            ),
        ]
    )
    return TenantData(
        alpha=alpha,
        beta=beta,
        alpha_user=alpha_user,
        beta_user=beta_user,
        staff_user=staff_user,
    )


@pytest.fixture
def registered_multitenant_orders() -> None:
    """Register orders with request-aware tenant scoping."""

    def tenant_scoped_orders(request):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return Order.objects.none()
        account_ids = AccountMembership.objects.filter(user=user).values("account_id")
        return Order.objects.filter(account_id__in=account_ids)

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "account.slug": {
                "label": "Tenant",
                "sensitive": True,
                "result_visible": True,
                "requires_permission": ACCOUNT_VIEW_PERMISSION,
            },
            "total": {"label": "Order total", "metric": True},
        },
        metrics=[
            Metric("order_count", op="count", field="id"),
            Metric("tenant_count", op="count", field="account.slug"),
        ],
        base_queryset=tenant_scoped_orders,
    )


def configure_dummy_plan(settings, *, question: str, plan: dict[str, Any]) -> None:
    """Configure the default dummy provider for one question."""

    settings.DJANGO_ASKLENS = {
        "DUMMY_PLANS": {question: plan},
        "MAX_ROWS": 50,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }


def orders_by_status_plan() -> dict[str, Any]:
    """Return a deterministic aggregate plan by order status."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def tenant_filter_plan() -> dict[str, Any]:
    """Return a crafted plan attempting to filter by a sensitive tenant field."""

    return {
        "resource": "orders",
        "intent": "list",
        "filters": [{"field": "account.slug", "op": "eq", "value": "beta"}],
        "select": ["status"],
        "limit": 10,
        "visualization": {"type": "table"},
    }


def tenant_field_plan() -> dict[str, Any]:
    """Return a plan selecting an explicitly permission-gated tenant field."""

    return {
        "resource": "orders",
        "intent": "list",
        "select": ["account.slug", "status"],
        "order_by": [{"field": "status", "direction": "asc"}],
        "limit": 10,
        "visualization": {"type": "table"},
    }


def grant_account_view_permission(user):
    """Grant the Django permission required for the account slug field."""

    content_type = ContentType.objects.get_for_model(Account)
    permission, _created = Permission.objects.get_or_create(
        content_type=content_type,
        codename="view_account",
        defaults={"name": "Can view account"},
    )
    user.user_permissions.add(permission)
    return type(user).objects.get(pk=user.pk)


def test_catalog_endpoint_scopes_fields_and_metrics_to_user_permissions(
    api_client: APIClient,
    tenant_data: TenantData,
    registered_multitenant_orders: None,
) -> None:
    api_client.force_authenticate(user=tenant_data.alpha_user)
    unpermissioned_response = api_client.get("/asklens/catalog/")

    assert unpermissioned_response.status_code == 200
    unpermissioned_catalog = str(unpermissioned_response.data)
    assert "status" in unpermissioned_catalog
    assert "order_count" in unpermissioned_catalog
    assert "account.slug" not in unpermissioned_catalog
    assert "tenant_count" not in unpermissioned_catalog

    alpha_user = grant_account_view_permission(tenant_data.alpha_user)
    api_client.force_authenticate(user=alpha_user)
    permissioned_response = api_client.get("/asklens/catalog/")

    assert permissioned_response.status_code == 200
    permissioned_catalog = str(permissioned_response.data)
    assert "account.slug" in permissioned_catalog
    assert "tenant_count" in permissioned_catalog


def test_planner_prompt_scopes_fields_and_metrics_to_user_permissions(
    tenant_data: TenantData,
    registered_multitenant_orders: None,
) -> None:
    unpermissioned_request = build_planner_request(
        question=QUESTION_TENANT_FIELD,
        registry=default_registry,
    )
    unpermissioned_prompt = "\n".join(
        message["content"] for message in unpermissioned_request.messages
    )

    assert "status" in unpermissioned_prompt
    assert "order_count" in unpermissioned_prompt
    assert "account.slug" not in unpermissioned_prompt
    assert "tenant_count" not in unpermissioned_prompt
    assert "alpha" not in unpermissioned_prompt
    assert "beta" not in unpermissioned_prompt

    alpha_user = grant_account_view_permission(tenant_data.alpha_user)
    permissioned_request = build_planner_request(
        question=QUESTION_TENANT_FIELD,
        registry=default_registry,
        permissions=alpha_user.get_all_permissions(),
    )
    permissioned_prompt = "\n".join(
        message["content"] for message in permissioned_request.messages
    )

    assert "account.slug" in permissioned_prompt
    assert "tenant_count" in permissioned_prompt
    assert "alpha" not in permissioned_prompt
    assert "beta" not in permissioned_prompt


def test_query_endpoint_applies_base_queryset_for_tenant_isolation(
    settings,
    api_client: APIClient,
    tenant_data: TenantData,
    registered_multitenant_orders: None,
) -> None:
    configure_dummy_plan(
        settings,
        question=QUESTION_BY_STATUS,
        plan=orders_by_status_plan(),
    )

    api_client.force_authenticate(user=tenant_data.alpha_user)
    alpha_response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_BY_STATUS},
        format="json",
    )

    assert alpha_response.status_code == 200
    assert alpha_response.data["data"] == [{"status": "paid", "order_count": 2}]

    api_client.force_authenticate(user=tenant_data.beta_user)
    beta_response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_BY_STATUS},
        format="json",
    )

    assert beta_response.status_code == 200
    assert beta_response.data["data"] == [{"status": "pending", "order_count": 3}]


def test_crafted_plan_cannot_filter_by_sensitive_tenant_field_without_permission(
    settings,
    api_client: APIClient,
    tenant_data: TenantData,
    registered_multitenant_orders: None,
) -> None:
    configure_dummy_plan(
        settings,
        question=QUESTION_TENANT_FILTER,
        plan=tenant_filter_plan(),
    )
    api_client.force_authenticate(user=tenant_data.alpha_user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_TENANT_FILTER},
        format="json",
    )

    assert response.status_code == 400
    assert "sensitive" in response.data["error"]
    assert "Traceback" not in response.data["error"]
    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.status == SemanticQueryRun.Status.FAILED
    assert run.plan == {}


def test_permissioned_sensitive_field_still_respects_tenant_base_queryset(
    settings,
    api_client: APIClient,
    tenant_data: TenantData,
    registered_multitenant_orders: None,
) -> None:
    alpha_user = grant_account_view_permission(tenant_data.alpha_user)
    configure_dummy_plan(
        settings,
        question=QUESTION_TENANT_FIELD,
        plan=tenant_field_plan(),
    )
    api_client.force_authenticate(user=alpha_user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_TENANT_FIELD},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"] == [
        {"account.slug": "alpha", "status": "paid"},
        {"account.slug": "alpha", "status": "paid"},
    ]


def test_configured_api_permission_class_applies_to_all_asklens_routes(
    settings,
    api_client: APIClient,
    tenant_data: TenantData,
) -> None:
    settings.DJANGO_ASKLENS = {
        "API_PERMISSION_CLASSES": [
            "tests.test_project.permissions.DenyAskLensAccess",
        ],
        "DUMMY_PLANS": {QUESTION_BY_STATUS: orders_by_status_plan()},
    }
    run = SemanticQueryRun.objects.create(
        user=tenant_data.alpha_user,
        question="private run",
        plan={},
        status=SemanticQueryRun.Status.SUCCESS,
    )
    api_client.force_authenticate(user=tenant_data.alpha_user)

    catalog_response = api_client.get("/asklens/catalog/")
    query_response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION_BY_STATUS},
        format="json",
    )
    run_response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert catalog_response.status_code == 403
    assert query_response.status_code == 403
    assert run_response.status_code == 403
    assert SemanticQueryRun.objects.count() == 1


def test_staff_user_can_view_other_users_run(
    api_client: APIClient,
    tenant_data: TenantData,
) -> None:
    run = SemanticQueryRun.objects.create(
        user=tenant_data.alpha_user,
        question="private run",
        plan={},
        status=SemanticQueryRun.Status.SUCCESS,
    )
    api_client.force_authenticate(user=tenant_data.staff_user)

    response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == run.pk

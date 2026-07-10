"""API tests for Django AskLens."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db

QUESTION = "Show orders by status"


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
def user():
    """Return a regular authenticated user."""

    return get_user_model().objects.create_user(username="regular", password="pw")


@pytest.fixture
def staff_user():
    """Return a staff authenticated user."""

    return get_user_model().objects.create_user(
        username="staff",
        password="pw",
        is_staff=True,
    )


@pytest.fixture
def api_client() -> APIClient:
    """Return a DRF API client."""

    return APIClient()


@pytest.fixture
def order_data() -> None:
    """Create deterministic order data."""

    customer = Customer.objects.create(name="Alice", email="alice@example.com")
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at=aware_datetime(2026, 1, 5),
        total=Decimal("100.00"),
    )
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at=aware_datetime(2026, 1, 6),
        total=Decimal("50.00"),
    )
    Order.objects.create(
        customer=customer,
        status="pending",
        created_at=aware_datetime(2026, 1, 7),
        total=Decimal("75.00"),
    )


@pytest.fixture
def registered_orders() -> None:
    """Register the Order resource in the default registry for API views."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "customer.email": {"label": "Customer email", "sensitive": True},
        },
        metrics=[Metric("order_count", op="count", field="id")],
    )


def valid_plan_payload() -> dict[str, Any]:
    """Return a deterministic QueryPlan payload for API tests."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def configure_dummy_plan(settings, plan: dict[str, Any]) -> None:
    """Configure the default dummy provider for one question."""

    settings.DJANGO_ASKLENS = {
        "DUMMY_PLANS": {QUESTION: plan},
        "MAX_ROWS": 50,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }


def test_catalog_endpoint_requires_authentication(
    api_client: APIClient,
    registered_orders: None,
    user,
) -> None:
    unauthenticated = api_client.get("/asklens/catalog/")
    assert unauthenticated.status_code in {401, 403}

    api_client.force_authenticate(user=user)
    response = api_client.get("/asklens/catalog/")

    assert response.status_code == 200
    catalog_text = str(response.data)
    assert "status" in catalog_text
    assert "customer.email" not in catalog_text


def test_capabilities_endpoint_returns_permission_scoped_query_guidance(
    api_client: APIClient,
    registered_orders: None,
    user,
) -> None:
    """Capabilities explain what a requester can query without exposing rows."""

    unauthenticated = api_client.get("/asklens/capabilities/")
    assert unauthenticated.status_code in {401, 403}

    api_client.force_authenticate(user=user)
    response = api_client.get("/asklens/capabilities/")

    assert response.status_code == 200
    assert response.data["summary"] == (
        "You can ask read-only list and aggregate questions over 1 resource."
    )
    assert response.data["query_patterns"]
    assert response.data["limitations"]
    [resource] = response.data["resources"]
    assert resource["name"] == "orders"
    assert resource["label"] == "Orders"
    assert {field["name"] for field in resource["fields"]} == {
        "id",
        "status",
        "created_at",
    }
    assert resource["metrics"][0]["name"] == "order_count"
    assert "Show count of Orders by Status" in resource["examples"]
    assert "customer.email" not in str(response.data)


def test_query_endpoint_intercepts_capabilities_question_without_provider_or_audit(
    api_client: APIClient,
    registered_orders: None,
    user,
) -> None:
    """Natural-language help questions should return capabilities locally."""

    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/asklens/query/",
        {"question": "What can I query?"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["question"] == "What can I query?"
    assert response.data["response_type"] == "capabilities"
    assert response.data["capabilities"]["summary"] == (
        "You can ask read-only list and aggregate questions over 1 resource."
    )
    assert response.data["capabilities"]["resources"][0]["name"] == "orders"
    assert response.data["routing_source"] == "fallback"
    assert response.data["capability_intent"]["intent"] == "capabilities"
    assert "database query" in response.data["explanation"]
    assert "run_id" not in response.data
    assert "plan" not in response.data
    assert SemanticQueryRun.objects.count() == 0


def test_query_endpoint_returns_result_and_records_successful_run(
    settings,
    api_client: APIClient,
    user,
    order_data: None,
    registered_orders: None,
) -> None:
    configure_dummy_plan(settings, valid_plan_payload())
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["question"] == QUESTION
    assert response.data["plan"]["resource"] == "orders"
    assert response.data["data"] == [
        {"status": "paid", "order_count": 2},
        {"status": "pending", "order_count": 1},
    ]
    assert response.data["visualization"] == {
        "type": "bar",
        "x": {"field": "status", "label": "Status", "type": "string"},
        "y": {"field": "order_count", "label": "Order Count", "type": "number"},
    }

    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.user == user
    assert run.status == SemanticQueryRun.Status.SUCCESS
    assert run.row_count == 2
    assert run.error == ""
    assert run.plan["resource"] == "orders"


def test_query_endpoint_can_return_serialized_data_without_visualization_hint(
    settings,
    api_client: APIClient,
    user,
    order_data: None,
    registered_orders: None,
) -> None:
    configure_dummy_plan(settings, valid_plan_payload())
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION, "include_visualization": False},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["columns"]
    assert response.data["data"] == [
        {"status": "paid", "order_count": 2},
        {"status": "pending", "order_count": 1},
    ]
    assert "visualization" not in response.data


def test_query_errors_are_audited_safely(
    settings,
    api_client: APIClient,
    user,
    registered_orders: None,
) -> None:
    bad_plan = valid_plan_payload()
    bad_plan["group_by"] = [{"field": "missing"}]
    bad_plan["visualization"] = {"type": "bar", "x": "missing", "y": "order_count"}
    configure_dummy_plan(settings, bad_plan)
    api_client.force_authenticate(user=user)

    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["status"] == SemanticQueryRun.Status.FAILED
    assert "missing" in response.data["error"]
    assert "Traceback" not in response.data["error"]

    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.status == SemanticQueryRun.Status.FAILED
    assert run.plan == {}
    assert "missing" in run.error


def test_run_detail_endpoint_returns_owned_run(
    settings,
    api_client: APIClient,
    user,
    order_data: None,
    registered_orders: None,
) -> None:
    configure_dummy_plan(settings, valid_plan_payload())
    api_client.force_authenticate(user=user)
    query_response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION},
        format="json",
    )

    response = api_client.get(f"/asklens/runs/{query_response.data['run_id']}/")

    assert response.status_code == 200
    assert response.data["id"] == query_response.data["run_id"]
    assert response.data["status"] == SemanticQueryRun.Status.SUCCESS


def test_run_detail_endpoint_blocks_other_regular_users(api_client: APIClient) -> None:
    user_model = get_user_model()
    owner = user_model.objects.create_user(username="owner", password="pw")
    other = user_model.objects.create_user(username="other", password="pw")
    run = SemanticQueryRun.objects.create(
        user=owner,
        question="Private question",
        plan={},
        status=SemanticQueryRun.Status.SUCCESS,
    )

    api_client.force_authenticate(user=other)
    response = api_client.get(f"/asklens/runs/{run.pk}/")

    assert response.status_code == 403


def test_debug_mode_is_staff_only(
    settings,
    api_client: APIClient,
    user,
    staff_user,
    order_data: None,
    registered_orders: None,
) -> None:
    configure_dummy_plan(settings, valid_plan_payload())

    api_client.force_authenticate(user=user)
    forbidden = api_client.post(
        "/asklens/query/",
        {"question": QUESTION, "debug": True},
        format="json",
    )
    assert forbidden.status_code == 403
    assert SemanticQueryRun.objects.count() == 0

    api_client.force_authenticate(user=staff_user)
    response = api_client.post(
        "/asklens/query/",
        {"question": QUESTION, "debug": True},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["debug"]["validated_plan"]["resource"] == "orders"

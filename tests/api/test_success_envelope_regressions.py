"""API-4b regressions for explicit successful query/help composition."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.contracts._generation import validate_contract_document
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolate_registry() -> None:
    """Keep the API-4b catalog isolated from other tests."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return an authenticated API client."""

    user = get_user_model().objects.create_user(username="api4b-envelope-user")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def registered_orders() -> None:
    """Register one empty synthetic resource for query and help responses."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        timezone="UTC",
        scope_mode="global",
        fields={
            "status": {
                "binding": "status",
                "type": "string",
                "nullable": False,
            }
        },
        metrics=[
            Metric("order_count", op="count", binding="id", result_type="integer")
        ],
    )


def empty_grouped_plan() -> dict[str, Any]:
    """Return a grouped plan whose complete result includes ``empty``."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"metric": "order_count"}],
        "limit": 10,
    }


def test_query_success_embeds_the_complete_exact_result_document(
    api_client: APIClient,
    registered_orders: None,
) -> None:
    """The query wrapper nests every core result member, including ``empty``."""

    response = api_client.post(
        "/asklens/query/",
        {
            "question": "Count synthetic orders by status",
            "plan": empty_grouped_plan(),
            "presentation": {"kind": "table"},
        },
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data) == {
        "question",
        "response_type",
        "plan",
        "result",
        "explanation",
        "run_id",
        "presentation",
    }
    assert response.data["response_type"] == "query"
    assert response.data["result"] == {
        "columns": [
            {"key": "status", "label": "Status", "type": "string", "nullable": False},
            {
                "key": "order_count",
                "label": "Order Count",
                "type": "integer",
                "nullable": False,
            },
        ],
        "data": [],
        "row_count": 0,
        "empty": True,
        "duration_ms": response.data["result"]["duration_ms"],
        "result_metadata": {
            "limit": 10,
            "limit_scope": "groups",
            "truncated": False,
        },
    }
    validate_contract_document("result", response.data["result"])
    for spread_member in (
        "columns",
        "data",
        "row_count",
        "empty",
        "duration_ms",
        "result_metadata",
    ):
        assert spread_member not in response.data

    run = SemanticQueryRun.objects.get(pk=response.data["run_id"])
    assert run.status == SemanticQueryRun.Status.SUCCESS
    assert run.row_count == response.data["result"]["row_count"]


def test_capabilities_success_separates_machine_documents_routing_and_help(
    api_client: APIClient,
    registered_orders: None,
) -> None:
    """Machine documents stay exact while routing and human help are explicit."""

    response = api_client.post(
        "/asklens/query/",
        {"question": "What can I query?"},
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data) == {
        "question",
        "response_type",
        "routing",
        "capabilities",
        "catalog",
        "help",
        "explanation",
    }
    assert response.data["response_type"] == "capabilities"
    assert set(response.data["routing"]) == {"intent", "source"}
    assert response.data["routing"]["intent"]["intent"] == "capabilities"
    assert response.data["routing"]["source"] == "fallback"
    assert set(response.data["help"]) == {"source", "content"}
    assert response.data["help"]["source"] == "deterministic"
    assert response.data["help"]["content"]["suggestions"]
    assert "error" not in response.data["help"]
    validate_contract_document("capabilities", response.data["capabilities"])
    validate_contract_document("catalog", response.data["catalog"])

    for spread_member in (
        "capability_intent",
        "routing_source",
        "query_help_source",
        "query_help",
        "query_help_error",
    ):
        assert spread_member not in response.data
    assert SemanticQueryRun.objects.count() == 0

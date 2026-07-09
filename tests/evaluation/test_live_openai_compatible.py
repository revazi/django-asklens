"""Opt-in live OpenAI-compatible provider smoke test.

This module is skipped by default. It is intended for private integration checks,
not normal CI.
"""

import os
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from django_asklens import Metric
from django_asklens.catalog.registry import CatalogRegistry
from django_asklens.execution import run_query_plan
from django_asklens.llms import get_llm_provider
from django_asklens.planning import plan_question
from tests.test_project.models import Account, AccountMembership, Customer, Order

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("DJANGO_ASKLENS_LIVE_LLM") != "1",
        reason="Set DJANGO_ASKLENS_LIVE_LLM=1 to run live provider tests.",
    ),
]

QUESTION = "Show my orders by status as a bar chart"


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for live smoke fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


@pytest.fixture
def live_settings(settings):
    """Configure AskLens from environment variables for a live smoke test."""

    api_key = os.environ.get("DJANGO_ASKLENS_LIVE_LLM_API_KEY")
    model = os.environ.get("DJANGO_ASKLENS_LIVE_LLM_MODEL")
    base_url = os.environ.get(
        "DJANGO_ASKLENS_LIVE_LLM_BASE_URL",
        "https://api.openai.com/v1",
    )
    if not api_key or not model:
        pytest.skip(
            "Set DJANGO_ASKLENS_LIVE_LLM_API_KEY and "
            "DJANGO_ASKLENS_LIVE_LLM_MODEL for live provider tests."
        )

    settings.DJANGO_ASKLENS = {
        "LLM_BACKEND": "openai_compatible",
        "LLM_BASE_URL": base_url,
        "LLM_API_KEY": api_key,
        "LLM_MODEL": model,
        "LLM_TIMEOUT_SECONDS": 45,
        "MAX_ROWS": 50,
        "MAX_JOINS": 2,
        "MAX_METRICS": 5,
        "MAX_GROUP_BY": 3,
    }


@pytest.fixture
def tenant_order_context():
    """Create a small tenant-scoped registry and request context."""

    user_model = AccountMembership._meta.get_field("user").remote_field.model
    user = user_model.objects.create_user(username="live-alpha", password="pw")
    account = Account.objects.create(name="Live Alpha", slug="live-alpha")
    AccountMembership.objects.create(user=user, account=account)
    customer = Customer.objects.create(name="Live Alice", email="live@example.com")
    Order.objects.bulk_create(
        [
            Order(
                account=account,
                customer=customer,
                status="paid",
                created_at=aware_datetime(2026, 1, 1),
                total=Decimal("100.00"),
            ),
            Order(
                account=account,
                customer=customer,
                status="pending",
                created_at=aware_datetime(2026, 1, 2),
                total=Decimal("50.00"),
            ),
        ]
    )

    def tenant_scoped_orders(request):
        account_ids = AccountMembership.objects.filter(
            user=request.user,
        ).values("account_id")
        return Order.objects.filter(account_id__in=account_ids)

    registry = CatalogRegistry()
    registry.register(
        model=Order,
        name="orders",
        label="Orders",
        default_date_field="created_at",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "total": {"label": "Order total", "metric": True},
            "account.slug": {
                "label": "Tenant",
                "sensitive": True,
                "requires_permission": "test_project.view_account",
            },
        },
        metrics=[Metric("order_count", op="count", field="id")],
        base_queryset=tenant_scoped_orders,
    )
    return registry, SimpleNamespace(user=user)


def test_live_openai_compatible_provider_can_plan_and_execute_tenant_query(
    live_settings,
    tenant_order_context,
) -> None:
    registry, request = tenant_order_context

    planner_result = plan_question(
        QUESTION,
        provider=get_llm_provider(),
        registry=registry,
        permissions=request.user.get_all_permissions(),
    )
    result = run_query_plan(planner_result.plan, registry=registry, request=request)

    assert planner_result.plan.resource == "orders"
    assert planner_result.plan.intent == "aggregate"
    assert result.row_count >= 1

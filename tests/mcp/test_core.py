"""Tests for framework-neutral MCP adapter helpers."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.mcp import (
    AskLensMCPToolSet,
    asklens_capabilities,
    asklens_execute_plan,
    asklens_query,
    asklens_validate_plan,
)
from django_asklens.models import SemanticQueryRun
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_default_registry() -> Iterator[None]:
    """Keep MCP adapter tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def user():
    """Return an authenticated user for request-like MCP contexts."""

    return get_user_model().objects.create_user(username="mcp-user", password="pw")


@pytest.fixture
def mcp_request(settings, user):
    """Return a request-like object with MCP-mapped permission strings."""

    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": lambda request: getattr(
            request,
            "asklens_permissions",
            (),
        ),
        "DUMMY_PLANS": {"Show orders by status": valid_aggregate_plan()},
    }
    return SimpleNamespace(user=user, asklens_permissions=frozenset())


@pytest.fixture
def registered_orders() -> None:
    """Register an order resource with a permission-gated sensitive field."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
            "customer.email": {
                "label": "Customer email",
                "sensitive": True,
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[Metric("order_count", op="count", field="id")],
    )


@pytest.fixture
def order_data() -> None:
    """Create deterministic order rows for MCP execution tests."""

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


def aware_datetime(year: int, month: int, day: int) -> datetime:
    """Return a UTC-aware datetime for fixtures."""

    return datetime(year, month, day, 12, 0, tzinfo=UTC)


def valid_aggregate_plan() -> dict[str, Any]:
    """Return a deterministic aggregate QueryPlan payload."""

    return {
        "resource": "orders",
        "intent": "aggregate",
        "group_by": [{"field": "status"}],
        "metrics": [{"name": "order_count", "op": "count", "field": "id"}],
        "order_by": [{"metric": "order_count", "direction": "desc"}],
        "limit": 10,
        "visualization": {"type": "bar", "x": "status", "y": "order_count"},
    }


def sensitive_list_plan() -> dict[str, Any]:
    """Return a plan that requires the customer PII permission."""

    return {
        "resource": "orders",
        "intent": "list",
        "select": ["customer.email"],
        "limit": 10,
        "visualization": {"type": "table"},
    }


def test_mcp_capabilities_are_permission_scoped(
    registered_orders: None,
    mcp_request,
) -> None:
    """Capabilities expose metadata/schema only and honor request permissions."""

    payload = asklens_capabilities(mcp_request)

    assert payload["response_type"] == "capabilities"
    assert payload["rows_omitted"] is True
    assert payload["executed"] is False
    assert "query_plan_schema" in payload
    [resource] = payload["capabilities"]["resources"]
    assert {field["name"] for field in resource["fields"]} == {
        "id",
        "status",
        "created_at",
    }
    assert "alice@example.com" not in str(payload)

    mcp_request.asklens_permissions = frozenset({"shop.view_customer_pii"})

    payload_with_pii_permission = asklens_capabilities(mcp_request)
    [resource] = payload_with_pii_permission["capabilities"]["resources"]
    assert "customer.email" in {field["name"] for field in resource["fields"]}
    assert "alice@example.com" not in str(payload_with_pii_permission)


def test_mcp_validate_plan_does_not_execute_or_audit(
    registered_orders: None,
    mcp_request,
) -> None:
    """Plan validation returns normalized plan JSON without touching rows."""

    payload = asklens_validate_plan(mcp_request, valid_aggregate_plan())

    assert payload["response_type"] == "plan_validation"
    assert payload["valid"] is True
    assert payload["executed"] is False
    assert payload["rows_omitted"] is True
    assert payload["plan"]["resource"] == "orders"
    assert SemanticQueryRun.objects.count() == 0


def test_mcp_validate_plan_returns_safe_error_for_unauthorized_fields(
    registered_orders: None,
    mcp_request,
) -> None:
    """Unauthorized client-produced plans are rejected before execution."""

    payload = asklens_validate_plan(mcp_request, sensitive_list_plan())

    assert payload == {
        "response_type": "plan_validation",
        "valid": False,
        "executed": False,
        "rows_omitted": True,
        "error_category": "permission_denied",
        "error": (
            "Field 'customer.email' is sensitive and requires explicit permission."
        ),
    }
    assert SemanticQueryRun.objects.count() == 0


def test_mcp_validate_plan_returns_plan_validation_category(
    registered_orders: None,
    mcp_request,
) -> None:
    """Malformed client-produced plans get an MCP-specific safe category."""

    payload = asklens_validate_plan(mcp_request, {"resource": "orders"})

    assert payload["valid"] is False
    assert payload["executed"] is False
    assert payload["error_category"] == "plan_validation_error"
    assert SemanticQueryRun.objects.count() == 0


def test_mcp_execute_plan_omits_rows_by_default(
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """MCP execution audits and returns metadata while omitting rows by default."""

    payload = asklens_execute_plan(mcp_request, valid_aggregate_plan())

    assert payload["response_type"] == "query"
    assert payload["row_count"] == 2
    assert payload["columns"] == [
        {"key": "status", "label": "Status", "type": "string"},
        {"key": "order_count", "label": "Order Count", "type": "number"},
    ]
    assert payload["data"] == []
    assert payload["rows_omitted"] is True
    assert "row_return_policy" in payload
    assert "paid" not in str(payload)
    assert "pending" not in str(payload)
    assert SemanticQueryRun.objects.count() == 1
    assert SemanticQueryRun.objects.get().question == "MCP submitted QueryPlan"


def test_mcp_execute_plan_returns_safe_error_for_rejected_plan(
    registered_orders: None,
    mcp_request,
) -> None:
    """Rejected execute attempts return safe MCP-shaped errors and audit."""

    payload = asklens_execute_plan(mcp_request, sensitive_list_plan())

    assert payload["response_type"] == "error"
    assert payload["status_code"] == 400
    assert payload["status"] == SemanticQueryRun.Status.FAILED
    assert payload["error"] == (
        "Field 'customer.email' is sensitive and requires explicit permission."
    )
    assert "data" not in payload
    run = SemanticQueryRun.objects.get()
    assert run.status == SemanticQueryRun.Status.FAILED
    assert run.row_count == 0


def test_mcp_execute_plan_denies_explicit_rows_by_default(
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """include_rows=True is denied unless MCP row return is enabled."""

    payload = asklens_execute_plan(
        mcp_request,
        valid_aggregate_plan(),
        include_rows=True,
    )

    assert payload["rows_omitted"] is True
    assert payload["row_return_denied"] is True
    assert payload["data"] == []
    assert "paid" not in str(payload)
    assert "pending" not in str(payload)


def test_mcp_execute_plan_can_include_rows_when_setting_allows_it(
    settings,
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """Rows require both include_rows=True and MCP_ALLOW_ROW_RETURN=True."""

    settings.DJANGO_ASKLENS["MCP_ALLOW_ROW_RETURN"] = True

    payload = asklens_execute_plan(
        mcp_request,
        valid_aggregate_plan(),
        include_rows=True,
    )

    assert payload["rows_omitted"] is False
    assert payload["data"] == [
        {"status": "paid", "order_count": 2},
        {"status": "pending", "order_count": 1},
    ]


def test_asklens_mcp_toolset_wraps_tools_with_context_factory(
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """AskLens-owned wrappers can be registered with generic MCP servers."""

    seen_contexts = []

    def request_factory(context):
        seen_contexts.append(context)
        return mcp_request

    toolset = AskLensMCPToolSet(request_factory=request_factory)
    context = object()

    capabilities = toolset.asklens_capabilities(context)
    validation = toolset.asklens_validate_plan(context, valid_aggregate_plan())
    execution = toolset.asklens_execute_plan(
        context,
        valid_aggregate_plan(),
        include_rows=True,
    )

    assert seen_contexts == [context, context, context]
    assert capabilities["response_type"] == "capabilities"
    assert validation["valid"] is True
    assert execution["response_type"] == "query"
    assert execution["rows_omitted"] is True
    assert execution["row_return_denied"] is True
    assert sorted(toolset.tools()) == [
        "asklens_capabilities",
        "asklens_execute_plan",
        "asklens_validate_plan",
    ]


def test_asklens_mcp_toolset_query_tool_is_disabled_by_default(
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """The question wrapper is opt-in because it may call a provider."""

    toolset = AskLensMCPToolSet(request_factory=lambda _context: mcp_request)

    payload = toolset.asklens_query(object(), "Show orders by status")

    assert payload == {
        "response_type": "error",
        "error_category": "tool_disabled",
        "error": (
            "The AskLens MCP query tool is disabled. Use asklens_capabilities, "
            "asklens_validate_plan, and asklens_execute_plan, or construct the "
            "toolset with expose_query_tool=True."
        ),
    }
    assert "asklens_query" not in toolset.tools()


def test_asklens_mcp_toolset_can_expose_query_tool_explicitly(
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """The optional question wrapper still applies MCP row policy."""

    toolset = AskLensMCPToolSet(
        request_factory=lambda _context: mcp_request,
        expose_query_tool=True,
    )

    payload = toolset.asklens_query(object(), "Show orders by status")

    assert payload["response_type"] == "query"
    assert payload["row_count"] == 2
    assert payload["data"] == []
    assert payload["rows_omitted"] is True
    assert "asklens_query" in toolset.tools()


def test_mcp_query_wrapper_uses_existing_orchestration_and_row_policy(
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """The question wrapper is available but still omits rows by default."""

    payload = asklens_query(mcp_request, "Show orders by status")

    assert payload["response_type"] == "query"
    assert payload["row_count"] == 2
    assert payload["data"] == []
    assert payload["rows_omitted"] is True

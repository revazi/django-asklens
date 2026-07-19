"""Concrete test-project MCP integration example tests."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from tests.test_project.mcp import (
    AskLensTestMCPContext,
    InMemoryMCPServer,
    build_asklens_mcp_toolset,
    register_asklens_mcp_tools,
)
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_default_registry() -> Iterator[None]:
    """Keep the concrete MCP example isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def user():
    """Return an authenticated test-project MCP user."""

    return get_user_model().objects.create_user(username="mcp-demo-user")


@pytest.fixture
def mcp_settings(settings) -> None:
    """Configure AskLens permissions for the test-project MCP example."""

    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.mcp.get_asklens_mcp_request_permissions"
        ),
        "DUMMY_PLANS": {"Show orders by status": valid_aggregate_plan()},
    }


@pytest.fixture
def registered_orders() -> None:
    """Register a resource used by the concrete MCP example."""

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
                "result_visible": True,
                "requires_permission": "shop.view_customer_pii",
            },
        },
        metrics=[Metric("order_count", op="count", field="id", label="Orders")],
    )


@pytest.fixture
def order_data() -> None:
    """Create deterministic data for the concrete MCP example."""

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


def sensitive_plan() -> dict[str, Any]:
    """Return a plan that needs server-derived PII permission."""

    return {
        "resource": "orders",
        "intent": "list",
        "select": ["customer.email"],
        "limit": 10,
        "visualization": {"type": "table"},
    }


def test_test_project_registers_asklens_tools_on_mcp_server(
    mcp_settings: None,
    registered_orders: None,
    user,
) -> None:
    """The test project shows how a host MCP server registers AskLens tools."""

    server = InMemoryMCPServer()
    register_asklens_mcp_tools(server)

    assert sorted(server.tools) == [
        "asklens_capabilities",
        "asklens_describe_resource",
        "asklens_execute_plan",
        "asklens_query_plan_schema",
        "asklens_validate_plan",
    ]

    context = AskLensTestMCPContext(user=user)
    payload = server.call_tool("asklens_capabilities", context)
    schema = server.call_tool("asklens_query_plan_schema", context)
    resource_description = server.call_tool(
        "asklens_describe_resource",
        context,
        resource="orders",
    )

    assert payload["response_type"] == "capabilities"
    assert payload["executed"] is False
    assert payload["rows_omitted"] is True
    assert "query_plan_schema" in payload
    assert schema["response_type"] == "query_plan_schema"
    assert resource_description["valid"] is True
    [resource] = payload["capabilities"]["resources"]
    assert {field["name"] for field in resource["fields"]} == {
        "id",
        "status",
        "created_at",
    }


def test_test_project_mcp_plan_flow_validates_then_executes_without_rows(
    mcp_settings: None,
    registered_orders: None,
    order_data: None,
    user,
) -> None:
    """The concrete example demonstrates MCP-native client-side planning."""

    server = InMemoryMCPServer()
    register_asklens_mcp_tools(server)
    context = AskLensTestMCPContext(user=user)

    validation = server.call_tool(
        "asklens_validate_plan",
        context,
        plan=valid_aggregate_plan(),
    )
    execution = server.call_tool(
        "asklens_execute_plan",
        context,
        plan=validation["plan"],
        include_rows=True,
    )

    assert validation["valid"] is True
    assert validation["executed"] is False
    assert execution["response_type"] == "query"
    assert execution["row_count"] == 2
    assert execution["data"] == []
    assert execution["rows_omitted"] is True
    assert execution["row_return_denied"] is True
    assert "paid" not in str(execution)
    assert "pending" not in str(execution)


def test_test_project_mcp_context_permissions_are_server_derived(
    mcp_settings: None,
    registered_orders: None,
    user,
) -> None:
    """The example derives permissions from context, not tool arguments."""

    server = InMemoryMCPServer()
    register_asklens_mcp_tools(server)
    no_pii_context = AskLensTestMCPContext(user=user)
    pii_context = AskLensTestMCPContext(
        user=user,
        asklens_permissions=frozenset({"shop.view_customer_pii"}),
    )

    denied = server.call_tool(
        "asklens_validate_plan",
        no_pii_context,
        plan=sensitive_plan(),
    )
    allowed = server.call_tool(
        "asklens_validate_plan",
        pii_context,
        plan=sensitive_plan(),
    )

    assert denied["valid"] is False
    assert denied["error_category"] == "permission_denied"
    assert allowed["valid"] is True
    assert allowed["plan"]["select"] == ["customer.email"]


def test_test_project_mcp_can_opt_into_query_tool(
    mcp_settings: None,
    registered_orders: None,
    order_data: None,
    user,
) -> None:
    """The AskLens-managed question tool is visible only when opted in."""

    server = InMemoryMCPServer()
    register_asklens_mcp_tools(
        server,
        toolset=build_asklens_mcp_toolset(expose_query_tool=True),
    )

    assert "asklens_query" in server.tools

    payload = server.call_tool(
        "asklens_query",
        AskLensTestMCPContext(user=user),
        question="Show orders by status",
    )

    assert payload["response_type"] == "query"
    assert payload["row_count"] == 2
    assert payload["data"] == []
    assert payload["rows_omitted"] is True


def test_test_project_mcp_row_return_requires_project_setting(
    settings,
    mcp_settings: None,
    registered_orders: None,
    order_data: None,
    user,
) -> None:
    """Rows return only when the test project explicitly enables them."""

    settings.DJANGO_ASKLENS["MCP_ALLOW_ROW_RETURN"] = True
    server = InMemoryMCPServer()
    register_asklens_mcp_tools(server)

    payload = server.call_tool(
        "asklens_execute_plan",
        AskLensTestMCPContext(user=user),
        plan=valid_aggregate_plan(),
        include_rows=True,
    )

    assert payload["rows_omitted"] is False
    assert payload["data"] == [
        {"status": "paid", "order_count": 2},
        {"status": "pending", "order_count": 1},
    ]

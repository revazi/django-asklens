"""Tests for the runnable test project's opt-in FastMCP server."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from django_asklens import Metric
from django_asklens.catalog.registry import default_registry
from django_asklens.mcp import AskLensMCPToolSet, create_fastmcp_server
from tests.test_project.mcp_server import create_demo_asklens_mcp_server
from tests.test_project.models import Customer, Order

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clear_default_registry() -> Iterator[None]:
    """Keep FastMCP server tests isolated from global catalog state."""

    default_registry.clear()
    yield
    default_registry.clear()


@pytest.fixture
def user():
    """Return the server-side authenticated MCP demo user."""

    return get_user_model().objects.create_user(username="mcp-server-user")


@pytest.fixture
def mcp_server_settings(settings, user) -> None:
    """Configure the test-project FastMCP bridge for a simple resource."""

    settings.TEST_PROJECT_REGISTER_COMPLEX_ASKLENS = False
    settings.DJANGO_ASKLENS_MCP_USERNAME = user.username
    settings.DJANGO_ASKLENS_MCP_EXPOSE_QUERY = False
    settings.DJANGO_ASKLENS = {
        "REQUEST_PERMISSIONS_GETTER": (
            "tests.test_project.mcp.get_asklens_mcp_request_permissions"
        ),
        "DUMMY_PLANS": {"Show orders by status": valid_aggregate_plan()},
    }


@pytest.fixture
def registered_orders() -> None:
    """Register a resource used by the FastMCP bridge tests."""

    default_registry.register(
        model=Order,
        name="orders",
        label="Orders",
        fields={
            "id": {"label": "Order ID"},
            "status": {"label": "Status"},
            "created_at": {"label": "Created date"},
        },
        metrics=[Metric("order_count", op="count", field="id", label="Orders")],
    )


@pytest.fixture
def order_data() -> None:
    """Create deterministic data for FastMCP execution tests."""

    customer = Customer.objects.create(name="Alice", email="alice@example.com")
    Order.objects.create(
        customer=customer,
        status="paid",
        created_at=aware_datetime(2026, 1, 5),
        total=Decimal("100.00"),
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


def test_demo_fastmcp_server_registers_asklens_tools(
    mcp_server_settings: None,
    registered_orders: None,
) -> None:
    """The demo FastMCP server exposes AskLens tools over MCP."""

    async def run() -> list[str]:
        server = create_demo_asklens_mcp_server()
        tools = await server.list_tools()
        return sorted(tool.name for tool in tools)

    assert asyncio.run(run()) == [
        "asklens_capabilities",
        "asklens_describe_resource",
        "asklens_execute_plan",
        "asklens_query_plan_schema",
        "asklens_validate_plan",
    ]


def test_fastmcp_bridge_passes_context_to_toolset_request_factory(
    mcp_server_settings: None,
    registered_orders: None,
    user,
) -> None:
    """FastMCP context reaches the host-provided request factory."""

    seen_contexts: list[Any] = []

    def request_factory(context: Any) -> Any:
        seen_contexts.append(context)
        return SimpleNamespace(
            user=user,
            asklens_permissions=frozenset(),
            tenant_scope={},
        )

    async def run() -> dict[str, Any]:
        toolset = AskLensMCPToolSet(
            request_factory=request_factory,
            include_query_plan_schema=False,
            capabilities_resource_detail="summary",
        )
        server = create_fastmcp_server(toolset)
        result = await server.call_tool("asklens_capabilities", {})
        return result.structured_content

    payload = asyncio.run(run())

    assert payload["response_type"] == "capabilities"
    assert len(seen_contexts) == 1
    assert seen_contexts[0].__class__.__name__ == "Context"


def test_demo_fastmcp_server_capabilities_are_compact_by_default(
    mcp_server_settings: None,
    registered_orders: None,
) -> None:
    """FastMCP capability discovery stays compact for MCP clients."""

    async def run() -> dict[str, Any]:
        server = create_demo_asklens_mcp_server()
        result = await server.call_tool("asklens_capabilities", {})
        return result.structured_content

    payload = asyncio.run(run())

    assert payload["response_type"] == "capabilities"
    assert "query_plan_schema" not in payload
    [resource] = payload["capabilities"]["resources"]
    assert resource["field_names"] == ["id", "status", "created_at"]
    assert resource["metric_names"] == ["order_count"]
    assert "fields" not in resource


def test_demo_fastmcp_server_exposes_schema_and_resource_description_tools(
    mcp_server_settings: None,
    registered_orders: None,
) -> None:
    """FastMCP clients can fetch schema/resource details separately."""

    async def run() -> dict[str, Any]:
        server = create_demo_asklens_mcp_server()
        schema = await server.call_tool("asklens_query_plan_schema", {})
        resource = await server.call_tool(
            "asklens_describe_resource",
            {"resource": "orders"},
        )
        return {
            "schema": schema.structured_content,
            "resource": resource.structured_content,
        }

    payload = asyncio.run(run())

    assert payload["schema"]["response_type"] == "query_plan_schema"
    assert payload["schema"]["query_plan_schema"]["title"] == "QueryPlan"
    assert payload["resource"]["response_type"] == "resource_description"
    assert payload["resource"]["valid"] is True
    assert {field["name"] for field in payload["resource"]["resource"]["fields"]} == {
        "id",
        "status",
        "created_at",
    }


def test_demo_fastmcp_server_executes_asklens_plan_without_rows_by_default(
    mcp_server_settings: None,
    registered_orders: None,
    order_data: None,
) -> None:
    """FastMCP tool calls go through AskLens validation and row-return policy."""

    async def run() -> dict[str, Any]:
        server = create_demo_asklens_mcp_server()
        result = await server.call_tool(
            "asklens_execute_plan",
            {
                "plan": valid_aggregate_plan(),
                "include_rows": True,
            },
        )
        return result.structured_content

    payload = asyncio.run(run())

    assert payload["response_type"] == "query"
    assert payload["row_count"] == 2
    assert payload["data"] == []
    assert payload["rows_omitted"] is True
    assert payload["row_return_denied"] is True
    assert "paid" not in str(payload)
    assert "pending" not in str(payload)


def test_demo_fastmcp_server_can_expose_query_tool_when_enabled(
    settings,
    mcp_server_settings: None,
    registered_orders: None,
) -> None:
    """The provider-backed question tool remains explicitly opt-in."""

    settings.DJANGO_ASKLENS_MCP_EXPOSE_QUERY = True

    async def run() -> list[str]:
        server = create_demo_asklens_mcp_server()
        tools = await server.list_tools()
        return sorted(tool.name for tool in tools)

    assert "asklens_query" in asyncio.run(run())


def test_demo_asgi_defaults_to_plain_django_when_mcp_disabled() -> None:
    """The ASGI app should not require FastMCP when the demo endpoint is off."""

    with override_settings(DJANGO_ASKLENS_MCP_ENABLED=False):
        from tests.test_project.demo_asgi import build_application

        application = build_application()

    assert application.__class__.__name__ == "ASGIHandler"


def test_demo_asgi_mounts_mcp_endpoint_when_enabled(
    settings,
    mcp_server_settings: None,
    registered_orders: None,
) -> None:
    """When enabled, the demo ASGI app exposes /mcp plus normal Django routes."""

    settings.DJANGO_ASKLENS_MCP_ENABLED = True
    with override_settings(DJANGO_ASKLENS_MCP_ENABLED=True):
        from tests.test_project.demo_asgi import build_application

        application = build_application()

    routes = {getattr(route, "path", "") for route in application.routes}
    assert "/mcp" in routes
    assert "" in routes


def test_demo_asgi_serves_admin_staticfiles_for_uvicorn() -> None:
    """The Uvicorn demo app should keep Django admin CSS/JS working locally."""

    demo_installed_apps = [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "rest_framework",
        "django_asklens",
        "tests.test_project.apps.TestProjectConfig",
    ]

    async def run(application) -> tuple[int, str, str]:
        import httpx

        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/static/admin/css/base.css")
        return (
            response.status_code,
            response.headers.get("content-type", ""),
            response.text,
        )

    with override_settings(
        DJANGO_ASKLENS_MCP_ENABLED=False,
        INSTALLED_APPS=demo_installed_apps,
        STATIC_URL="/static/",
    ):
        from tests.test_project.demo_asgi import build_application

        application = build_application()
        assert application.__class__.__name__ == "ASGIStaticFilesHandler"
        status_code, content_type, body = asyncio.run(run(application))

    assert status_code == 200
    assert content_type.startswith("text/css")
    assert "body" in body

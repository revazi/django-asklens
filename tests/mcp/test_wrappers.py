"""Tests for dependency-free MCP toolset wrappers."""

import pytest

from django_asklens.mcp import AskLensMCPToolSet
from tests.mcp._support import valid_aggregate_plan

pytestmark = pytest.mark.django_db


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
    schema = toolset.asklens_query_plan_schema(context)
    resource = toolset.asklens_describe_resource(context, "orders")
    validation = toolset.asklens_validate_plan(context, valid_aggregate_plan())
    execution = toolset.asklens_execute_plan(
        context,
        valid_aggregate_plan(),
        include_rows=True,
    )

    assert seen_contexts == [context, context, context, context, context]
    assert capabilities["response_type"] == "capabilities"
    assert schema["response_type"] == "query_plan_schema"
    assert resource["valid"] is True
    assert validation["valid"] is True
    assert execution["response_type"] == "query"
    assert execution["rows_omitted"] is True
    assert execution["row_return_denied"] is True
    assert sorted(toolset.tools()) == [
        "asklens_capabilities",
        "asklens_describe_resource",
        "asklens_execute_plan",
        "asklens_query_plan_schema",
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

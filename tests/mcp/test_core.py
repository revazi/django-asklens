"""Tests for framework-neutral MCP core helpers."""

import pytest

from django_asklens.mcp import (
    asklens_capabilities,
    asklens_describe_resource,
    asklens_execute_plan,
    asklens_query,
    asklens_query_plan_schema,
    asklens_validate_plan,
)
from django_asklens.models import SemanticQueryRun
from tests.mcp._support import sensitive_list_plan, valid_aggregate_plan

pytestmark = pytest.mark.django_db


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


def test_mcp_capabilities_can_return_compact_resource_summaries(
    registered_orders: None,
    mcp_request,
) -> None:
    """Compact capabilities keep MCP discovery payloads small."""

    payload = asklens_capabilities(
        mcp_request,
        include_query_plan_schema=False,
        resource_detail="summary",
    )

    assert payload["response_type"] == "capabilities"
    assert "query_plan_schema" not in payload
    [resource] = payload["capabilities"]["resources"]
    assert resource["field_names"] == ["id", "status", "created_at"]
    assert resource["metric_names"] == ["order_count"]
    assert "fields" not in resource
    assert payload["capabilities"]["resource_detail"] == "summary"


def test_mcp_capabilities_reject_invalid_resource_detail(
    registered_orders: None,
    mcp_request,
) -> None:
    """Untrusted MCP capability arguments fail closed."""

    payload = asklens_capabilities(mcp_request, resource_detail="verbose")

    assert payload == {
        "response_type": "error",
        "executed": False,
        "rows_omitted": True,
        "error_category": "invalid_argument",
        "error": "resource_detail must be either 'summary' or 'full'.",
    }


def test_mcp_query_plan_schema_is_available_without_capabilities(
    registered_orders: None,
    mcp_request,
) -> None:
    """MCP clients can fetch the QueryPlan schema separately."""

    payload = asklens_query_plan_schema(mcp_request)

    assert payload["response_type"] == "query_plan_schema"
    assert payload["executed"] is False
    assert payload["rows_omitted"] is True
    assert payload["query_plan_schema"]["title"] == "QueryPlan"
    assert payload["query_plan_schema"]["required"] == ["resource", "intent"]


def test_mcp_describe_resource_returns_full_permission_scoped_metadata(
    registered_orders: None,
    mcp_request,
) -> None:
    """MCP clients can request full metadata for one visible resource."""

    payload = asklens_describe_resource(mcp_request, "orders")

    assert payload["response_type"] == "resource_description"
    assert payload["valid"] is True
    assert payload["executed"] is False
    assert payload["rows_omitted"] is True
    assert payload["resource"]["name"] == "orders"
    assert {field["name"] for field in payload["resource"]["fields"]} == {
        "id",
        "status",
        "created_at",
    }

    mcp_request.asklens_permissions = frozenset({"shop.view_customer_pii"})
    payload_with_permission = asklens_describe_resource(mcp_request, "orders")
    assert "customer.email" in {
        field["name"] for field in payload_with_permission["resource"]["fields"]
    }


def test_mcp_describe_resource_returns_safe_unknown_resource_error(
    registered_orders: None,
    mcp_request,
) -> None:
    """Unknown or unauthorized resources are not described."""

    payload = asklens_describe_resource(mcp_request, "missing")

    assert payload == {
        "response_type": "resource_description",
        "valid": False,
        "rows_omitted": True,
        "executed": False,
        "error_category": "unknown_resource",
        "error": "Resource 'missing' is not queryable for this request.",
    }


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
    assert payload["mcp_row_limit"] == 100
    assert payload["mcp_returned_row_count"] == 2
    assert payload["mcp_rows_truncated"] is False
    assert payload["data"] == [
        {"status": "paid", "order_count": 2},
        {"status": "pending", "order_count": 1},
    ]


def test_mcp_execute_plan_caps_returned_rows_when_rows_are_allowed(
    settings,
    registered_orders: None,
    order_data: None,
    mcp_request,
) -> None:
    """MCP row return has its own output cap beyond normal query limits."""

    settings.DJANGO_ASKLENS["MCP_ALLOW_ROW_RETURN"] = True
    settings.DJANGO_ASKLENS["MCP_MAX_RETURNED_ROWS"] = 2
    plan = {
        "resource": "orders",
        "intent": "list",
        "select": ["id", "status"],
        "order_by": [{"field": "id", "direction": "asc"}],
        "limit": 10,
        "visualization": {"type": "table"},
    }

    payload = asklens_execute_plan(mcp_request, plan, include_rows=True)

    assert payload["row_count"] == 3
    assert len(payload["data"]) == 2
    assert payload["rows_omitted"] is False
    assert payload["mcp_row_limit"] == 2
    assert payload["mcp_returned_row_count"] == 2
    assert payload["mcp_rows_truncated"] is True
    assert "MCP_MAX_RETURNED_ROWS" in payload["mcp_row_limit_warning"]


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

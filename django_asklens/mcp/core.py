"""Framework-neutral AskLens helpers suitable for MCP tool wrappers.

The functions in this module do not depend on an MCP SDK. They accept the same
request-like object used by AskLens core so host projects can map an
MCP-authenticated principal to ``request.user`` and existing permission/tenant
scope hooks before calling into AskLens.
"""

from collections.abc import Mapping
from typing import Any

from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.exceptions import (
    AskLensError,
    PermissionDeniedError,
    PlanValidationError,
)
from django_asklens.permissions import get_request_permissions
from django_asklens.planning.schemas import get_query_plan_json_schema
from django_asklens.planning.validation import parse_and_validate_query_plan
from django_asklens.querying import (
    AskLensQueryResponse,
    execute_asklens_query_request,
    safe_error_message,
)
from django_asklens.settings import get_asklens_setting

DEFAULT_MCP_PLAN_QUESTION = "MCP submitted QueryPlan"
MCP_ROW_RETURN_POLICY = (
    "Rows are omitted by default for MCP tool results because MCP clients often "
    "place tool output into an LLM context. To return rows, the tool call must "
    "pass include_rows=True and the Django project must set "
    "DJANGO_ASKLENS['MCP_ALLOW_ROW_RETURN'] = True."
)

__all__ = [
    "DEFAULT_MCP_PLAN_QUESTION",
    "MCP_ROW_RETURN_POLICY",
    "asklens_capabilities",
    "asklens_describe_resource",
    "asklens_execute_plan",
    "asklens_query",
    "asklens_query_plan_schema",
    "asklens_validate_plan",
    "apply_mcp_row_policy",
    "mcp_max_returned_rows",
    "mcp_row_return_allowed",
]


def asklens_capabilities(
    request: Any,
    *,
    include_query_plan_schema: bool = True,
    resource_detail: str = "full",
) -> dict[str, Any]:
    """Return permission-scoped capabilities for an MCP client.

    The payload is derived from registered catalog metadata only. It does not
    inspect database rows, include sample values, execute a query, or call an
    LLM provider.
    """

    if resource_detail not in {"full", "summary"}:
        return invalid_mcp_argument(
            "resource_detail must be either 'summary' or 'full'."
        )

    permissions = get_request_permissions(request)
    capabilities: dict[str, Any] = build_capabilities(permissions=permissions)
    if resource_detail == "summary":
        capabilities = summarize_capabilities(capabilities)

    payload: dict[str, Any] = {
        "response_type": "capabilities",
        "capabilities": capabilities,
        "rows_omitted": True,
        "executed": False,
        "explanation": (
            "Returned permission-scoped AskLens capabilities without executing "
            "a database query."
        ),
    }
    if include_query_plan_schema:
        payload["query_plan_schema"] = get_query_plan_json_schema()
    return payload


def asklens_query_plan_schema(request: Any) -> dict[str, Any]:
    """Return the QueryPlan JSON schema without catalog capabilities."""

    return {
        "response_type": "query_plan_schema",
        "query_plan_schema": get_query_plan_json_schema(),
        "rows_omitted": True,
        "executed": False,
        "explanation": (
            "Returned the AskLens QueryPlan JSON schema without executing a "
            "database query."
        ),
    }


def asklens_describe_resource(request: Any, resource: str) -> dict[str, Any]:
    """Return full permission-scoped metadata for one visible resource."""

    permissions = get_request_permissions(request)
    capabilities = build_capabilities(permissions=permissions)
    for resource_capability in capabilities["resources"]:
        if resource_capability["name"] == resource:
            return {
                "response_type": "resource_description",
                "valid": True,
                "resource": resource_capability,
                "rows_omitted": True,
                "executed": False,
                "explanation": (
                    "Returned full permission-scoped metadata for one AskLens "
                    "resource without executing a database query."
                ),
            }

    return {
        "response_type": "resource_description",
        "valid": False,
        "rows_omitted": True,
        "executed": False,
        "error_category": "unknown_resource",
        "error": f"Resource {resource!r} is not queryable for this request.",
    }


def summarize_capabilities(capabilities: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact capability view suitable for MCP discovery calls."""

    resources = capabilities.get("resources", [])
    summarized_resources = [
        summarize_resource_capability(resource)
        for resource in resources
        if isinstance(resource, Mapping)
    ]
    summary = dict(capabilities)
    summary["resources"] = summarized_resources
    summary["resource_detail"] = "summary"
    summary["resource_detail_guidance"] = (
        "Call asklens_describe_resource(resource) for full field and metric "
        "metadata before constructing a QueryPlan for a specific resource."
    )
    return summary


def summarize_resource_capability(resource: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact metadata for one permission-scoped resource."""

    fields = resource.get("fields", [])
    metrics = resource.get("metrics", [])
    date_fields = resource.get("date_fields", [])
    summary: dict[str, Any] = {
        "name": resource.get("name"),
        "label": resource.get("label"),
        "description": resource.get("description", ""),
        "default_date_field": resource.get("default_date_field"),
        "field_names": names_from_capability_items(fields),
        "metric_names": names_from_capability_items(metrics),
        "date_field_names": names_from_capability_items(date_fields),
        "examples": resource.get("examples", []),
        "scope": resource.get("scope", {}),
    }
    for optional_key in (
        "requires_permission",
        "scope_resource",
        "examples_enabled",
    ):
        if optional_key in resource:
            summary[optional_key] = resource[optional_key]
    return summary


def names_from_capability_items(value: Any) -> list[str]:
    """Return item names from a list of capability dictionaries."""

    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        if isinstance(item, Mapping) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def invalid_mcp_argument(message: str) -> dict[str, Any]:
    """Return a safe MCP argument error payload."""

    return {
        "response_type": "error",
        "executed": False,
        "rows_omitted": True,
        "error_category": "invalid_argument",
        "error": message,
    }


def asklens_validate_plan(
    request: Any,
    plan: str | bytes | Mapping[str, Any],
) -> dict[str, Any]:
    """Validate an MCP/client-produced QueryPlan without executing it.

    Client-produced plans are always treated as untrusted input. Validation uses
    the current request permissions and the registered AskLens catalog.
    """

    permissions = get_request_permissions(request)
    try:
        validated_plan = parse_and_validate_query_plan(
            plan,
            permissions=permissions,
        )
    except AskLensError as exc:
        return {
            "response_type": "plan_validation",
            "valid": False,
            "executed": False,
            "rows_omitted": True,
            "error_category": safe_mcp_error_category(exc),
            "error": safe_error_message(exc),
        }

    return {
        "response_type": "plan_validation",
        "valid": True,
        "executed": False,
        "rows_omitted": True,
        "plan": validated_plan.model_dump(mode="json"),
        "explanation": (
            "Validated the submitted QueryPlan against AskLens catalog, "
            "permissions, and limits without executing a database query."
        ),
    }


def asklens_execute_plan(
    request: Any,
    plan: str | bytes | Mapping[str, Any],
    *,
    question: str = DEFAULT_MCP_PLAN_QUESTION,
    include_rows: bool = False,
    include_visualization: bool = True,
    debug: bool = False,
) -> dict[str, Any]:
    """Validate and execute an MCP/client-produced QueryPlan.

    Rows are omitted from the returned payload by default. The database query is
    still executed through the normal AskLens path so row counts, audit records,
    limits, and visualization hints are accurate.
    """

    outcome = execute_asklens_query_request(
        request,
        question=question,
        debug=debug,
        include_visualization=include_visualization,
        provided_plan=dict(plan) if isinstance(plan, Mapping) else plan,
    )
    return apply_mcp_response_policy(outcome, include_rows=include_rows)


def asklens_query(
    request: Any,
    question: str,
    *,
    include_rows: bool = False,
    include_visualization: bool = True,
    debug: bool = False,
    provided_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run AskLens question orchestration from an MCP tool wrapper.

    This convenience helper may call the configured AskLens provider when the
    deployment uses a non-dummy backend. For MCP-native planning with no
    AskLens-side LLM call, use ``asklens_capabilities()``,
    ``asklens_validate_plan()``, and ``asklens_execute_plan()`` instead.
    """

    outcome = execute_asklens_query_request(
        request,
        question=question,
        debug=debug,
        include_visualization=include_visualization,
        provided_plan=dict(provided_plan) if provided_plan is not None else None,
    )
    return apply_mcp_response_policy(outcome, include_rows=include_rows)


def apply_mcp_response_policy(
    outcome: AskLensQueryResponse,
    *,
    include_rows: bool,
) -> dict[str, Any]:
    """Return a normalized MCP payload for one AskLens query outcome."""

    payload = dict(outcome.payload)
    payload.setdefault("response_type", outcome.response_type)
    if outcome.status_code != 200:
        payload.setdefault("status_code", outcome.status_code)
    return apply_mcp_row_policy(payload, include_rows=include_rows)


def safe_mcp_error_category(exc: AskLensError) -> str:
    """Return an MCP-oriented safe error category."""

    if isinstance(exc, PermissionDeniedError):
        return "permission_denied"
    if isinstance(exc, PlanValidationError):
        return "plan_validation_error"
    return "asklens_error"


def mcp_row_return_allowed() -> bool:
    """Return whether MCP helpers may include result rows in tool payloads."""

    return bool(get_asklens_setting("MCP_ALLOW_ROW_RETURN"))


def mcp_max_returned_rows() -> int:
    """Return the maximum rows an MCP tool result may include."""

    return max(0, int(get_asklens_setting("MCP_MAX_RETURNED_ROWS")))


def apply_mcp_row_return_limit(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return an MCP query payload capped by MCP_MAX_RETURNED_ROWS."""

    mcp_payload = dict(payload)
    rows = mcp_payload.get("data")
    if not isinstance(rows, list):
        mcp_payload["rows_omitted"] = False
        return mcp_payload

    max_rows = mcp_max_returned_rows()
    returned_rows = rows[:max_rows]
    mcp_payload["data"] = returned_rows
    mcp_payload["rows_omitted"] = False
    mcp_payload["mcp_row_limit"] = max_rows
    mcp_payload["mcp_returned_row_count"] = len(returned_rows)
    mcp_payload["mcp_rows_truncated"] = len(rows) > max_rows
    if mcp_payload["mcp_rows_truncated"]:
        mcp_payload["mcp_row_limit_warning"] = (
            f"Returned {len(returned_rows)} rows in the MCP tool payload, "
            f"capped by DJANGO_ASKLENS['MCP_MAX_RETURNED_ROWS']={max_rows}. "
            "The executed query row_count may be higher. Narrow the query or "
            "raise the MCP row cap intentionally to return more rows."
        )
    return mcp_payload


def apply_mcp_row_policy(
    payload: Mapping[str, Any],
    *,
    include_rows: bool,
) -> dict[str, Any]:
    """Return an MCP-safe payload with rows omitted unless explicitly allowed."""

    mcp_payload = dict(payload)
    if mcp_payload.get("response_type") != "query":
        return mcp_payload

    if include_rows and mcp_row_return_allowed():
        return apply_mcp_row_return_limit(mcp_payload)

    if include_rows:
        mcp_payload["row_return_denied"] = True

    mcp_payload["data"] = []
    mcp_payload["rows_omitted"] = True
    mcp_payload["row_return_policy"] = MCP_ROW_RETURN_POLICY
    return mcp_payload

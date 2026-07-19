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

DEFAULT_MCP_PLAN_QUESTION = "MCP submitted QueryPlan"
MCP_ROW_RETURN_POLICY = (
    "Rows are omitted by default for MCP tool results because MCP clients often "
    "place tool output into an LLM context. Call with include_rows=True only in "
    "trusted deployments or after explicit user approval."
)

__all__ = [
    "DEFAULT_MCP_PLAN_QUESTION",
    "MCP_ROW_RETURN_POLICY",
    "asklens_capabilities",
    "asklens_execute_plan",
    "asklens_query",
    "asklens_validate_plan",
    "apply_mcp_row_policy",
]


def asklens_capabilities(
    request: Any,
    *,
    include_query_plan_schema: bool = True,
) -> dict[str, Any]:
    """Return permission-scoped capabilities for an MCP client.

    The payload is derived from registered catalog metadata only. It does not
    inspect database rows, include sample values, execute a query, or call an
    LLM provider.
    """

    permissions = get_request_permissions(request)
    payload: dict[str, Any] = {
        "response_type": "capabilities",
        "capabilities": build_capabilities(permissions=permissions),
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


def apply_mcp_row_policy(
    payload: Mapping[str, Any],
    *,
    include_rows: bool,
) -> dict[str, Any]:
    """Return an MCP-safe payload with rows omitted unless explicitly allowed."""

    mcp_payload = dict(payload)
    if mcp_payload.get("response_type") != "query":
        return mcp_payload

    if include_rows:
        mcp_payload["rows_omitted"] = False
        return mcp_payload

    mcp_payload["data"] = []
    mcp_payload["rows_omitted"] = True
    mcp_payload["row_return_policy"] = MCP_ROW_RETURN_POLICY
    return mcp_payload

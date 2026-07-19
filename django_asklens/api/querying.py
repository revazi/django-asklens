"""Compatibility exports for AskLens query orchestration.

Shared query/help orchestration lives in :mod:`django_asklens.querying` so it can
be reused outside the DRF API package. Import from that module in new code.
"""

from django_asklens.querying import (
    AskLensQueryResponse,
    QueryResponseType,
    build_capabilities_payload,
    build_result_metadata,
    build_success_payload,
    create_query_run,
    enforce_debug_permission,
    execute_asklens_query_request,
    get_query_help_for_capabilities,
    get_user_permissions,
    safe_error_category,
    safe_error_message,
    safe_provider_fallback_message,
    should_return_capabilities_fallback,
    should_use_unified_provider_response,
)

__all__ = [
    "AskLensQueryResponse",
    "QueryResponseType",
    "build_capabilities_payload",
    "build_result_metadata",
    "build_success_payload",
    "create_query_run",
    "enforce_debug_permission",
    "execute_asklens_query_request",
    "get_query_help_for_capabilities",
    "get_user_permissions",
    "safe_error_category",
    "safe_error_message",
    "safe_provider_fallback_message",
    "should_return_capabilities_fallback",
    "should_use_unified_provider_response",
]

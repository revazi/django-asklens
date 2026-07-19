"""Framework-neutral helpers for exposing AskLens through MCP tools.

This package intentionally does not import an MCP SDK. Host projects can wrap
these functions with whichever Django-aware MCP server they use.
"""

from django_asklens.mcp.core import (
    DEFAULT_MCP_PLAN_QUESTION,
    MCP_ROW_RETURN_POLICY,
    apply_mcp_row_policy,
    asklens_capabilities,
    asklens_execute_plan,
    asklens_query,
    asklens_validate_plan,
    mcp_row_return_allowed,
)
from django_asklens.mcp.fastmcp import create_fastmcp_server
from django_asklens.mcp.wrappers import AskLensMCPToolSet, RequestFactory

__all__ = [
    "DEFAULT_MCP_PLAN_QUESTION",
    "AskLensMCPToolSet",
    "create_fastmcp_server",
    "MCP_ROW_RETURN_POLICY",
    "RequestFactory",
    "asklens_capabilities",
    "asklens_execute_plan",
    "asklens_query",
    "asklens_validate_plan",
    "apply_mcp_row_policy",
    "mcp_row_return_allowed",
]

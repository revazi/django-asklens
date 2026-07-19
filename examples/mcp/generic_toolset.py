"""Generic example for registering AskLens tools with an MCP server.

This file intentionally avoids importing a specific MCP SDK. Adapt
``register_asklens_tools`` to your server's decorator/registration API.
"""

from typing import Any

from django_asklens.mcp import AskLensMCPToolSet


def build_request_from_mcp_context(context: Any) -> Any:
    """Map trusted MCP server context to a Django request-like object.

    Implement this in your host project. The returned object should expose
    ``request.user`` and any attributes used by your AskLens
    ``REQUEST_PERMISSIONS_GETTER`` or resource ``base_queryset(request)`` hooks.

    Do not trust permission strings sent as tool arguments by the MCP client.
    Derive permissions from the authenticated server-side principal/session.
    """

    raise NotImplementedError


toolset = AskLensMCPToolSet(
    request_factory=build_request_from_mcp_context,
    # Keep this disabled unless you intentionally want AskLens to call its
    # configured provider from an MCP tool. MCP-native clients usually plan by
    # reading capabilities and submitting a QueryPlan to asklens_execute_plan.
    expose_query_tool=False,
)


def register_asklens_tools(mcp_server: Any) -> None:
    """Register AskLens tools with a generic decorator-style MCP server."""

    for name, tool in toolset.tools().items():
        mcp_server.tool(name=name)(tool)

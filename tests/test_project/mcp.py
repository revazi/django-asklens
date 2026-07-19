"""Concrete AskLens MCP integration example for the test project.

This module is intentionally dependency-free: it does not import an MCP SDK,
Django REST Framework, or a transport implementation. A real host project can
use the same shape with whichever MCP server it chooses.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from django_asklens.mcp import AskLensMCPToolSet

MCPToolCallable = Callable[..., dict[str, Any]]
MCPToolDecorator = Callable[[MCPToolCallable], MCPToolCallable]


@dataclass(frozen=True, slots=True)
class AskLensTestMCPContext:
    """Trusted server-side context for the test-project MCP example.

    A real MCP server would usually build this from its authenticated session or
    request context. The permission strings here are deliberately server-side
    metadata; they should not be accepted as client-controlled tool arguments.
    """

    user: Any
    asklens_permissions: frozenset[str] = field(default_factory=frozenset)
    tenant_scope: Mapping[str, Any] | None = None


def build_asklens_mcp_request(context: AskLensTestMCPContext) -> Any:
    """Map an MCP context to the request-like object AskLens expects."""

    return SimpleNamespace(
        user=context.user,
        asklens_permissions=context.asklens_permissions,
        tenant_scope=context.tenant_scope or {},
        mcp_context=context,
    )


def get_asklens_mcp_request_permissions(request: Any) -> frozenset[str]:
    """Return permission strings for the test-project MCP request example."""

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()

    permissions: set[str] = set(user.get_all_permissions())
    permissions.update(getattr(user, "asklens_extra_permissions", ()))
    permissions.update(getattr(request, "asklens_permissions", ()))
    return frozenset(permissions)


def build_asklens_mcp_toolset(*, expose_query_tool: bool = False) -> AskLensMCPToolSet:
    """Return the AskLens toolset used by the test-project MCP example."""

    return AskLensMCPToolSet(
        request_factory=build_asklens_mcp_request,
        expose_query_tool=expose_query_tool,
    )


def register_asklens_mcp_tools(
    mcp_server: Any,
    *,
    toolset: AskLensMCPToolSet | None = None,
) -> None:
    """Register AskLens tools on a decorator-style MCP server.

    The fake test server and many real MCP libraries support a shape like
    ``server.tool(name="...")(callable)``. If your MCP server has a different
    API, register the callables from ``toolset.tools()`` using that API instead.
    """

    resolved_toolset = toolset or build_asklens_mcp_toolset()
    for name, tool in resolved_toolset.tools().items():
        mcp_server.tool(name=name)(tool)


class InMemoryMCPServer:
    """Tiny test double showing the registration API AskLens expects."""

    def __init__(self) -> None:
        self.tools: dict[str, MCPToolCallable] = {}

    def tool(self, *, name: str) -> MCPToolDecorator:
        """Return a decorator that registers one tool callable."""

        def register(function: MCPToolCallable) -> MCPToolCallable:
            self.tools[name] = function
            return function

        return register

    def call_tool(
        self,
        name: str,
        context: AskLensTestMCPContext,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call a registered tool by name for tests and examples."""

        return self.tools[name](context, **kwargs)

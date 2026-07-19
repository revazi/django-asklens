"""Optional FastMCP bridge for AskLens MCP tools.

Importing this module does not require FastMCP. Calling
``create_fastmcp_server`` does, so core AskLens users do not inherit an MCP
server dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ImproperlyConfigured

from django_asklens.mcp.wrappers import AskLensMCPToolSet

if TYPE_CHECKING:
    from fastmcp import FastMCP

__all__ = ["create_fastmcp_server"]


def create_fastmcp_server(
    toolset: AskLensMCPToolSet,
    *,
    name: str = "Django AskLens",
    instructions: str | None = None,
) -> FastMCP:
    """Return a FastMCP server exposing one AskLens toolset.

    FastMCP is optional. Install it in host projects that want to expose a real
    MCP transport; dependency-free callers can keep using ``AskLensMCPToolSet``
    directly.
    """

    try:
        from fastmcp import FastMCP
        from fastmcp.dependencies import CurrentContext
    except ImportError as exc:  # pragma: no cover - exercised when extra absent
        msg = (
            "FastMCP is required to expose AskLens as an MCP server. Install "
            "fastmcp or use the dependency-free django_asklens.mcp helpers."
        )
        raise ImproperlyConfigured(msg) from exc

    current_context = CurrentContext()

    server = FastMCP(
        name,
        instructions=instructions
        or (
            "AskLens exposes permission-scoped analytics capabilities and "
            "validated read-only QueryPlan execution over registered Django "
            "resources. Prefer compact asklens_capabilities, "
            "asklens_describe_resource, asklens_query_plan_schema, "
            "asklens_validate_plan, and asklens_execute_plan for "
            "MCP-native planning."
        ),
    )

    @server.tool(name="asklens_capabilities")
    def capabilities(
        include_query_plan_schema: bool = False,
        resource_detail: str = "summary",
        ctx: Any = current_context,
    ) -> dict[str, Any]:
        """Return permission-scoped AskLens capabilities."""

        return toolset.asklens_capabilities(
            ctx,
            include_query_plan_schema=include_query_plan_schema,
            resource_detail=resource_detail,
        )

    @server.tool(name="asklens_query_plan_schema")
    def query_plan_schema(ctx: Any = current_context) -> dict[str, Any]:
        """Return the AskLens QueryPlan JSON schema."""

        return toolset.asklens_query_plan_schema(ctx)

    @server.tool(name="asklens_describe_resource")
    def describe_resource(
        resource: str,
        ctx: Any = current_context,
    ) -> dict[str, Any]:
        """Return full metadata for one permission-scoped AskLens resource."""

        return toolset.asklens_describe_resource(ctx, resource)

    @server.tool(name="asklens_validate_plan")
    def validate_plan(
        plan: dict[str, Any],
        ctx: Any = current_context,
    ) -> dict[str, Any]:
        """Validate an untrusted QueryPlan without executing a query."""

        return toolset.asklens_validate_plan(ctx, plan)

    @server.tool(name="asklens_execute_plan")
    def execute_plan(
        plan: dict[str, Any],
        include_rows: bool = False,
        question: str = "MCP submitted QueryPlan",
        include_visualization: bool = True,
        ctx: Any = current_context,
    ) -> dict[str, Any]:
        """Validate and execute an untrusted QueryPlan through safe ORM."""

        return toolset.asklens_execute_plan(
            ctx,
            plan,
            include_rows=include_rows,
            question=question,
            include_visualization=include_visualization,
        )

    if toolset.expose_query_tool:

        @server.tool(name="asklens_query")
        def query(
            question: str,
            include_rows: bool = False,
            include_visualization: bool = True,
            provided_plan: dict[str, Any] | None = None,
            ctx: Any = current_context,
        ) -> dict[str, Any]:
            """Run optional AskLens-managed query/help orchestration."""

            return toolset.asklens_query(
                ctx,
                question,
                include_rows=include_rows,
                include_visualization=include_visualization,
                provided_plan=provided_plan,
            )

    return server

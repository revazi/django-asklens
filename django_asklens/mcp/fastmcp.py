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
    except ImportError as exc:  # pragma: no cover - exercised when extra absent
        msg = (
            "FastMCP is required to expose AskLens as an MCP server. Install "
            "fastmcp or use the dependency-free django_asklens.mcp helpers."
        )
        raise ImproperlyConfigured(msg) from exc

    server = FastMCP(
        name,
        instructions=instructions
        or (
            "AskLens exposes permission-scoped analytics capabilities and "
            "validated read-only QueryPlan execution over registered Django "
            "resources. Prefer asklens_capabilities, asklens_validate_plan, "
            "and asklens_execute_plan for MCP-native planning."
        ),
    )

    @server.tool(name="asklens_capabilities")
    def capabilities() -> dict[str, Any]:
        """Return permission-scoped AskLens capabilities and QueryPlan schema."""

        return toolset.asklens_capabilities(None)

    @server.tool(name="asklens_validate_plan")
    def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
        """Validate an untrusted QueryPlan without executing a query."""

        return toolset.asklens_validate_plan(None, plan)

    @server.tool(name="asklens_execute_plan")
    def execute_plan(
        plan: dict[str, Any],
        include_rows: bool = False,
        question: str = "MCP submitted QueryPlan",
        include_visualization: bool = True,
    ) -> dict[str, Any]:
        """Validate and execute an untrusted QueryPlan through safe ORM."""

        return toolset.asklens_execute_plan(
            None,
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
        ) -> dict[str, Any]:
            """Run optional AskLens-managed query/help orchestration."""

            return toolset.asklens_query(
                None,
                question,
                include_rows=include_rows,
                include_visualization=include_visualization,
                provided_plan=provided_plan,
            )

    return server

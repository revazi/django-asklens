"""Dependency-free wrapper classes for registering AskLens MCP tools.

This module intentionally does not implement the MCP transport protocol and does
not import an MCP SDK. Instead, it gives host projects a small, AskLens-owned
surface that can be registered with whichever MCP server implementation they
choose.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from django_asklens.mcp.core import (
    DEFAULT_MCP_PLAN_QUESTION,
    asklens_capabilities,
    asklens_describe_resource,
    asklens_execute_plan,
    asklens_query,
    asklens_query_plan_schema,
    asklens_validate_plan,
)

RequestFactory = Callable[[Any], Any]

__all__ = ["AskLensMCPToolSet", "RequestFactory"]


@dataclass(frozen=True, slots=True)
class AskLensMCPToolSet:
    """AskLens tool wrappers suitable for MCP server registration.

    ``request_factory`` is deliberately host-provided because MCP authentication,
    sessions, tenants, and Django-user mapping are project-specific. The factory
    should derive the request-like object from trusted server context, not from
    client-controlled tool arguments.
    """

    request_factory: RequestFactory
    expose_query_tool: bool = False
    default_include_rows: bool = False
    include_query_plan_schema: bool = True
    capabilities_resource_detail: str = "full"

    def asklens_capabilities(
        self,
        context: Any,
        *,
        include_query_plan_schema: bool | None = None,
        resource_detail: str | None = None,
    ) -> dict[str, Any]:
        """Return permission-scoped AskLens capabilities for one MCP context."""

        return asklens_capabilities(
            self.request_factory(context),
            include_query_plan_schema=self._resolve_include_query_plan_schema(
                include_query_plan_schema
            ),
            resource_detail=self._resolve_capabilities_resource_detail(resource_detail),
        )

    def asklens_query_plan_schema(self, context: Any) -> dict[str, Any]:
        """Return the QueryPlan JSON schema for one MCP context."""

        return asklens_query_plan_schema(self.request_factory(context))

    def asklens_describe_resource(self, context: Any, resource: str) -> dict[str, Any]:
        """Return full permission-scoped metadata for one visible resource."""

        return asklens_describe_resource(self.request_factory(context), resource)

    def asklens_validate_plan(
        self,
        context: Any,
        plan: str | bytes | Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate a client-produced QueryPlan without executing it."""

        return asklens_validate_plan(self.request_factory(context), plan)

    def asklens_execute_plan(
        self,
        context: Any,
        plan: str | bytes | Mapping[str, Any],
        *,
        question: str = DEFAULT_MCP_PLAN_QUESTION,
        include_rows: bool | None = None,
        include_visualization: bool = True,
    ) -> dict[str, Any]:
        """Validate and execute a client-produced QueryPlan."""

        return asklens_execute_plan(
            self.request_factory(context),
            plan,
            question=question,
            include_rows=self._resolve_include_rows(include_rows),
            include_visualization=include_visualization,
        )

    def asklens_query(
        self,
        context: Any,
        question: str,
        *,
        include_rows: bool | None = None,
        include_visualization: bool = True,
        provided_plan: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run optional AskLens-managed question orchestration.

        This tool is disabled by default because it may call the configured
        AskLens provider in non-dummy deployments. MCP-native clients should
        prefer capabilities plus client-produced plan validation/execution.
        """

        if not self.expose_query_tool:
            return {
                "response_type": "error",
                "error_category": "tool_disabled",
                "error": (
                    "The AskLens MCP query tool is disabled. Use "
                    "asklens_capabilities, asklens_validate_plan, and "
                    "asklens_execute_plan, or construct the toolset with "
                    "expose_query_tool=True."
                ),
            }
        return asklens_query(
            self.request_factory(context),
            question,
            include_rows=self._resolve_include_rows(include_rows),
            include_visualization=include_visualization,
            provided_plan=provided_plan,
        )

    def tools(self) -> dict[str, Callable[..., dict[str, Any]]]:
        """Return named callables for generic MCP server registration."""

        tool_map: dict[str, Callable[..., dict[str, Any]]] = {
            "asklens_capabilities": self.asklens_capabilities,
            "asklens_query_plan_schema": self.asklens_query_plan_schema,
            "asklens_describe_resource": self.asklens_describe_resource,
            "asklens_validate_plan": self.asklens_validate_plan,
            "asklens_execute_plan": self.asklens_execute_plan,
        }
        if self.expose_query_tool:
            tool_map["asklens_query"] = self.asklens_query
        return tool_map

    def _resolve_include_rows(self, include_rows: bool | None) -> bool:
        """Resolve per-call row-return preference."""

        if include_rows is None:
            return self.default_include_rows
        return include_rows

    def _resolve_include_query_plan_schema(
        self,
        include_query_plan_schema: bool | None,
    ) -> bool:
        """Resolve per-call schema inclusion preference."""

        if include_query_plan_schema is None:
            return self.include_query_plan_schema
        return include_query_plan_schema

    def _resolve_capabilities_resource_detail(self, resource_detail: str | None) -> str:
        """Resolve per-call capabilities resource detail preference."""

        if resource_detail is None:
            return self.capabilities_resource_detail
        return resource_detail

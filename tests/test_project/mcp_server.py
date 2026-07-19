"""Opt-in FastMCP server for the runnable AskLens test project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

from django_asklens.mcp import create_fastmcp_server
from tests.test_project.asklens_registry import ensure_complex_resources_registered
from tests.test_project.mcp import AskLensTestMCPContext

if TYPE_CHECKING:
    from fastmcp import FastMCP


def create_demo_asklens_mcp_server() -> FastMCP:
    """Return the runnable test project's AskLens FastMCP server."""

    if getattr(settings, "TEST_PROJECT_REGISTER_COMPLEX_ASKLENS", False):
        ensure_complex_resources_registered()
    return create_fastmcp_server(
        build_asklens_mcp_toolset(
            expose_query_tool=getattr(
                settings,
                "DJANGO_ASKLENS_MCP_EXPOSE_QUERY",
                False,
            ),
        ),
        name="Django AskLens demo",
        instructions=(
            "AskLens demo MCP server. The authenticated demo user is selected "
            "server-side by DJANGO_ASKLENS_MCP_USERNAME. Use capabilities, "
            "validate_plan, and execute_plan for MCP-native planning."
        ),
    )


def build_demo_mcp_context() -> AskLensTestMCPContext:
    """Return server-side MCP context for the configured demo user."""

    username = getattr(settings, "DJANGO_ASKLENS_MCP_USERNAME", "")
    if not username:
        msg = "DJANGO_ASKLENS_MCP_USERNAME must be set when demo MCP is enabled."
        raise ImproperlyConfigured(msg)

    user_model = get_user_model()
    try:
        user = user_model.objects.get(username=username)
    except user_model.DoesNotExist as exc:
        msg = (
            f"DJANGO_ASKLENS_MCP_USERNAME={username!r} does not match a demo user. "
            "Run `python -m django seed_complex_test_project "
            "--settings=tests.test_project.demo_settings`."
        )
        raise ImproperlyConfigured(msg) from exc
    return AskLensTestMCPContext(user=user)


def build_asklens_mcp_toolset(*, expose_query_tool: bool = False):
    """Return a toolset whose request context is derived server-side."""

    from django_asklens.mcp import AskLensMCPToolSet
    from tests.test_project.mcp import build_asklens_mcp_request

    return AskLensMCPToolSet(
        request_factory=lambda _context: build_asklens_mcp_request(
            build_demo_mcp_context()
        ),
        expose_query_tool=expose_query_tool,
    )

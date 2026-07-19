"""Smoke-test installed django-asklens wheels in isolated CI venvs."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from types import SimpleNamespace

import django
from django.conf import settings
from django.core.management import call_command


def main() -> None:
    """Run the requested wheel smoke scenario."""

    mode = sys.argv[1]
    assert django.get_version().startswith(os.environ["DJANGO_VERSION_PREFIX"])
    if mode == "core":
        smoke_core_install()
    elif mode == "mcp":
        smoke_mcp_extra_install()
    elif mode == "api":
        smoke_api_extra_install()
    else:
        raise SystemExit(f"Unsupported wheel smoke mode: {mode}")


def smoke_core_install() -> None:
    """Check the core wheel imports without optional DRF or FastMCP extras."""

    assert importlib.util.find_spec("rest_framework") is None
    assert importlib.util.find_spec("fastmcp") is None

    import django_asklens

    assert django_asklens.__version__ == "0.1.0a1"
    configure_settings(installed_apps=["django_asklens"])

    from django_asklens.access import can_access_asklens
    from django_asklens.catalog.registry import serialize_catalog
    from django_asklens.mcp import AskLensMCPToolSet
    from django_asklens.planning import parse_query_plan

    request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
    assert can_access_asklens(request) is True
    assert serialize_catalog()["resources"] == []
    assert AskLensMCPToolSet(request_factory=lambda _context: request).tools()
    assert (
        parse_query_plan(
            {"resource": "orders", "intent": "list", "select": [], "limit": 1}
        ).resource
        == "orders"
    )


def smoke_mcp_extra_install() -> None:
    """Check the optional MCP extra installs FastMCP without DRF."""

    assert importlib.util.find_spec("fastmcp") is not None
    assert importlib.util.find_spec("rest_framework") is None
    configure_settings(installed_apps=["django_asklens"])

    from django_asklens.mcp import AskLensMCPToolSet, create_fastmcp_server

    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, get_all_permissions=lambda: set())
    )
    seen_contexts = []

    def request_factory(context):
        seen_contexts.append(context)
        return request

    toolset = AskLensMCPToolSet(request_factory=request_factory)
    server = create_fastmcp_server(toolset)
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "asklens_capabilities",
        "asklens_query_plan_schema",
        "asklens_describe_resource",
        "asklens_validate_plan",
        "asklens_execute_plan",
    }
    result = asyncio.run(server.call_tool("asklens_capabilities", {}))
    assert result.structured_content["response_type"] == "capabilities"
    assert seen_contexts and seen_contexts[0].__class__.__name__ == "Context"


def smoke_api_extra_install() -> None:
    """Check the optional API extra installs DRF and API URLs."""

    assert importlib.util.find_spec("rest_framework") is not None
    configure_settings(
        installed_apps=["rest_framework", "django_asklens"],
        root_urlconf="django_asklens.api.urls",
    )

    import django_asklens.api.urls

    assert django_asklens.api.urls.urlpatterns


def configure_settings(
    *,
    installed_apps: list[str],
    root_urlconf: str | None = None,
) -> None:
    """Configure minimal Django settings for one isolated smoke test."""

    settings.configure(
        SECRET_KEY="django-asklens-ci-wheel-smoke-test",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            *installed_apps,
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        MIDDLEWARE=[],
        ROOT_URLCONF=root_urlconf,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()
    call_command("check")


if __name__ == "__main__":
    main()

"""ASGI entrypoint for the runnable AskLens demo project.

Set DJANGO_ASKLENS_MCP_ENABLED=1 to expose the local FastMCP endpoint at /mcp.
"""

import os
from contextlib import asynccontextmanager

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.test_project.demo_settings")

from django.conf import settings  # noqa: E402
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402


def build_application():
    """Return the demo ASGI app, optionally with an AskLens MCP endpoint."""

    django_application = build_django_application()
    if not getattr(settings, "DJANGO_ASKLENS_MCP_ENABLED", False):
        return django_application

    from starlette.applications import Starlette
    from starlette.routing import Mount

    from tests.test_project.mcp_server import create_demo_asklens_mcp_server

    mcp_http_app = create_demo_asklens_mcp_server().http_app(
        path="/mcp",
        transport="http",
        stateless_http=True,
    )

    @asynccontextmanager
    async def lifespan(app):
        async with mcp_http_app.lifespan(app):
            yield

    return Starlette(
        routes=[
            *mcp_http_app.routes,
            Mount("/", app=django_application),
        ],
        lifespan=lifespan,
    )


def build_django_application():
    """Return Django's ASGI app, with local staticfiles serving when available."""

    application = get_asgi_application()
    if not getattr(settings, "STATIC_URL", None):
        return application
    if "django.contrib.staticfiles" not in getattr(settings, "INSTALLED_APPS", []):
        return application
    return ASGIStaticFilesHandler(application)


application = build_application()

"""MCP-only recipe: no HTTP API/admin apps or transport authentication defaults."""

from .settings import *  # noqa: F403

DJANGO_ASKLENS = {  # noqa: F405
    **DJANGO_ASKLENS,  # noqa: F405
    "API_PERMISSION_CLASSES": ["django_asklens.access.IsAuthenticated"],
    "REQUEST_PERMISSIONS_GETTER": None,
    "MCP_ALLOW_ROW_RETURN": False,
    "MCP_MAX_RETURNED_ROWS": 1,
}

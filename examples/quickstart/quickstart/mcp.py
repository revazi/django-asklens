"""Inject host authentication; never accept identity as a tool argument."""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from django_asklens.access import can_access_asklens
from django_asklens.mcp import AskLensMCPToolSet, create_fastmcp_server


def make_toolset(authenticated_user_id):
    """The host callback resolves a verified server session on EVERY tool call.

    It must reject invalid/expired connections and return the host-mapped Django
    user PK, never a username/PK/permission/tenant claim from tool arguments.
    No authentication implementation or permissive default is supplied here.
    """

    def request_from_context(context):
        user_id = authenticated_user_id(context)
        if type(user_id) is not int:
            raise PermissionDenied("The current request is not authorized.")
        # Fresh ORM identity avoids reusing Django's cached permission set.
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            raise PermissionDenied("The current request is not authorized.")
        request = SimpleNamespace(user=user)
        if not can_access_asklens(request):
            raise PermissionDenied("The current request is not authorized.")
        return request

    return AskLensMCPToolSet(
        request_factory=request_from_context,
        expose_query_tool=False,
        default_include_rows=False,
        include_query_plan_schema=False,
        capabilities_resource_detail="summary",
    )


def make_server(authenticated_user_id):
    """Wire tools only; the host must secure and mount the actual transport."""
    return create_fastmcp_server(make_toolset(authenticated_user_id))

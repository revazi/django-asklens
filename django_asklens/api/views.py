"""DRF views for the AskLens API."""

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django_asklens.api.permissions import get_api_permission_classes
from django_asklens.api.serializers import (
    QueryRequestSerializer,
    SemanticQueryRunSerializer,
)
from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.catalog.registry import serialize_catalog
from django_asklens.models import SemanticQueryRun
from django_asklens.permissions import get_request_permissions
from django_asklens.querying import (
    build_capabilities_payload,
    build_success_payload,
    create_query_run,
    enforce_debug_permission,
    execute_asklens_query_request,
    get_query_help_for_capabilities,
    get_user_permissions,
    safe_error_message,
    should_return_capabilities_fallback,
    should_use_unified_provider_response,
)

__all__ = [
    "AskLensAPIView",
    "CapabilitiesView",
    "CatalogView",
    "QueryRunDetailView",
    "QueryView",
    "build_capabilities_payload",
    "build_success_payload",
    "can_view_run",
    "create_query_run",
    "enforce_debug_permission",
    "get_query_help_for_capabilities",
    "get_user_permissions",
    "safe_error_message",
    "should_return_capabilities_fallback",
    "should_use_unified_provider_response",
]


class AskLensAPIView(APIView):
    """Base API view with configurable AskLens permissions."""

    def get_permissions(self):
        """Instantiate configured permission classes."""

        return [permission() for permission in get_api_permission_classes()]


class CatalogView(AskLensAPIView):
    """Return safe semantic catalog metadata."""

    def get(self, request: Request) -> Response:
        """Return catalog metadata visible to the planner by default."""

        return Response(serialize_catalog(permissions=get_request_permissions(request)))


class CapabilitiesView(AskLensAPIView):
    """Return permission-scoped guidance about what can be queried."""

    def get(self, request: Request) -> Response:
        """Return safe capabilities derived from visible catalog metadata."""

        return Response(
            build_capabilities(permissions=get_request_permissions(request))
        )


class QueryView(AskLensAPIView):
    """Plan, execute, help, and audit one natural-language query."""

    def post(self, request: Request) -> Response:
        """Execute one AskLens query request."""

        serializer = QueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = execute_asklens_query_request(
            request,
            question=serializer.validated_data["question"],
            debug=serializer.validated_data["debug"],
            include_visualization=serializer.validated_data["include_visualization"],
            provided_plan=serializer.validated_data.get("plan"),
        )
        return Response(outcome.payload, status=outcome.status_code)


class QueryRunDetailView(AskLensAPIView):
    """Return one audited query run."""

    def get(self, request: Request, pk: int) -> Response:
        """Return a query run if the requester may view it."""

        run = get_object_or_404(SemanticQueryRun, pk=pk)
        if not can_view_run(request, run):
            raise PermissionDenied("You do not have access to this AskLens run.")
        return Response(SemanticQueryRunSerializer(run).data)


def can_view_run(request: Request, run: SemanticQueryRun) -> bool:
    """Return whether a request user can view a run."""

    user = request.user
    if getattr(user, "is_staff", False):
        return True
    return bool(getattr(user, "is_authenticated", False) and run.user_id == user.pk)

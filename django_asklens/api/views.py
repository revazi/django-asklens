"""DRF views for the AskLens API."""

from django.db import DatabaseError
from django.db.utils import ConnectionDoesNotExist
from rest_framework.exceptions import APIException, NotFound
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
from django_asklens.execution.audit import (
    _AuditDatabaseUnavailable,
    _resolve_audit_database_alias,
)
from django_asklens.models import SemanticQueryRun
from django_asklens.permissions import get_request_permissions
from django_asklens.querying import (
    build_capabilities_payload,
    build_success_payload,
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
    """Return machine-readable query features and structural limits."""

    def get(self, request: Request) -> Response:
        """Return machine capabilities without catalog or human guidance."""

        return Response(build_capabilities())


class QueryView(AskLensAPIView):
    """Plan, execute, help, and audit one natural-language query."""

    def post(self, request: Request) -> Response:
        """Execute one AskLens query request."""

        serializer = QueryRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "response_type": "error",
                    "error": {
                        "code": "asklens.parse.invalid",
                        "message": "The query request could not be parsed.",
                    },
                },
                status=400,
            )
        outcome = execute_asklens_query_request(
            request,
            question=serializer.validated_data["question"],
            debug=serializer.validated_data["debug"],
            include_presentation=serializer.validated_data["include_presentation"],
            provided_plan=serializer.validated_data.get("plan"),
            provided_presentation=serializer.validated_data.get("presentation"),
        )
        return Response(outcome.payload, status=outcome.status_code)


class _AuditRecordsUnavailable(APIException):
    """Return one fixed safe response for audit database failures."""

    status_code = 503
    default_detail = "AskLens audit records are unavailable."
    default_code = "audit_unavailable"


class QueryRunDetailView(AskLensAPIView):
    """Return one audited query run."""

    def get(self, request: Request, pk: int) -> Response:
        """Return a run selected through current authorization and audit routing."""

        try:
            alias = _resolve_audit_database_alias()
            queryset = SemanticQueryRun.objects.all()
            if alias is not None:
                queryset = queryset.using(alias)
            user = request.user
            if not getattr(user, "is_authenticated", False):
                queryset = queryset.none()
            elif not user.has_perm("asklens.view_semanticqueryrun"):
                queryset = queryset.filter(user_id=user.pk)
            try:
                run = queryset.get(pk=pk)
            except SemanticQueryRun.DoesNotExist:
                raise NotFound("AskLens run not found.") from None
        except (
            _AuditDatabaseUnavailable,
            ConnectionDoesNotExist,
            DatabaseError,
        ):
            raise _AuditRecordsUnavailable from None
        return Response(SemanticQueryRunSerializer(run).data)


def can_view_run(request: Request, run: SemanticQueryRun) -> bool:
    """Return whether a request user can view a run."""

    user = request.user
    return bool(
        getattr(user, "is_authenticated", False)
        and (run.user_id == user.pk or user.has_perm("asklens.view_semanticqueryrun"))
    )

"""DRF views for the AskLens API."""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import DatabaseError
from django.db.utils import ConnectionDoesNotExist
from django.http import Http404
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAcceptable,
    NotAuthenticated,
    NotFound,
    ParseError,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.exceptions import (
    PermissionDenied as DRFPermissionDenied,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView, set_rollback

from django_asklens.api.permissions import get_api_permission_classes
from django_asklens.api.serializers import (
    QueryRequestSerializer,
    SemanticQueryRunSerializer,
)
from django_asklens.catalog.capabilities import build_capabilities
from django_asklens.catalog.registry import serialize_catalog
from django_asklens.exceptions import AskLensError, public_error_payload
from django_asklens.execution.audit import (
    _AuditDatabaseUnavailable,
    _resolve_audit_database_alias,
)
from django_asklens.models import SemanticQueryRun
from django_asklens.permissions import get_request_permissions
from django_asklens.querying import execute_asklens_query_request

__all__ = [
    "AskLensAPIView",
    "CapabilitiesView",
    "CatalogView",
    "QueryRunDetailView",
    "QueryView",
]

logger = logging.getLogger(__name__)

_PARSE_ERROR = {
    "code": "asklens.parse.invalid",
    "message": "The AskLens request could not be parsed.",
}
_AUTHORIZATION_ERROR = {
    "code": "asklens.authorization.denied",
    "message": "The current request is not authorized.",
}
_MEMBER_UNAVAILABLE_ERROR = {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable.",
}
_BUDGET_ERROR = {
    "code": "asklens.budget.exceeded",
    "message": "The AskLens request exceeds an execution limit.",
}
_EXECUTION_ERROR = {
    "code": "asklens.execute.failed",
    "message": "The AskLens request could not be completed.",
}


def _error_envelope(
    error: dict[str, Any],
    *,
    run_id: int | None = None,
) -> dict[str, Any]:
    """Return the only HTTP error envelope emitted by AskLens DRF views."""

    payload: dict[str, Any] = {"error": dict(error)}
    if run_id is not None:
        payload["run_id"] = run_id
    return payload


def _framework_error(exc: Exception) -> dict[str, Any]:
    """Map one route-local framework exception to a fixed safe ErrorDocument."""

    if isinstance(exc, (Http404, NotFound)):
        return _MEMBER_UNAVAILABLE_ERROR
    if isinstance(
        exc,
        (
            AuthenticationFailed,
            NotAuthenticated,
            DRFPermissionDenied,
            DjangoPermissionDenied,
        ),
    ):
        return _AUTHORIZATION_ERROR
    if isinstance(exc, Throttled):
        return _BUDGET_ERROR
    if isinstance(
        exc,
        (
            MethodNotAllowed,
            NotAcceptable,
            ParseError,
            UnsupportedMediaType,
            ValidationError,
        ),
    ):
        return _PARSE_ERROR
    return _EXECUTION_ERROR


class AskLensAPIView(APIView):
    """Base API view with configurable AskLens permissions."""

    def get_permissions(self):
        """Instantiate configured permission classes."""

        return [permission() for permission in get_api_permission_classes()]

    def handle_exception(self, exc: Exception) -> Response:
        """Normalize only AskLens-view failures while retaining DRF semantics."""

        if isinstance(exc, AskLensError):
            set_rollback()
            response = Response(status=400)
            response.exception = True
            error = public_error_payload(exc)
        else:
            try:
                response = super().handle_exception(exc)
            except Exception:
                set_rollback()
                logger.exception("Unexpected AskLens API error.")
                response = Response(status=500)
                response.exception = True
                error = _EXECUTION_ERROR
            else:
                error = _framework_error(exc)
        response.data = _error_envelope(error)
        return response


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
            return Response(_error_envelope(_PARSE_ERROR), status=400)
        outcome = execute_asklens_query_request(
            request,
            question=serializer.validated_data["question"],
            debug=serializer.validated_data["debug"],
            include_presentation=serializer.validated_data["include_presentation"],
            provided_plan=serializer.validated_data.get("plan"),
            provided_presentation=serializer.validated_data.get("presentation"),
        )
        if outcome.response_type == "error":
            run_id = outcome.run.pk if outcome.run is not None else None
            return Response(
                _error_envelope(outcome.payload["error"], run_id=run_id),
                status=outcome.status_code,
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
